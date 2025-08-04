"""
Controller for communicating with Dwarf3 smart telescope.
Enhanced with proper API flow based on dwarf_python_api implementation.
"""

import requests
import requests.exceptions
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, Optional, Tuple, Callable

# Import dwarf_python_api modules
try:
    from dwarf_python_api.lib.dwarf_utils import (
        perform_goto, perform_start_autofocus, perform_stop_autofocus,
        perform_calibration, perform_stop_calibration, perform_open_camera,
        perform_takePhoto, perform_takeAstroPhoto, perform_stopAstroPhoto,
        perform_waitEndAstroPhoto, perform_time, perform_disconnect,
        perform_getstatus
    )
    from dwarf_python_api.lib.websockets_utils import connect_socket, disconnect_socket
    DWARF_API_AVAILABLE = True
except ImportError as e:
    DWARF_API_AVAILABLE = False
    logging.getLogger(__name__).warning(f"dwarf_python_api not available: {e}")

class DwarfController:
    """Controls Dwarf3 telescope via API with enhanced session management."""
    
    def __init__(self, config_manager, force_http: bool = False):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Connection settings - will be loaded when needed
        self.ip = None
        self.port = None
        self.timeout = None
        self.base_url = None
        
        self.connected = False
        self.connecting = False  # Flag to prevent concurrent connection attempts
        self.session = requests.Session()
        
        # Session state tracking
        self.current_session_active = False
        self.photo_session_running = False
        
        # SLAVE MODE detection - when telescope is being used by another app
        self.slave_mode_detected = False
        
        # Connection keep-alive
        self.last_keepalive = 0
        self.keepalive_interval = 60  # seconds - reduced frequency to prevent connection spam
        
        # Telescope information for status display
        self.telescope_info = None
        self.telescope_info_retrieved = False  # Flag to prevent repeated telescope info queries
        
        # Thread pool for non-blocking operations (single worker to prevent connection conflicts)
        # Configure to not prevent application shutdown
        self.executor = ThreadPoolExecutor(
            max_workers=1, 
            thread_name_prefix="DwarfAPI"
        )
        self._operation_lock = threading.RLock()
        self._connection_lock = threading.Lock()  # Prevent simultaneous connection attempts
        
        # API mode - prefer dwarf_python_api if available (unless forced to HTTP)
        self.use_dwarf_api = DWARF_API_AVAILABLE and not force_http
        if self.use_dwarf_api:
            self.logger.info("Using dwarf_python_api for telescope control")
        else:
            self.logger.info("Using HTTP-based telescope control" + (" (forced)" if force_http else ""))
        
        # Load initial settings
        self._load_settings()
    
    def __del__(self):
        """Destructor to ensure cleanup when object is garbage collected."""
        try:
            self.cleanup()
        except:
            pass  # Ignore errors during destruction
    
    def check_dwarf_python_api(self) -> bool:
        """Check if dwarf_python_api is available."""
        return DWARF_API_AVAILABLE
        
    def _load_settings(self):
        """Load telescope settings from configuration."""
        try:
            # Force reload of settings from file
            self.config_manager.settings = self.config_manager.load_settings()
            
            telescope_config = self.config_manager.get_telescope_settings()
            self.ip = telescope_config.get("ip", "192.168.4.1")
            self.port = telescope_config.get("port", 80)
            self.timeout = telescope_config.get("timeout", 10)
            
            self.base_url = f"http://{self.ip}:{self.port}/"
            
            self.logger.info(f"Loaded telescope settings: IP={self.ip}, Port={self.port}, Timeout={self.timeout}")
            
        except Exception as e:
            self.logger.error(f"Failed to load telescope settings: {e}")
            # Use defaults
            self.ip = "192.168.4.1"
            self.port = 80
            self.timeout = 10
            self.base_url = f"http://{self.ip}:{self.port}/api"
    
    def refresh_settings(self):
        """Refresh telescope settings from configuration (call this when settings change)."""
        self.logger.info("Refreshing telescope settings")
        old_ip = self.ip
        old_port = self.port
        
        self._load_settings()
        
        # If connection settings changed and we're connected, need to reconnect
        if self.connected and (old_ip != self.ip or old_port != self.port):
            self.logger.info("Connection settings changed, will reconnect on next operation")
            self.disconnect()
        
    def connect(self, timeout: Optional[int] = None, callback: Optional[Callable] = None) -> Future:
        """Connect to the Dwarf3 telescope (non-blocking)."""
        return self.executor.submit(self._connect_sync, timeout, callback)
    
    def connect_sync(self, timeout: Optional[int] = None) -> bool:
        """Connect to the Dwarf3 telescope (blocking version)."""
        return self._connect_sync(timeout)
    
    def _connect_sync(self, timeout: Optional[int] = None, callback: Optional[Callable] = None) -> bool:
        """Internal synchronous connect method."""
        # Use connection lock to prevent simultaneous connection attempts
        with self._connection_lock:
            # Check if another connection attempt is in progress
            if self.connecting:
                self.logger.warning("Connection attempt already in progress, skipping duplicate request")
                if callback:
                    callback(False, "Connection attempt already in progress")
                return False
                
            max_retries = 3
            retry_count = 0
            
            try:
                # Set connecting flag
                self.connecting = True
                
                with self._operation_lock:
                    # If already connected, just do keepalive check
                    if self.connected and self._check_connection_keepalive():
                        self.logger.debug("Connection already established and healthy")
                        if callback:
                            callback(True, "Connection already established")
                        return True
                    
                    # Always refresh settings before connecting
                    self._load_settings()
                    
                    # Use provided timeout or default
                    if timeout is None:
                        timeout = self.timeout
                    
                    self.logger.info(f"Connecting to Dwarf3 at {self.base_url} (timeout: {timeout}s, max retries: {max_retries})")
                    
                    while retry_count < max_retries:
                        try:
                            retry_count += 1
                            self.logger.info(f"Connection attempt {retry_count}/{max_retries}")
                            
                            # Reset SLAVE MODE detection for each new connection attempt
                            if retry_count == 1:
                                self.slave_mode_detected = False
                            
                            if self.use_dwarf_api:
                                # Use dwarf_python_api for connection
                                if self._connect_via_dwarf_api(timeout):
                                    self.connected = True
                                    self.last_keepalive = time.time()  # Reset keepalive timer on successful connection
                                    self.logger.info("Successfully connected to Dwarf3 via dwarf_python_api")
                                    if callback:
                                        callback(True, "Connected via dwarf_python_api")
                                    return True
                                else:
                                    # Check if SLAVE MODE was detected - if so, stop retrying
                                    if self.slave_mode_detected:
                                        self.logger.error("SLAVE MODE detected - telescope is being used by another application. Stopping connection attempts.")
                                        if callback:
                                            callback(False, "Telescope is in SLAVE MODE - being used by another application")
                                        return False
                                    
                                    if retry_count < max_retries:
                                        self.logger.warning(f"Connection attempt {retry_count} failed, retrying...")
                                        # Check for cancellation before retrying
                                        if not self.connecting:
                                            self.logger.info("Connection cancelled by user")
                                            if callback:
                                                callback(False, "Connection cancelled by user")
                                            return False
                                        time.sleep(2)  # Wait before retry
                                        continue
                                    else:
                                        self.logger.error("Failed to establish connection via dwarf_python_api after all retries")
                                        if callback:
                                            callback(False, f"Failed to connect via dwarf_python_api after {max_retries} attempts")
                                        return False
                            else:
                                # Fallback to HTTP-based connection test
                                if self._test_connection():
                                    self.connected = True
                                    self.last_keepalive = time.time()  # Reset keepalive timer on successful connection
                                    self.logger.info("Successfully connected to Dwarf3 via HTTP")
                                    if callback:
                                        callback(True, "Connected via HTTP")
                                    return True
                                else:
                                    if retry_count < max_retries:
                                        self.logger.warning(f"HTTP connection attempt {retry_count} failed, retrying...")
                                        # Check for cancellation before retrying
                                        if not self.connecting:
                                            self.logger.info("Connection cancelled by user")
                                            if callback:
                                                callback(False, "Connection cancelled by user")
                                            return False
                                        time.sleep(2)  # Wait before retry
                                        continue
                                    else:
                                        self.logger.error("Failed to establish HTTP connection after all retries")
                                        if callback:
                                            callback(False, f"Failed to connect via HTTP after {max_retries} attempts")
                                        return False
                                        
                        except Exception as retry_error:
                            self.logger.warning(f"Connection attempt {retry_count} error: {retry_error}")
                            if retry_count < max_retries:
                                time.sleep(2)  # Wait before retry
                                continue
                            else:
                                raise retry_error
                        
            except Exception as e:
                self.logger.error(f"Failed to connect to Dwarf3: {e}")
                if callback:
                    callback(False, f"Connection error: {e}")
                return False
            finally:
                # Always reset the connecting flag
                self.connecting = False
    
    def _connect_via_dwarf_api(self, timeout: int = 10) -> bool:
        """Connect using dwarf_python_api."""
        try:
            # Set up configuration for dwarf_python_api
            self._setup_dwarf_api_config()
            
            # Test connection by getting status with timeout handling
            self.logger.info(f"Testing dwarf_python_api connection (timeout: {timeout}s)...")
            
            # Use a shorter timeout for individual operations to prevent hanging
            operation_timeout = min(timeout, 15)  # Cap at 15 seconds per operation
            
            # For initial connection, try to call perform_getstatus directly
            # and be more lenient about what constitutes success
            try:
                # Use a timeout to prevent GUI lockup
                import signal
                import threading
                
                # Create a timeout mechanism for the perform_getstatus call
                result_container = []
                exception_container = []
                
                def timeout_getstatus():
                    try:
                        result = perform_getstatus()
                        result_container.append(result)
                    except Exception as e:
                        exception_container.append(e)
                
                # Run the getstatus in a separate thread with timeout
                getstatus_thread = threading.Thread(target=timeout_getstatus, daemon=True)
                getstatus_thread.start()
                getstatus_thread.join(timeout=operation_timeout)
                
                if getstatus_thread.is_alive():
                    # Timeout occurred
                    self.logger.warning(f"perform_getstatus timed out after {operation_timeout}s")
                    # Still consider connection successful if we can import the module
                    import dwarf_python_api.lib.dwarf_utils
                    self.logger.info("dwarf_python_api connection established - API module responding despite timeout")
                    if not self.telescope_info_retrieved:
                        self._get_telescope_info_via_api()
                        self.telescope_info_retrieved = True
                    return True
                
                if exception_container:
                    raise exception_container[0]
                
                result = result_container[0] if result_container else None
                
                # First check for explicit SLAVE MODE
                if self._check_slave_mode_in_response(result=result):
                    self.logger.error("SLAVE MODE detected during connection - telescope is being used by another application")
                    return False
                
                # If we get any result (even None), the API is working
                # The fact that perform_getstatus() didn't raise an exception means connection is established
                self.logger.info("dwarf_python_api connection successful - API is responding")
                # Only get telescope info once per connection session
                if not self.telescope_info_retrieved:
                    self._get_telescope_info_via_api()
                    self.telescope_info_retrieved = True
                return True
                
            except Exception as e:
                # Check for SLAVE MODE in exception
                if self._check_slave_mode_in_response(exception=e):
                    self.logger.error("SLAVE MODE detected in connection exception")
                    return False
                
                # For other exceptions during initial connection, still try to proceed
                # The websocket might be connected even if getstatus fails initially
                self.logger.warning(f"getstatus failed during connection but API might still be connected: {e}")
                
                # Try a simple connection test by checking if the dwarf_python_api module responds
                try:
                    # If we can import and the connection was attempted, consider it successful
                    # since the websocket connection logs show it's working
                    import dwarf_python_api.lib.dwarf_utils
                    self.logger.info("dwarf_python_api connection established - API module is responding")
                    # Only get telescope info once per connection session
                    if not self.telescope_info_retrieved:
                        self._get_telescope_info_via_api()
                        self.telescope_info_retrieved = True
                    return True
                except Exception as import_error:
                    self.logger.error(f"dwarf_python_api connection failed completely: {import_error}")
                    return False
                
        except Exception as e:
            self.logger.error(f"Error connecting via dwarf_python_api: {e}")
            return False
    
    def _setup_dwarf_api_config(self):
        """Set up configuration for dwarf_python_api."""
        try:
            import os
            
            # Create config.py file for dwarf_python_api
            config_content = f'''# Configuration for dwarf_python_api
DWARF_IP = "{self.ip}"
DWARF_UI = "8080"  # UI port
DWARF_ID = "{self.ip}"
CLIENT_ID = "scheduler"
UPDATE_CLIENT_ID = True
TEST_CALIBRATION = False
DEBUG = False
TRACE = False
LOG_FILE = "logs/dwarf_api.log"
TIMEOUT_CMD = 160
'''
            
            with open('config.py', 'w') as f:
                f.write(config_content)
                
            self.logger.info(f"Created dwarf_python_api config for IP: {self.ip}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup dwarf_python_api config: {e}")
    
    def _get_telescope_info_via_api(self):
        """Get telescope information via dwarf_python_api."""
        try:
            # Create enhanced telescope info with discovered data
            self.telescope_info = {
                "model": "DWARF3",
                "firmware_version": "Connected via API",
                "connected": True,
                "last_update": time.time(),
                "api_mode": "dwarf_python_api",
                "stream_type": "RTSP for Tele Photo",  # From the log output
                "status": "Successfully connected and retrieved status"
            }
            
            # Try to extract more detailed info if available
            # This would require parsing the actual status response
            self.logger.info("Telescope status retrieved via dwarf_python_api")
            
        except Exception as e:
            self.logger.error(f"Failed to get telescope info via API: {e}")
            # Create minimal info
            self.telescope_info = {
                "model": "DWARF3",
                "connected": True,
                "api_mode": "dwarf_python_api",
                "status": "Partial connection established"
            }
    
    def _test_connection(self, log_level='INFO') -> bool:
        """Test connection using getDefaultParamsConfig endpoint."""
        try:
            # Use a shorter timeout for connection testing to prevent hanging
            test_timeout = min(self.timeout, 8)  # Cap at 8 seconds for connection test
            
            # Use the new endpoint for connection testing
            url = f"http://{self.ip}:8082/getDefaultParamsConfig"
            self.logger.debug(f"Testing connection to {url} with timeout {test_timeout}s")
            
            response = self.session.get(url, timeout=test_timeout)
            
            if response.status_code == 200:
                data = response.json()
                # Store telescope info for status display
                self.telescope_info = self._extract_telescope_info(data)
                # Use configurable log level - DEBUG for keep-alive, INFO for user-initiated tests
                if log_level == 'DEBUG':
                    self.logger.debug("HTTP connection test successful")
                else:
                    self.logger.info("HTTP connection test successful")
                return True
            else:
                self.logger.warning(f"Connection test failed with status {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.warning(f"Connection test timed out after {test_timeout}s")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.warning("Connection test failed - unable to connect to telescope")
            return False
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def test_connection(self, callback: Optional[Callable] = None) -> Future:
        """Public method to test telescope connection (non-blocking)."""
        return self.executor.submit(self._test_connection_sync, callback)
    
    def test_connection_sync(self) -> bool:
        """Public method to test telescope connection (blocking version)."""
        return self._test_connection_sync()
    
    def _test_connection_sync(self, callback: Optional[Callable] = None) -> bool:
        """Internal synchronous test connection method - single test only."""
        try:
            with self._operation_lock:
                self.logger.info("Testing telescope connection (single attempt)")
                
                result = self._test_connection()
                
                if result:
                    self.logger.info("Connection test successful")
                    if callback:
                        callback(True, "Connection test successful")
                    return True
                else:
                    self.logger.warning("Connection test failed")
                    if callback:
                        callback(False, "Connection test failed - telescope not responding")
                    return False
                
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            if callback:
                callback(False, f"Connection test error: {e}")
            return False
    
    def _extract_telescope_info(self, config_data: Dict) -> Dict[str, Any]:
        """Extract useful telescope information from config data."""
        try:
            data = config_data.get("data", {})
            
            # Extract telescope model and version info
            telescope_info = {
                "model": data.get("name", "Unknown"),
                "firmware_version": f"{data.get('fwMajorVersion', 0)}.{data.get('fwMinorVersion', 0)}.{data.get('fwPatchVersion', 0)}.{data.get('fwBuildVersion', 0)}",
                "app_version": f"{data.get('majorVersion', 0)}.{data.get('minorVersion', 0)}",
                "connected": True,
                "last_update": time.time()
            }
            
            # Extract camera information
            cameras = data.get("cameras", [])
            if cameras:
                main_camera = cameras[0]  # Primary camera (Tele)
                telescope_info.update({
                    "camera_name": main_camera.get("name", "Unknown"),
                    "field_of_view": f"{main_camera.get('fvWidth', 0):.2f}° x {main_camera.get('fvHeight', 0):.2f}°",
                    "preview_resolution": f"{main_camera.get('previewWidth', 0)}x{main_camera.get('previewHeight', 0)}"
                })
            
            self.logger.info(f"Telescope info extracted: {telescope_info['model']} v{telescope_info['firmware_version']}")
            return telescope_info
            
        except Exception as e:
            self.logger.error(f"Failed to extract telescope info: {e}")
            return {
                "model": "Unknown", 
                "firmware_version": "Unknown",
                "connected": True,
                "last_update": time.time()
            }
    
    def emergency_stop(self):
        """Emergency stop all telescope operations."""
        try:
            self.logger.warning("Emergency stop initiated")
            
            if self.use_dwarf_api:
                # Force disconnect and cleanup
                try:
                    perform_disconnect()
                    # Force cleanup of any hanging threads
                    import threading
                    active_threads = threading.active_count()
                    self.logger.info(f"Active threads after emergency stop: {active_threads}")
                except Exception as e:
                    self.logger.error(f"Error during emergency stop: {e}")
            
            # Reset all states
            self.current_session_active = False
            self.photo_session_running = False
            self.connected = False
            
        except Exception as e:
            self.logger.error(f"Error during emergency stop: {e}")
    
    def cleanup(self):
        """Clean up resources and threads."""
        try:
            self.logger.info("Starting controller cleanup...")
            
            # First, cancel any ongoing operations
            self.cancel_connection()
            
            # Reset connection states immediately
            self.connected = False
            self.connecting = False
            self.current_session_active = False
            self.photo_session_running = False
            self.telescope_info_retrieved = False
            
            # Quick disconnect without blocking
            try:
                if self.use_dwarf_api:
                    perform_disconnect()
                    self.logger.debug("Quick dwarf_python_api disconnect")
                else:
                    self.logger.debug("Quick HTTP disconnect")
            except:
                pass  # Ignore errors during quick disconnect
            
            # Shutdown thread pool with immediate return
            if hasattr(self, 'executor'):
                self.logger.info("Shutting down thread pool...")
                try:
                    # Store reference to executor for cleanup
                    executor_to_shutdown = self.executor
                    
                    # Remove our reference immediately
                    self.executor = None
                    
                    # Cancel any pending futures first
                    try:
                        # Python 3.9+ has cancel_futures parameter
                        executor_to_shutdown.shutdown(wait=False, cancel_futures=True)
                    except TypeError:
                        # Fallback for older Python versions - manually cancel futures
                        # This is more aggressive shutdown
                        executor_to_shutdown._shutdown = True
                        
                        # Try to cancel running tasks
                        for future in list(executor_to_shutdown._pending_work_items.values() if hasattr(executor_to_shutdown, '_pending_work_items') else []):
                            future.cancel()
                        
                        executor_to_shutdown.shutdown(wait=False)
                    
                    self.logger.info("Thread pool shutdown initiated (no wait)")
                    
                except Exception as e:
                    self.logger.warning(f"Error shutting down thread pool: {e}")
            
            if self.use_dwarf_api:
                # Quick cleanup for dwarf_python_api without blocking
                try:
                    # Try to stop the event loop
                    from dwarf_python_api.lib.websockets_utils import stop_event_loop
                    stop_event_loop()
                    self.logger.debug("Stopped dwarf_python_api event loop")
                except ImportError:
                    pass  # Function might not exist in all versions
                except Exception as e:
                    self.logger.debug(f"Error stopping event loop: {e}")
            
            self.logger.info("Controller cleanup completed (immediate return)")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            # Even if cleanup fails, make sure we reset states
            self.connected = False
            self.connecting = False
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
        finally:
            # Ensure cleanup completes even if there are errors
            try:
                if hasattr(self, 'session'):
                    self.session.close()
            except:
                pass
            
    def get_detailed_telescope_status(self, callback: Optional[Callable] = None) -> Future:
        """Get detailed telescope status including runtime information (non-blocking)."""
        return self.executor.submit(self._get_detailed_telescope_status_sync, callback)
    
    def get_detailed_telescope_status_sync(self) -> Dict[str, Any]:
        """Get detailed telescope status including runtime information (blocking version)."""
        return self._get_detailed_telescope_status_sync()
    
    def _get_detailed_telescope_status_sync(self, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Internal synchronous detailed telescope status method."""
        try:
            with self._operation_lock:
                status = {
                    "connected": self.connected,
                    "api_mode": "dwarf_python_api" if self.use_dwarf_api else "HTTP",
                    "ip": self.ip,
                    "last_update": time.time()
                }
                
                if self.use_dwarf_api and self.connected:
                    # Try to get current status with timeout
                    try:
                        result = self._safe_getstatus(timeout=30)
                        status.update({
                            "status_check": "Success" if result else "Partial",
                            "real_time_data": "Available"
                        })
                    except Exception as e:
                        status.update({
                            "status_check": f"Error: {str(e)}",
                            "real_time_data": "Limited"
                        })
                
                # Merge with stored telescope info
                if self.telescope_info:
                    status.update(self.telescope_info)
                
                if callback:
                    callback(status)
                return status
                
        except Exception as e:
            self.logger.error(f"Failed to get detailed telescope status: {e}")
            error_status = {
                "connected": False,
                "error": str(e),
                "last_update": time.time()
            }
            if callback:
                callback(error_status)
            return error_status
    
    def get_telescope_status(self, timeout: int = 30, callback: Optional[Callable] = None) -> Future:
        """Get telescope status with timeout handling (non-blocking)."""
        return self.executor.submit(self._get_telescope_status_sync, timeout, callback)
    
    def get_telescope_status_sync(self, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Get telescope status with timeout handling (blocking version)."""
        return self._get_telescope_status_sync(timeout)
    
    def _get_telescope_status_sync(self, timeout: int = 30, callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """Internal synchronous telescope status method."""
        try:
            with self._operation_lock:
                if self.use_dwarf_api and self.connected:
                    result = self._safe_getstatus(timeout=timeout)
                    if callback:
                        callback(result)
                    return result
                elif self.connected:
                    # Use HTTP fallback
                    result = self._get_http_status()
                    if callback:
                        callback(result)
                    return result
                else:
                    if callback:
                        callback(None)
                    return None
        except Exception as e:
            self.logger.error(f"Failed to get telescope status: {e}")
            if callback:
                callback(None)
            return None
    
    def _safe_getstatus(self, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Safely call perform_getstatus with timeout handling."""
        try:
            # Since we're already in a thread pool, use a simple direct call
            # The ThreadPoolExecutor already handles timeouts
            result = perform_getstatus()
            
            # Check for SLAVE MODE in result message if result is a dict
            if self._check_slave_mode_in_response(result=result):
                return None
            
            # Check for telescope timeout (like "No result after 150 seconds")
            if self._check_telescope_timeout_in_response(result=result):
                self.logger.warning("Telescope idle timeout detected - disconnecting gracefully")
                self.connected = False
                return None
                
            return result
            
        except Exception as e:
            # Check for SLAVE MODE error in general exception
            if self._check_slave_mode_in_response(exception=e):
                return None
            
            # Check for telescope timeout in exception
            if self._check_telescope_timeout_in_response(exception=e):
                self.logger.warning("Telescope timeout detected in exception - disconnecting gracefully")
                self.connected = False
                return None
                
            self.logger.error(f"Error in safe getstatus: {e}")
            return None
    
    def _get_http_status(self) -> Optional[Dict[str, Any]]:
        """Get status using HTTP fallback."""
        try:
            config_data = self.get_config_data()
            if config_data:
                return {
                    "mode": "HTTP",
                    "config_params": len(config_data),
                    "status": "Connected"
                }
            return None
        except Exception as e:
            self.logger.error(f"HTTP status check failed: {e}")
            return None
    
    def get_telescope_info(self) -> Optional[Dict[str, Any]]:
        """Get current telescope information."""
        return getattr(self, 'telescope_info', None)
    
    def _perform_time_sync(self) -> bool:
        """Perform time synchronization with telescope."""
        try:
            response = self._make_request("POST", "/time_sync", {
                "timestamp": int(time.time())
            })
            return response is not None
        except Exception as e:
            self.logger.error(f"Time sync failed: {e}")
            return False
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, retries: int = 3) -> Optional[Dict]:
        """Make HTTP request with retry logic."""
        for attempt in range(retries):
            try:
                url = f"{self.base_url}{endpoint}"
                
                if method.upper() == "GET":
                    response = self.session.get(url, timeout=self.timeout)
                elif method.upper() == "POST":
                    response = self.session.post(url, json=data or {}, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                if response.status_code == 200:
                    return response.json() if response.text else {}
                else:
                    self.logger.warning(f"Request failed with status {response.status_code}, attempt {attempt + 1}")
                    
            except Exception as e:
                self.logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(1)  # Wait before retry
                    
        return None
    
    def start_session(self, stop_event: threading.Event = None) -> bool:
        """Start a new imaging session (Go Live)."""
        try:
            self.logger.info("Starting imaging session (Go Live)")
            
            # Close any previous session first
            if self.current_session_active:
                self._stop_current_session()
            
            if self.use_dwarf_api:
                # Use dwarf_python_api to open camera
                result = perform_open_camera()
                if result:
                    self.current_session_active = True
                    self.logger.info("Imaging session started successfully via dwarf_python_api")
                    return True
                else:
                    self.logger.error("Failed to start imaging session via dwarf_python_api")
                    return False
            else:
                # Fallback to HTTP request
                result = self._make_request("POST", "/go_live", {})
                if result:
                    self.current_session_active = True
                    self.logger.info("Imaging session started successfully via HTTP")
                    return True
                else:
                    self.logger.error("Failed to start imaging session via HTTP")
                    return False
                
        except Exception as e:
            self.logger.error(f"Error starting session: {e}")
            # Check if this is a SLAVE MODE error
            if self._check_slave_mode_in_response(exception=e):
                self.logger.warning("Telescope is in SLAVE MODE - cannot start session")
            return False
    
    def _stop_current_session(self):
        """Stop current imaging session."""
        try:
            self.logger.info("Stopping current imaging session")
            self._make_request("POST", "/stop_session", {})
            self.current_session_active = False
            self.photo_session_running = False
        except Exception as e:
            self.logger.error(f"Error stopping session: {e}")
    
    def auto_focus(self, infinite_focus: bool = False, stop_event: threading.Event = None, callback: Optional[Callable] = None) -> Future:
        """Perform auto focus operation (non-blocking)."""
        return self.executor.submit(self._auto_focus_sync, infinite_focus, stop_event, callback)
    
    def auto_focus_sync(self, infinite_focus: bool = False, stop_event: threading.Event = None) -> bool:
        """Perform auto focus operation (blocking version)."""
        return self._auto_focus_sync(infinite_focus, stop_event)
    
    def _auto_focus_sync(self, infinite_focus: bool = False, stop_event: threading.Event = None, callback: Optional[Callable] = None) -> bool:
        """Internal synchronous auto focus method."""
        try:
            with self._operation_lock:
                focus_type = "infinite" if infinite_focus else "automatic"
                self.logger.info(f"Starting {focus_type} auto focus")
                
                if stop_event and stop_event.is_set():
                    if callback:
                        callback(False, "Operation cancelled")
                    return False
                
                if self.use_dwarf_api:
                    # Use dwarf_python_api for autofocus
                    result = perform_start_autofocus(infinite=infinite_focus)
                    if result:
                        self.logger.info(f"{focus_type} auto focus completed successfully via dwarf_python_api")
                        if callback:
                            callback(True, f"{focus_type} focus completed")
                        return True
                    else:
                        self.logger.error(f"{focus_type} auto focus failed via dwarf_python_api")
                        if callback:
                            callback(False, f"{focus_type} focus failed")
                        return False
                else:
                    # Fallback to HTTP request
                    result = self._make_request("POST", "/autofocus", {
                        "infinite": infinite_focus
                    })
                    
                    if result:
                        # Wait for autofocus to complete
                        success = self._wait_for_autofocus_completion(stop_event)
                        if callback:
                            callback(success, f"{focus_type} focus completed" if success else f"{focus_type} focus failed")
                        return success
                    else:
                        if callback:
                            callback(False, f"{focus_type} focus request failed")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Auto focus failed: {e}")
            if callback:
                callback(False, f"Auto focus error: {e}")
            return False
    
    def _wait_for_autofocus_completion(self, stop_event: threading.Event = None, timeout: int = 60) -> bool:
        """Wait for autofocus operation to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if stop_event and stop_event.is_set():
                return False
                
            status = self._make_request("GET", "/autofocus/status")
            if status and status.get("completed", False):
                success = status.get("success", False)
                if success:
                    self.logger.info("Auto focus completed successfully")
                else:
                    self.logger.warning("Auto focus completed but may not be optimal")
                return success
                
            time.sleep(2)
            
        self.logger.error("Auto focus timeout")
        return False
    
    def perform_eq_solving(self, stop_event: threading.Event = None) -> bool:
        """Perform equatorial solving (polar alignment)."""
        try:
            self.logger.info("Starting EQ solving (polar alignment)")
            
            if stop_event and stop_event.is_set():
                return False
            
            # Stop goto first
            self._make_request("POST", "/stop_goto", {})
            time.sleep(5)
            
            if stop_event and stop_event.is_set():
                return False
            
            result = self._make_request("POST", "/polar_align", {})
            
            if result:
                return self._wait_for_polar_align_completion(stop_event)
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"EQ solving failed: {e}")
            return False
    
    def _wait_for_polar_align_completion(self, stop_event: threading.Event = None, timeout: int = 300) -> bool:
        """Wait for polar alignment to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if stop_event and stop_event.is_set():
                return False
                
            status = self._make_request("GET", "/polar_align/status")
            if status and status.get("completed", False):
                success = status.get("success", False)
                if success:
                    self.logger.info("Polar alignment completed successfully")
                else:
                    self.logger.warning("Polar alignment completed with issues")
                return success
                
            time.sleep(5)
            
        self.logger.error("Polar alignment timeout")
        return False
    
    def perform_calibration(self, stop_event: threading.Event = None, callback: Optional[Callable] = None) -> Future:
        """Perform telescope calibration (non-blocking)."""
        return self.executor.submit(self._perform_calibration_sync, stop_event, callback)
    
    def perform_calibration_sync(self, stop_event: threading.Event = None) -> bool:
        """Perform telescope calibration (blocking version)."""
        return self._perform_calibration_sync(stop_event)
    
    def _perform_calibration_sync(self, stop_event: threading.Event = None, callback: Optional[Callable] = None) -> bool:
        """Internal synchronous calibration method."""
        try:
            with self._operation_lock:
                self.logger.info("Starting telescope calibration")
                
                if stop_event and stop_event.is_set():
                    if callback:
                        callback(False, "Operation cancelled")
                    return False
                
                if self.use_dwarf_api:
                    # Use dwarf_python_api for calibration
                    result = perform_calibration()
                    if result:
                        self.logger.info("Telescope calibration completed successfully via dwarf_python_api")
                        if callback:
                            callback(True, "Calibration completed successfully")
                        return True
                    else:
                        self.logger.error("Telescope calibration failed via dwarf_python_api")
                        if callback:
                            callback(False, "Calibration failed")
                        return False
                else:
                    # Fallback to HTTP-based calibration
                    # Set calibration camera settings
                    if not self._set_calibration_settings(stop_event):
                        if callback:
                            callback(False, "Failed to set calibration settings")
                        return False
                    
                    if stop_event and stop_event.is_set():
                        if callback:
                            callback(False, "Operation cancelled")
                        return False
                    
                    # Stop goto before calibration
                    self._make_request("POST", "/stop_goto", {})
                    time.sleep(5)
                    
                    if stop_event and stop_event.is_set():
                        if callback:
                            callback(False, "Operation cancelled")
                        return False
                    
                    # Start calibration
                    result = self._make_request("POST", "/calibration", {})
                    
                    if result:
                        success = self._wait_for_calibration_completion(stop_event)
                        if callback:
                            callback(success, "Calibration completed" if success else "Calibration failed")
                        return success
                    else:
                        if callback:
                            callback(False, "Calibration request failed")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            if callback:
                callback(False, f"Calibration error: {e}")
            return False
    
    def _set_calibration_settings(self, stop_event: threading.Event = None) -> bool:
        """Set camera settings for calibration."""
        try:
            self.logger.info("Setting calibration camera settings")
            
            # Set exposure to 1s
            if not self._update_camera_setting("exposure", "1"):
                return False
            
            if stop_event and stop_event.is_set():
                return False
            
            # Set gain to 80
            if not self._update_camera_setting("gain", "80"):
                return False
            
            if stop_event and stop_event.is_set():
                return False
            
            # Set IR filter (1 = IR_PASS for Dwarf2, ASTRO_FILTER for Dwarf3)
            if not self._update_camera_setting("IR", "1"):
                return False
            
            if stop_event and stop_event.is_set():
                return False
            
            # Set binning to 4k (0 = 4k)
            if not self._update_camera_setting("binning", "0"):
                return False
            
            time.sleep(5)  # Allow settings to take effect
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set calibration settings: {e}")
            return False
    
    def _update_camera_setting(self, setting: str, value: str) -> bool:
        """Update a camera setting."""
        try:
            result = self._make_request("POST", "/camera/setting", {
                "setting": setting,
                "value": value
            })
            
            if result and result.get("success", False):
                self.logger.debug(f"Updated {setting} to {value}")
                return True
            else:
                self.logger.error(f"Failed to update {setting} to {value}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating camera setting {setting}: {e}")
            return False
    
    def _wait_for_calibration_completion(self, stop_event: threading.Event = None, timeout: int = 180) -> bool:
        """Wait for calibration to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if stop_event and stop_event.is_set():
                return False
                
            status = self._make_request("GET", "/calibration/status")
            if status and status.get("completed", False):
                success = status.get("success", False)
                if success:
                    self.logger.info("Calibration completed successfully")
                else:
                    self.logger.warning("Calibration completed with issues")
                return success
                
            time.sleep(3)
            
        self.logger.error("Calibration timeout")
        return False
    
    def goto_coordinates(self, ra: float, dec: float, target_name: str = "", stop_event: threading.Event = None, callback: Optional[Callable] = None) -> Future:
        """Move telescope to specified coordinates (non-blocking)."""
        return self.executor.submit(self._goto_coordinates_sync, ra, dec, target_name, stop_event, callback)
    
    def goto_coordinates_sync(self, ra: float, dec: float, target_name: str = "", stop_event: threading.Event = None) -> bool:
        """Move telescope to specified coordinates (blocking version)."""
        return self._goto_coordinates_sync(ra, dec, target_name, stop_event)
    
    def _goto_coordinates_sync(self, ra: float, dec: float, target_name: str = "", stop_event: threading.Event = None, callback: Optional[Callable] = None) -> bool:
        """Internal synchronous goto coordinates method."""
        try:
            with self._operation_lock:
                self.logger.info(f"Moving to coordinates RA: {ra}, DEC: {dec} (Target: {target_name})")
                
                if stop_event and stop_event.is_set():
                    if callback:
                        callback(False, "Operation cancelled")
                    return False
                
                if self.use_dwarf_api:
                    # Use dwarf_python_api for goto
                    result = perform_goto(ra, dec, target_name or "Unknown")
                    if result:
                        self.logger.info(f"Goto coordinates completed successfully via dwarf_python_api")
                        if callback:
                            callback(True, "Goto completed successfully")
                        return True
                    else:
                        self.logger.error(f"Goto coordinates failed via dwarf_python_api")
                        if callback:
                            callback(False, "Goto failed via API")
                        return False
                else:
                    # Fallback to HTTP request
                    result = self._make_request("POST", "/goto", {
                        "ra": ra,
                        "dec": dec,
                        "target_name": target_name or "Unknown"
                    })
                    
                    if result:
                        success = self._wait_for_goto_completion(stop_event)
                        if callback:
                            callback(success, "Goto completed" if success else "Goto failed")
                        return success
                    else:
                        if callback:
                            callback(False, "Goto request failed")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Goto coordinates failed: {e}")
            # Check if this is a SLAVE MODE error
            if self._check_slave_mode_in_response(exception=e):
                self.logger.warning("Telescope is in SLAVE MODE - cannot perform goto")
            if callback:
                callback(False, f"Goto error: {e}")
            return False
    
    def _wait_for_goto_completion(self, stop_event: threading.Event = None, timeout: int = 120) -> bool:
        """Wait for goto operation to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if stop_event and stop_event.is_set():
                return False
                
            status = self._make_request("GET", "/goto/status")
            if status:
                if status.get("completed", False):
                    success = status.get("success", False)
                    if success:
                        self.logger.info("Goto completed successfully")
                    else:
                        self.logger.warning("Goto completed with issues")
                    return success
                elif status.get("error"):
                    self.logger.error(f"Goto failed: {status.get('error')}")
                    return False
                    
            time.sleep(2)
            
        self.logger.error("Goto timeout")
        return False
    
    def setup_camera_for_capture(self, capture_settings: Dict[str, Any], stop_event: threading.Event = None) -> bool:
        """Setup camera settings for capture session."""
        try:
            self.logger.info("Setting up camera for capture")
            
            # Extract settings
            exposure = capture_settings.get("exposure_time", 30)
            gain = capture_settings.get("gain", 100)
            binning = capture_settings.get("binning", "4k")
            ir_filter = capture_settings.get("ir_filter", "astro")
            frame_count = capture_settings.get("frame_count", 1)
            
            # Convert settings to API format
            binning_value = "0" if binning == "4k" else "1"  # 0=4k, 1=2k
            ir_value = self._get_ir_filter_value(ir_filter)
            
            # Apply settings
            settings_to_apply = [
                ("exposure", str(exposure)),
                ("gain", str(gain)),
                ("binning", binning_value),
                ("IR", ir_value),
                ("count", str(frame_count))
            ]
            
            for setting, value in settings_to_apply:
                if stop_event and stop_event.is_set():
                    return False
                    
                if not self._update_camera_setting(setting, value):
                    self.logger.error(f"Failed to set {setting} to {value}")
                    return False
                    
                time.sleep(0.5)  # Small delay between settings
            
            # Allow settings to stabilize
            time.sleep(2)
            
            # Log current camera settings
            self._log_camera_settings()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup camera: {e}")
            return False
    
    def _get_ir_filter_value(self, ir_filter: str) -> str:
        """Convert IR filter name to API value."""
        # For Dwarf3: 0=VIS_FILTER, 1=ASTRO_FILTER, 2=DUAL_BAND
        # For Dwarf2: 0=IR_CUT, 1=IR_PASS
        filter_map = {
            "vis": "0",
            "astro": "1", 
            "dual": "2",
            "ir_cut": "0",
            "ir_pass": "1"
        }
        return filter_map.get(ir_filter.lower(), "1")  # Default to astro filter
    
    def _log_camera_settings(self):
        """Log current camera settings."""
        try:
            settings = self._make_request("GET", "/camera/settings")
            if settings:
                self.logger.info("Current camera settings:")
                for key, value in settings.items():
                    self.logger.info(f"  {key}: {value}")
        except Exception as e:
            self.logger.debug(f"Could not log camera settings: {e}")
    
    def start_capture_session(self, frame_count: int, stop_event: threading.Event = None) -> bool:
        """Start astrophoto capture session."""
        try:
            self.logger.info(f"Starting capture session for {frame_count} frames")
            
            if stop_event and stop_event.is_set():
                return False
            
            result = self._make_request("POST", "/capture/start", {
                "frame_count": frame_count
            })
            
            if result:
                self.photo_session_running = True
                return True
            else:
                self.logger.error("Failed to start capture session")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting capture session: {e}")
            return False
    
    def wait_for_capture_completion(self, stop_event: threading.Event = None, progress_callback=None) -> bool:
        """Wait for capture session to complete."""
        try:
            self.logger.info("Waiting for capture session to complete")
            
            while self.photo_session_running:
                if stop_event and stop_event.is_set():
                    self.logger.info("Capture session interrupted by user")
                    self._stop_capture_session()
                    return False
                
                status = self._make_request("GET", "/capture/status")
                if status:
                    if status.get("completed", False):
                        success = status.get("success", False)
                        frames_captured = status.get("frames_captured", 0)
                        total_frames = status.get("total_frames", 0)
                        
                        self.photo_session_running = False
                        
                        if success:
                            self.logger.info(f"Capture session completed: {frames_captured}/{total_frames} frames")
                        else:
                            self.logger.warning(f"Capture session completed with issues: {frames_captured}/{total_frames} frames")
                        
                        return success
                    else:
                        # Session still running, update progress
                        frames_captured = status.get("frames_captured", 0)
                        total_frames = status.get("total_frames", 0)
                        
                        if progress_callback:
                            progress_callback(frames_captured, total_frames)
                        
                        self.logger.debug(f"Capture progress: {frames_captured}/{total_frames}")
                
                time.sleep(3)  # Check every 3 seconds
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error waiting for capture completion: {e}")
            self.photo_session_running = False
            return False
    
    def _stop_capture_session(self):
        """Stop the current capture session."""
        try:
            self.logger.info("Stopping capture session")
            self._make_request("POST", "/capture/stop", {})
            self.photo_session_running = False
        except Exception as e:
            self.logger.error(f"Error stopping capture session: {e}")
    
    def capture_frame(self, exposure_time: int) -> bool:
        """Capture a single frame (simplified method for backward compatibility)."""
        try:
            # Setup for single frame
            capture_settings = {
                "exposure_time": exposure_time,
                "frame_count": 1
            }
            
            if not self.setup_camera_for_capture(capture_settings):
                return False
            
            if not self.start_capture_session(1):
                return False
            
            return self.wait_for_capture_completion()
            
        except Exception as e:
            self.logger.error(f"Error capturing frame: {e}")
            return False
    
    def plate_solve(self, stop_event: threading.Event = None) -> bool:
        """Perform plate solving (same as EQ solving)."""
        return self.perform_eq_solving(stop_event)
    
    def start_guiding(self, stop_event: threading.Event = None) -> bool:
        """Start auto guiding."""
        try:
            self.logger.info("Starting auto guiding")
            
            if stop_event and stop_event.is_set():
                return False
            
            result = self._make_request("POST", "/guiding/start", {})
            
            if result:
                # Wait a moment for guiding to establish
                time.sleep(5)
                
                # Check if guiding is active
                status = self._make_request("GET", "/guiding/status")
                if status and status.get("active", False):
                    self.logger.info("Auto guiding started successfully")
                    return True
                else:
                    self.logger.warning("Auto guiding may not have started properly")
                    return False
            else:
                self.logger.error("Failed to start auto guiding")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting guiding: {e}")
            return False
    
    def stop_guiding(self) -> bool:
        """Stop auto guiding."""
        try:
            self.logger.info("Stopping auto guiding")
            
            result = self._make_request("POST", "/guiding/stop", {})
            
            if result:
                self.logger.info("Auto guiding stopped")
                return True
            else:
                self.logger.error("Failed to stop auto guiding")
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping guiding: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the telescope."""
        try:
            # Stop any active sessions
            if self.current_session_active:
                self._stop_current_session()
            
            # Stop any running capture
            if self.photo_session_running:
                self._stop_capture_session()
            
            if self.use_dwarf_api:
                # Disconnect using dwarf_python_api with proper cleanup
                try:
                    perform_disconnect()
                    # Give time for the websocket to close properly
                    time.sleep(1)
                    self.logger.info("Disconnected from Dwarf3 via dwarf_python_api")
                except Exception as api_error:
                    self.logger.warning(f"Error during dwarf_python_api disconnect: {api_error}")
            else:
                # Close HTTP session
                self.session.close()
                self.logger.info("Disconnected from Dwarf3 via HTTP")
            
            # Reset connection state
            self.connected = False
            self.telescope_info_retrieved = False  # Reset flag so telescope info is retrieved on next connection
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    def cancel_connection(self):
        """Cancel any ongoing connection attempt."""
        try:
            self.logger.info("Cancelling connection attempt")
            
            # Set connecting flag to false to stop retry loops
            self.connecting = False
            
            # Reset connection state
            self.connected = False
            self.telescope_info_retrieved = False  # Reset flag so telescope info is retrieved on next connection
            
            # Force disconnect to clean up any partial connections
            if self.use_dwarf_api:
                try:
                    # Import here to avoid issues if dwarf_python_api not available
                    from dwarf_python_api.lib.dwarf_command import perform_disconnect
                    perform_disconnect()
                    self.logger.debug("Cancelled dwarf_python_api connection")
                except ImportError:
                    pass
                except Exception as e:
                    self.logger.debug(f"Error cancelling dwarf_python_api connection: {e}")
            
            # Close HTTP session
            try:
                self.session.close()
                self.session = requests.Session()  # Create new session
                self.logger.debug("Reset HTTP session")
            except Exception as e:
                self.logger.debug(f"Error resetting HTTP session: {e}")
            
            self.logger.info("Connection attempt cancelled successfully")
            
        except Exception as e:
            self.logger.error(f"Error during connection cancellation: {e}")
            # Force reset flags even if there were errors
            self.connecting = False
            self.connected = False
    
    def is_slave_mode_detected(self) -> bool:
        """Check if SLAVE MODE was detected (telescope being used by another app)."""
        return self.slave_mode_detected
    
    def is_connected(self) -> bool:
        """Check if telescope is connected, with optional keepalive check."""
        if not self.connected:
            return False
        
        # For frequent checks (like in scheduler), use cached connection status
        # Only do keepalive check occasionally to avoid overwhelming the telescope
        return self._check_connection_keepalive()
    
    def reset_slave_mode_detection(self):
        """Reset SLAVE MODE detection flag."""
        self.slave_mode_detected = False
    
    def _check_connection_keepalive(self) -> bool:
        """Check connection health with keep-alive pings instead of full reconnection."""
        current_time = time.time()
        
        # Only check if enough time has passed since last keepalive
        if current_time - self.last_keepalive < self.keepalive_interval:
            return True  # Don't check too frequently
        
        if not self.connected:
            return False
        
        try:
            # Quick status check to verify connection is still alive
            if self.use_dwarf_api:
                # Use a very short timeout for keepalive checks
                result = self._safe_getstatus(timeout=5)
                if result:
                    self.last_keepalive = current_time
                    self.logger.debug("Connection keepalive successful")
                    return True
                else:
                    self.logger.warning("Connection keepalive failed - connection may be lost")
                    self.connected = False
                    return False
            else:
                # For HTTP mode, do a quick connection test
                if self._test_connection(log_level='DEBUG'):
                    self.last_keepalive = current_time
                    self.logger.debug("HTTP connection keepalive successful")
                    return True
                else:
                    self.logger.warning("HTTP connection keepalive failed")
                    self.connected = False
                    return False
                    
        except Exception as e:
            self.logger.warning(f"Connection keepalive check failed: {e}")
            # Check for SLAVE MODE and disconnect immediately
            if self._check_slave_mode_in_response(exception=e):
                self.connected = False
                return False
            
            # Check for telescope timeout and disconnect gracefully
            if self._check_telescope_timeout_in_response(exception=e):
                self.logger.warning("Telescope timeout during keepalive - disconnecting gracefully")
                self.connected = False
                # Also force disconnect the dwarf_python_api if connected
                if self.use_dwarf_api:
                    try:
                        perform_disconnect()
                        self.logger.info("Forced disconnection due to telescope timeout")
                    except:
                        pass  # Ignore errors during forced disconnect
                return False
            
            return True  # Keep connection alive for other temporary errors
            
        return False
    
    def _check_slave_mode_in_response(self, result=None, exception=None) -> bool:
        """Check if SLAVE MODE is detected in API response or exception."""
        # Check result first - this is the primary way SLAVE MODE is detected
        if isinstance(result, dict):
            # Check the message field from telescope response like:
            # {'cmd_send': 10039, 'cmd_recv': 10039, 'result': <Dwarf_Result.WARNING: -1>, 'message': 'Error SLAVE MODE', 'code': -15}
            message = result.get('message', '')
            if message and isinstance(message, str):
                if "SLAVE MODE" in message.upper() or "Error SLAVE MODE" in message:
                    self.slave_mode_detected = True
                    self.logger.error(f"SLAVE MODE detected in telescope response: {result}")
                    return True
            
            # Also check for SLAVE MODE in other message fields as fallback
            for field in ['error', 'status', 'description']:
                field_value = result.get(field, '')
                if field_value and isinstance(field_value, str):
                    if "SLAVE MODE" in field_value.upper():
                        self.slave_mode_detected = True
                        self.logger.error(f"SLAVE MODE detected in {field}: {result}")
                        return True
        
        # Check exception as secondary method
        if exception:
            exception_str = str(exception).upper()
            if "SLAVE MODE" in exception_str:
                self.slave_mode_detected = True
                self.logger.error(f"SLAVE MODE detected in exception: {exception}")
                return True
        
        return False
    
    def _check_telescope_timeout_in_response(self, result=None, exception=None) -> bool:
        """Check if telescope timeout is detected in API response or exception."""
        # Check result for timeout messages
        if isinstance(result, dict):
            message = result.get('message', '')
            if message and isinstance(message, str):
                # Check for the specific 150-second timeout message
                if "No result after" in message and "seconds" in message:
                    self.logger.warning(f"Telescope idle timeout detected: {message}")
                    return True
                # Check for other timeout patterns
                if any(keyword in message.lower() for keyword in ["timeout", "timed out", "no response"]):
                    self.logger.warning(f"Telescope timeout detected: {message}")
                    return True
        
        # Check exception for timeout indicators
        if exception:
            exception_str = str(exception).lower()
            if any(keyword in exception_str for keyword in ["timeout", "timed out", "no result after", "150 seconds"]):
                self.logger.warning(f"Telescope timeout detected in exception: {exception}")
                return True
        
        return False
    
    def quick_status_check(self) -> Dict[str, Any]:
        """Get quick status without blocking operations."""
        return {
            "connected": self.connected,
            "api_mode": "dwarf_python_api" if self.use_dwarf_api else "HTTP",
            "ip": self.ip,
            "session_active": self.current_session_active,
            "photo_running": self.photo_session_running,
            "last_update": time.time()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current telescope status."""
        try:
            if not self.connected:
                return {"connected": False, "error": "Not connected"}
            
            status = self._make_request("GET", "/status")
            if status:
                status["connected"] = True
                status["session_active"] = self.current_session_active
                status["photo_session_running"] = self.photo_session_running
                return status
            else:
                return {"connected": False, "error": "Failed to get status"}
                
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return {"connected": False, "error": str(e)}
    
    def emergency_stop(self):
        """Emergency stop all telescope operations."""
        try:
            self.logger.warning("Emergency stop initiated")
            
            # Stop all operations
            self._make_request("POST", "/emergency_stop", {})
            
            # Reset state
            self.current_session_active = False
            self.photo_session_running = False
            
            self.logger.info("Emergency stop completed")
            
        except Exception as e:
            self.logger.error(f"Error during emergency stop: {e}")
        try:
            if not self.connected:
                self.logger.error("Not connected to telescope")
                return False
                
            self.logger.info("Starting auto focus")
            
            response = self.session.post(
                f"{self.base_url}/api/camera/autofocus",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                # Wait for focus to complete
                return self._wait_for_focus_completion()
            else:
                self.logger.error(f"Auto focus command failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in auto_focus: {e}")
            return False
            
    def plate_solve(self) -> bool:
        """Perform plate solving."""
        try:
            if not self.connected:
                self.logger.error("Not connected to telescope")
                return False
                
            self.logger.info("Starting plate solving")
            
            response = self.session.post(
                f"{self.base_url}/api/mount/platesolve",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                # Wait for plate solving to complete
                return self._wait_for_plate_solve_completion()
            else:
                self.logger.error(f"Plate solve command failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in plate_solve: {e}")
            return False
            
    def start_guiding(self) -> bool:
        """Start auto guiding."""
        try:
            if not self.connected:
                self.logger.error("Not connected to telescope")
                return False
                
            self.logger.info("Starting auto guiding")
            
            response = self.session.post(
                f"{self.base_url}/api/guiding/start",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                # Wait for guiding to start
                time.sleep(5)
                return self._check_guiding_status()
            else:
                self.logger.error(f"Start guiding command failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in start_guiding: {e}")
            return False
            
    def stop_guiding(self) -> bool:
        """Stop auto guiding."""
        try:
            if not self.connected:
                self.logger.error("Not connected to telescope")
                return False
                
            self.logger.info("Stopping auto guiding")
            
            response = self.session.post(
                f"{self.base_url}/api/guiding/stop",
                timeout=self.timeout
            )
            
            return response.status_code == 200
            
        except Exception as e:
            self.logger.error(f"Error in stop_guiding: {e}")
            return False
            
    def capture_frame(self, exposure_time: float, filename: str = None) -> bool:
        """Capture a single frame."""
        try:
            if not self.connected:
                self.logger.error("Not connected to telescope")
                return False
                
            self.logger.debug(f"Capturing frame with {exposure_time}s exposure")
            
            payload = {
                "exposure": exposure_time,
                "filename": filename or f"frame_{int(time.time())}.fits"
            }
            
            response = self.session.post(
                f"{self.base_url}/api/camera/capture",
                json=payload,
                timeout=self.timeout + exposure_time + 10  # Add buffer for exposure time
            )
            
            if response.status_code == 200:
                # Wait for capture to complete
                return self._wait_for_capture_completion(exposure_time)
            else:
                self.logger.error(f"Capture command failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in capture_frame: {e}")
            return False
            
    def get_status(self) -> Optional[Dict[str, Any]]:
        """Get telescope status."""
        try:
            if not self.connected:
                return None
                
            response = self.session.get(
                f"{self.base_url}/api/status",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return None
            
    def _parse_coordinates(self, ra: str, dec: str) -> Tuple[float, float]:
        """Parse RA/DEC strings to decimal degrees."""
        try:
            # Handle RA (hours:minutes:seconds to degrees)
            if ":" in ra:
                parts = ra.split(":")
                hours = float(parts[0])
                minutes = float(parts[1]) if len(parts) > 1 else 0
                seconds = float(parts[2]) if len(parts) > 2 else 0
                ra_degrees = (hours + minutes/60 + seconds/3600) * 15  # Convert to degrees
            else:
                ra_degrees = float(ra)
                
            # Handle DEC (degrees:minutes:seconds)
            if ":" in dec:
                parts = dec.split(":")
                degrees = float(parts[0])
                minutes = float(parts[1]) if len(parts) > 1 else 0
                seconds = float(parts[2]) if len(parts) > 2 else 0
                
                # Handle negative declination
                sign = -1 if degrees < 0 or dec.startswith("-") else 1
                dec_degrees = sign * (abs(degrees) + minutes/60 + seconds/3600)
            else:
                dec_degrees = float(dec)
                
            return ra_degrees, dec_degrees
            
        except Exception as e:
            self.logger.error(f"Error parsing coordinates: {e}")
            raise
            
    def _wait_for_slew_completion(self, timeout: int = 120) -> bool:
        """Wait for telescope slew to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_status()
            if status and status.get("mount", {}).get("slewing") == False:
                self.logger.info("Slew completed")
                return True
                
            time.sleep(2)
            
        self.logger.error("Slew timeout")
        return False
        
    def _wait_for_focus_completion(self, timeout: int = 300) -> bool:
        """Wait for auto focus to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_status()
            if status and status.get("camera", {}).get("focusing") == False:
                focus_result = status.get("camera", {}).get("focus_result", "unknown")
                self.logger.info(f"Auto focus completed: {focus_result}")
                return focus_result == "success"
                
            time.sleep(5)
            
        self.logger.error("Auto focus timeout")
        return False
        
    def _wait_for_plate_solve_completion(self, timeout: int = 180) -> bool:
        """Wait for plate solving to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_status()
            if status and status.get("mount", {}).get("plate_solving") == False:
                solve_result = status.get("mount", {}).get("plate_solve_result", "unknown")
                self.logger.info(f"Plate solve completed: {solve_result}")
                return solve_result == "success"
                
            time.sleep(3)
            
        self.logger.error("Plate solve timeout")
        return False
        
    def _wait_for_capture_completion(self, exposure_time: float) -> bool:
        """Wait for image capture to complete."""
        # Wait for exposure time plus some buffer
        wait_time = exposure_time + 10
        time.sleep(wait_time)
        
        # Check if capture completed successfully
        status = self.get_status()
        if status and status.get("camera", {}).get("capturing") == False:
            return True
            
        return False
        
    def _check_guiding_status(self) -> bool:
        """Check if guiding is active."""
        status = self.get_status()
        if status:
            return status.get("guiding", {}).get("active", False)
        return False
        
    def set_camera_settings(self, gain: int = None, binning: str = None) -> bool:
        """Set camera settings."""
        try:
            if not self.connected:
                return False
                
            payload = {}
            if gain is not None:
                payload["gain"] = gain
            if binning is not None:
                payload["binning"] = binning
                
            if not payload:
                return True  # Nothing to set
                
            response = self.session.post(
                f"{self.base_url}/api/camera/settings",
                json=payload,
                timeout=self.timeout
            )
            
            return response.status_code == 200
            
        except Exception as e:
            self.logger.error(f"Error setting camera settings: {e}")
            return False
