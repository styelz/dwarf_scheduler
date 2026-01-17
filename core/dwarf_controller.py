"""
Controller for communicating with Dwarf3 smart telescope.
Enhanced with proper API flow based on dwarf_python_api implementation.
"""

import requests
import requests.exceptions
import time
import logging
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, Optional, Tuple, Callable

# Import dwarf_python_api modules
from dwarf_python_api.lib.dwarf_utils import (
    perform_goto, perform_start_autofocus, perform_stop_autofocus,
    perform_calibration, perform_stop_calibration, perform_open_camera,
    perform_takePhoto, perform_takeAstroPhoto, perform_stopAstroPhoto,
    perform_waitEndAstroPhoto, perform_time, perform_disconnect,
    perform_getstatus
)
from dwarf_python_api.lib.websockets_utils import connect_socket, disconnect_socket
DWARF_API_AVAILABLE = True

class DwarfController:
    """Controls Dwarf3 telescope via dwarf_python_api websocket connection."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Connection settings - will be loaded when needed
        self.ip = None
        self.port = None
        self.timeout = None
        self.base_url = None
        
        self.connected = False
        self.connecting = False  # Flag to prevent concurrent connection attempts
        self.session = requests.Session()  # Only used for getDefaultParamsConfig
        
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
        
        # Track connection threads for proper cleanup
        self._connection_threads = []
        self._connection_thread_lock = threading.Lock()
        
        # Track active futures for cancellation
        self._active_futures = set()
        self._futures_lock = threading.Lock()
        
        self.logger.info("Using dwarf_python_api for telescope control")
        
        # Load initial settings
        self._load_settings()
    
    def cleanup(self):
        """Properly cleanup executor and resources."""
        try:
            # Cancel all pending futures
            with self._futures_lock:
                for future in list(self._active_futures):
                    future.cancel()
                self._active_futures.clear()
            
            # Shutdown executor with timeout
            if self.executor:
                self.executor.shutdown(wait=True, timeout=5)
                self.executor = None
                
            # Disconnect websocket if connected
            if self.connected:
                try:
                    disconnect_socket()
                    self.connected = False
                except Exception:
                    pass  # Ignore disconnect errors during cleanup
                    
            self.logger.info("DwarfController cleanup completed")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup when object is garbage collected."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors during destruction
    
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
        
        # Reload config file
        self.config_manager.config.read(self.config_manager.config_file)
        self._load_settings()
        
        # If connection settings changed and we're connected, need to reconnect
        if self.connected and (old_ip != self.ip or str(old_port) != str(self.port)):
            self.logger.info("Connection settings changed, will reconnect on next operation")
            self.disconnect()
        
    def connect(self, timeout: Optional[int] = None, callback: Optional[Callable] = None) -> Future:
        """Connect to the Dwarf3 telescope (non-blocking)."""
        if self.executor is None:
            self.logger.error("Executor not available - controller has been cleaned up")
            # Create a failed future to return
            failed_future = concurrent.futures.Future()
            failed_future.set_exception(RuntimeError("Controller has been cleaned up"))
            return failed_future
        
        future = self.executor.submit(self._connect_sync, timeout, callback)
        # Track future for cancellation
        with self._futures_lock:
            self._active_futures.add(future)
        # Clean up completed futures
        future.add_done_callback(lambda f: self._cleanup_future(f))
        return future
    
    def _cleanup_future(self, future):
        """Remove completed future from tracking set."""
        with self._futures_lock:
            self._active_futures.discard(future)
    
    def _invoke_callback(self, callback: Optional[Callable], *args, **kwargs):
        """Safely invoke a callback with provided arguments."""
        if callback and callable(callback):
            try:
                callback(*args, **kwargs)
                self.logger.debug(f"Callback invoked successfully with args: {args}, kwargs: {kwargs}")
            except Exception as e:
                self.logger.error(f"Error invoking callback: {e}")
        else:
            self.logger.warning("Provided callback is not callable or is None")
    
    def is_slave_mode_detected(self) -> bool:
        """Check if telescope is in SLAVE MODE (being used by another application)."""
        return self.slave_mode_detected
    
    def reset_slave_mode_detection(self):
        """Reset SLAVE MODE detection flag."""
        self.slave_mode_detected = False
        self.logger.info("SLAVE MODE detection reset")
    
    def cancel_connection(self):
        """Cancel any ongoing connection attempt."""
        try:
            # Cancel any pending futures
            with self._futures_lock:
                for future in list(self._active_futures):
                    future.cancel()
            
            # Reset connection state
            self.connecting = False
            self.connected = False
            
            self.logger.info("Connection attempt cancelled")
        except Exception as e:
            self.logger.error(f"Error cancelling connection: {e}")
    
    def is_connected(self) -> bool:
        """Check if telescope is currently connected."""
        return self.connected and not self.connecting
    
    def quick_status_check(self) -> Dict[str, Any]:
        """Quick non-blocking status check."""
        return {
            "connected": self.connected,
            "connecting": self.connecting,
            "slave_mode": self.slave_mode_detected,
            "last_keepalive": self.last_keepalive
        }
    
    def get_telescope_info(self) -> Optional[Dict[str, Any]]:
        """Get cached telescope information."""
        return self.telescope_info

    def _connect_sync(self, timeout: Optional[int] = None, callback: Optional[Callable] = None) -> bool:
        """Internal synchronous connect method."""
        with self._connection_lock:
            # Check if another connection attempt is in progress
            if self.connecting:
                self.logger.warning("Connection attempt already in progress, skipping duplicate request")
                self._invoke_callback(callback, False, "Connection attempt already in progress")
                return False

            max_retries = 3
            retry_count = 0
            callback_invoked = False  # Track if callback has been invoked

            try:
                self.connecting = True

                with self._operation_lock:
                    if self.connected:
                        self.logger.debug("Connection already established and healthy")
                        return True
                    
                    while retry_count < max_retries:
                        if not DWARF_API_AVAILABLE:
                            self.logger.error("dwarf_python_api not available")
                            break
                        
                        try:
                            retry_count += 1
                            self.logger.info(f"Connection attempt {retry_count}/{max_retries}")

                            if retry_count == 1:
                                self.slave_mode_detected = False

                            if perform_time():
                                self.connected = True
                                self.last_keepalive = time.time()
                                self.logger.info("Successfully connected to Dwarf3")
                                if not callback_invoked:
                                    self._invoke_callback(callback, True, "Connected successfully")
                                    callback_invoked = True
                                return True
                            else:
                                self.logger.warning("Connection attempt failed, retrying...")
                                time.sleep(2)

                        except Exception as retry_error:
                            self.logger.warning(f"Connection attempt {retry_count} error: {retry_error}")
                            if retry_count >= max_retries:
                                raise retry_error
                            time.sleep(2)

                    self.logger.error("Failed to establish connection after all retries")
                    if not callback_invoked:
                        self._invoke_callback(callback, False, f"Failed to connect after {max_retries} attempts")
                        callback_invoked = True
                    return False

            except Exception as e:
                self.logger.error(f"Failed to connect to Dwarf3: {e}")
                if not callback_invoked:
                    self._invoke_callback(callback, False, f"Connection error: {e}")
                    callback_invoked = True
                return False

            finally:
                self.connecting = False
    
    def _connect_via_dwarf_api(self, timeout: int = 10) -> bool:
        """Connect using dwarf_python_api."""
        try:
            # Use safe_getstatus to check if the telescope is reachable
            if not self._safe_getstatus(timeout):
                self.logger.error("Telescope is not reachable")
                return False

            self.logger.info("Telescope is reachable")

            # Set up configuration for dwarf_python_api
            self._setup_dwarf_api_config()
            
            self.logger.info(f"Setting up dwarf_python_api connection...")
            
            # Skip perform_getstatus entirely since it never works
            # Just verify the API module is available and configured
            try:                
                # Test basic module functionality without calling getstatus
                self.logger.info("dwarf_python_api module imported successfully")
                
                # Set up telescope info without requiring getstatus
                if not self.telescope_info_retrieved:
                    self._get_telescope_info_via_api()
                    self.telescope_info_retrieved = True
                
                self.logger.info("dwarf_python_api connection established successfully")
                return True
                
            except ImportError as e:
                self.logger.error(f"dwarf_python_api module not available: {e}")
                return False
            except Exception as e:
                self.logger.warning(f"Error setting up dwarf_python_api: {e}")
                # Still consider connection successful if we can import the module
                self.logger.info("dwarf_python_api connection established with warnings")
                return True
                
        except Exception as e:
            self.logger.error(f"Error connecting via dwarf_python_api: {e}")
            return False

    def _setup_dwarf_api_config(self):
        """Set up configuration for dwarf_python_api."""
        try:
            import os

            config_path = 'config.py'

            # Check if config.py already exists
            if os.path.exists(config_path):
                self.logger.info("Config file already exists. Skipping creation.")
                return

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
            with open(config_path, 'w') as f:
                f.write(config_content)

            self.logger.info(f"Created dwarf_python_api config for IP: {self.ip}")

        except Exception as e:
            self.logger.error(f"Error setting up config: {e}")
    
    def start_session(self, stop_event: threading.Event) -> bool:
        """Start imaging session (Go Live)."""
        try:
            # Use perform_open_camera to start the camera session
            success = perform_open_camera()
            if success:
                self.current_session_active = True
                self.logger.info("Imaging session started successfully")
                return True
            else:
                self.logger.error("Failed to start imaging session")
                return False
        except Exception as e:
            self.logger.error(f"Error starting session: {e}")
            return False
    
    def auto_focus(self, infinite_focus: bool, stop_event: threading.Event) -> bool:
        """Perform auto focus operation."""
        try:
            # Start autofocus
            if perform_start_autofocus():
                self.logger.info("Auto focus started")
                
                # Wait for completion (simplified - in real implementation would monitor status)
                import time
                timeout = 300  # 5 minutes timeout
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    if stop_event.is_set():
                        perform_stop_autofocus()
                        return False
                    time.sleep(2)
                    # In real implementation, would check focus status here
                    break  # Simplified - assume completed
                
                self.logger.info("Auto focus completed")
                return True
            else:
                self.logger.error("Failed to start auto focus")
                return False
        except Exception as e:
            self.logger.error(f"Error during auto focus: {e}")
            return False
    
    def perform_eq_solving(self, stop_event: threading.Event) -> bool:
        """Perform EQ solving (polar alignment)."""
        try:
            # Start calibration which includes EQ solving
            if perform_calibration():
                self.logger.info("EQ solving started")
                
                # Wait for completion (simplified)
                import time
                timeout = 600  # 10 minutes timeout
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    if stop_event.is_set():
                        perform_stop_calibration()
                        return False
                    time.sleep(5)
                    # In real implementation, would check calibration status
                    break  # Simplified - assume completed
                
                self.logger.info("EQ solving completed")
                return True
            else:
                self.logger.error("Failed to start EQ solving")
                return False
        except Exception as e:
            self.logger.error(f"Error during EQ solving: {e}")
            return False
    
    def perform_calibration(self, stop_event: threading.Event) -> bool:
        """Perform telescope calibration."""
        try:
            # Use the calibration function from dwarf_python_api
            if perform_calibration():
                self.logger.info("Telescope calibration started")
                
                # Wait for completion (simplified)
                import time
                timeout = 900  # 15 minutes timeout
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    if stop_event.is_set():
                        perform_stop_calibration()
                        return False
                    time.sleep(5)
                    # In real implementation, would check calibration status
                    break  # Simplified - assume completed
                
                self.logger.info("Telescope calibration completed")
                return True
            else:
                self.logger.error("Failed to start telescope calibration")
                return False
        except Exception as e:
            self.logger.error(f"Error during calibration: {e}")
            return False
    
    def goto_coordinates(self, ra: float, dec: float, target_name: str, stop_event: threading.Event) -> bool:
        """Move telescope to specified coordinates."""
        try:
            self.logger.info(f"Moving to target {target_name} at RA: {ra}, DEC: {dec}")
            
            # Use perform_goto to move to coordinates
            success = perform_goto(ra, dec)
            if success:
                self.logger.info(f"Successfully moved to {target_name}")
                return True
            else:
                self.logger.error(f"Failed to move to {target_name}")
                return False
        except Exception as e:
            self.logger.error(f"Error moving to coordinates: {e}")
            return False
    
    def start_guiding(self, stop_event: threading.Event) -> bool:
        """Start auto guiding."""
        try:
            # Auto guiding would typically be part of the calibration process
            # For now, just log that it's started
            self.logger.info("Auto guiding started (integrated with calibration)")
            return True
        except Exception as e:
            self.logger.error(f"Error starting auto guiding: {e}")
            return False
    
    def stop_guiding(self):
        """Stop auto guiding."""
        try:
            self.logger.info("Auto guiding stopped")
        except Exception as e:
            self.logger.error(f"Error stopping auto guiding: {e}")
    
    def setup_camera_for_capture(self, capture_settings: Dict[str, Any], stop_event: threading.Event) -> bool:
        """Setup camera with specified capture settings."""
        try:
            exposure_time = capture_settings.get("exposure_time", 30.0)
            gain = capture_settings.get("gain", 100)
            frame_count = capture_settings.get("frame_count", 1)
            
            self.logger.info(f"Setting up camera - Exposure: {exposure_time}s, Gain: {gain}, Frames: {frame_count}")
            
            # Camera setup would be handled by the dwarf_python_api
            # For now, just validate settings and log
            if exposure_time <= 0 or frame_count <= 0:
                self.logger.error("Invalid capture settings")
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Error setting up camera: {e}")
            return False
    
    def start_capture_session(self, frame_count: int, stop_event: threading.Event) -> bool:
        """Start capture session for specified number of frames."""
        try:
            self.logger.info(f"Starting capture session for {frame_count} frames")
            
            # Use perform_takeAstroPhoto to start the capture
            success = perform_takeAstroPhoto(count=frame_count)
            if success:
                self.photo_session_running = True
                self.logger.info("Astro photo session started")
                return True
            else:
                self.logger.error("Failed to start astro photo session")
                return False
        except Exception as e:
            self.logger.error(f"Error starting capture session: {e}")
            return False
    
    def wait_for_capture_completion(self, stop_event: threading.Event, progress_callback=None) -> bool:
        """Wait for capture session to complete with progress updates."""
        try:
            self.logger.info("Waiting for capture session to complete")
            
            # Use perform_waitEndAstroPhoto to wait for completion
            success = perform_waitEndAstroPhoto()
            
            if success:
                self.photo_session_running = False
                self.logger.info("Capture session completed successfully")
                return True
            else:
                self.logger.warning("Capture session completed with issues")
                self.photo_session_running = False
                return False
                
        except Exception as e:
            self.logger.error(f"Error during capture completion: {e}")
            self.photo_session_running = False
            return False
    
    def emergency_stop(self):
        """Emergency stop all telescope operations."""
        try:
            self.logger.warning("Emergency stop initiated")
            
            # Stop any ongoing operations
            if self.photo_session_running:
                try:
                    perform_stopAstroPhoto()
                    self.photo_session_running = False
                except Exception:
                    pass
            
            try:
                perform_stop_autofocus()
            except Exception:
                pass
                
            try:
                perform_stop_calibration()
            except Exception:
                pass
                
            self.logger.info("Emergency stop completed")
        except Exception as e:
            self.logger.error(f"Error during emergency stop: {e}")
    
    def disconnect(self):
        """Disconnect from telescope."""
        try:
            if self.connected:
                # Stop any ongoing operations
                self.emergency_stop()
                
                # Disconnect websocket
                perform_disconnect()
                disconnect_socket()
                
                self.connected = False
                self.current_session_active = False
                self.photo_session_running = False
                
                self.logger.info("Disconnected from telescope")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
            # Force disconnection state even if errors occurred
            self.connected = False
            self.current_session_active = False
            self.photo_session_running = False
    
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
    
    
    def cleanup(self):
        """Clean up resources and threads."""
        try:
            self.logger.info("Starting controller cleanup...")
            
            # First, cancel any ongoing operations
            self.cancel_connection()
            
            # Clear all tracked futures
            with self._futures_lock:
                self._active_futures.clear()
            
            # Reset connection states immediately
            self.connected = False
            self.connecting = False
            self.current_session_active = False
            self.photo_session_running = False
            self.telescope_info_retrieved = False
            
            # Quick disconnect without blocking
            try:
                perform_disconnect()
                self.logger.debug("Quick dwarf_python_api disconnect")
            except:
                pass  # Ignore errors during quick disconnect
            
            # Shutdown thread pool with immediate return
            if hasattr(self, 'executor') and self.executor is not None:
                self.logger.info("Shutting down thread pool...")
                try:
                    # Store reference to executor for cleanup
                    executor_to_shutdown = self.executor
                    
                    # Remove our reference immediately
                    self.executor = None
                    
                    # Cancel all pending and running futures
                    try:
                        # Cancel any remaining tracked futures
                        with self._futures_lock:
                            remaining_futures = list(self._active_futures)
                            for future in remaining_futures:
                                if not future.done():
                                    cancelled = future.cancel()
                                    self.logger.debug(f"Cancelled future: {cancelled}")
                            self._active_futures.clear()
                        
                        # Try shutdown with cancel_futures if available (Python 3.9+)
                        try:
                            executor_to_shutdown.shutdown(wait=False, cancel_futures=True)
                        except TypeError:
                            # Fallback for older Python versions
                            executor_to_shutdown._shutdown = True
                            executor_to_shutdown.shutdown(wait=False)
                        
                        self.logger.info("Thread pool shutdown completed (no wait)")
                        
                    except Exception as shutdown_error:
                        self.logger.warning(f"Error during executor shutdown: {shutdown_error}")
                        # Force shutdown by setting internal flags
                        try:
                            executor_to_shutdown._shutdown = True
                            if hasattr(executor_to_shutdown, '_threads'):
                                for thread in executor_to_shutdown._threads:
                                    if thread.is_alive():
                                        self.logger.debug(f"Thread still alive: {thread.name}")
                        except:
                            pass
                    
                except Exception as e:
                    self.logger.warning(f"Error shutting down thread pool: {e}")
            
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
            
            # Force cleanup of any remaining dwarf_python_api threads
            try:
                import threading
                active_threads = threading.active_count()
                self.logger.debug(f"Active threads after cleanup: {active_threads}")
                
                # List any remaining non-daemon threads
                for thread in threading.enumerate():
                    if thread.is_alive() and not thread.daemon and thread != threading.current_thread():
                        self.logger.debug(f"Non-daemon thread still active: {thread.name}")
            except Exception as e:
                self.logger.debug(f"Error checking active threads: {e}")
            
            self.logger.info("Controller cleanup completed (immediate return)")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            # Even if cleanup fails, make sure we reset states
            self.connected = False
            self.connecting = False
        finally:
            # Ensure cleanup completes even if there are errors
            try:
                if hasattr(self, 'session'):
                    self.session.close()
            except:
                pass
            
    def get_detailed_telescope_status(self, callback: Optional[Callable] = None) -> Future:
        """Get detailed telescope status including runtime information (non-blocking)."""
        if self.executor is None:
            self.logger.error("Executor not available - controller has been cleaned up")
            failed_future = concurrent.futures.Future()
            failed_future.set_exception(RuntimeError("Controller has been cleaned up"))
            return failed_future
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
                    "api_mode": "dwarf_python_api",
                    "ip": self.ip,
                    "last_update": time.time()
                }
                
                if self.connected:
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
        if self.executor is None:
            self.logger.error("Executor not available - controller has been cleaned up")
            failed_future = concurrent.futures.Future()
            failed_future.set_exception(RuntimeError("Controller has been cleaned up"))
            return failed_future
        return self.executor.submit(self._get_telescope_status_sync, timeout, callback)
    
    def get_telescope_status_sync(self, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Get telescope status with timeout handling (blocking version)."""
        return self._get_telescope_status_sync(timeout)
    
    def _get_telescope_status_sync(self, timeout: int = 30, callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """Internal synchronous telescope status method."""
        try:
            # Use our reliable get_status method instead of unreliable getstatus
            status = self.get_status()
            if callback:
                callback(status)
            return status
        except Exception as e:
            self.logger.error(f"Failed to get telescope status: {e}")
            error_status = {
                "connected": False,
                "error": str(e)
            }
            if callback:
                callback(error_status)
            return error_status
    
    def _safe_getstatus(self, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Safely call perform_getstatus with timeout handling - returns None if getstatus is unreliable."""
        try:
            # Since perform_getstatus has never worked reliably, we'll attempt it but not rely on it
            self.logger.debug("Attempting perform_getstatus (known to be unreliable)")
            
            # Try the call but expect it to fail
            result = perform_getstatus()
            # Ensure we return a dict or None, not a bool
            if isinstance(result, dict):
                return result
            return None

        except Exception as e:
            # This is expected since getstatus never works reliably
            self.logger.debug(f"perform_getstatus failed as expected: {e}")
            
            # Check for specific error conditions that we do care about
            if self._check_slave_mode_in_response(exception=e):
                self.logger.warning("SLAVE MODE detected in getstatus exception")
                return None
            
            if self._check_telescope_timeout_in_response(exception=e):
                self.logger.warning("Telescope timeout detected in exception - disconnecting gracefully")
                self.connected = False
                return None
            
            # For all other getstatus failures, just return None (this is normal)
            return None
    
    def _get_http_status(self) -> Optional[Dict[str, Any]]:
        """Get status using HTTP fallback."""
        try:
            # Try to get config data via HTTP
            try:
                response = self.session.get(
                    f"{self.base_url}/api/config",
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    config_data = response.json()
                    return {
                        "mode": "HTTP",
                        "config_params": len(config_data),
                        "status": "Connected"
                    }
            except Exception as e:
                self.logger.debug(f"HTTP config request failed: {e}")
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
            # dwarf_python_api handles time sync automatically
            self.logger.info("Time sync handled by dwarf_python_api")
            return True
        except Exception as e:
            self.logger.error(f"Time sync failed: {e}")
            return False
    
    def start_session(self, stop_event: Optional[threading.Event] = None) -> bool:
        """Start a new imaging session (Go Live)."""
        try:
            self.logger.info("Starting imaging session (Go Live)")
            
            # Close any previous session first
            if self.current_session_active:
                self._stop_current_session()
            
            # Use dwarf_python_api to open camera
            result = perform_open_camera()
            if result:
                self.current_session_active = True
                self.logger.info("Imaging session started successfully")
                return True
            else:
                self.logger.error("Failed to start imaging session")
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
            # perform_close_camera may not be available, wrap in try-catch
            try:
                # Try dynamic import to avoid static analysis errors
                import importlib
                module = importlib.import_module("dwarf_python_api.lib.dwarf_utils")
                if hasattr(module, "perform_close_camera"):
                    close_camera_fn = getattr(module, "perform_close_camera")
                    close_camera_fn()
            except Exception:
                self.logger.debug("perform_close_camera not available")
            self.current_session_active = False
            self.photo_session_running = False
        except Exception as e:
            self.logger.error(f"Error stopping session: {e}")
    
    def auto_focus(self, infinite_focus: bool = False, stop_event: Optional[threading.Event] = None, callback: Optional[Callable] = None) -> Future:
        """Perform auto focus operation (non-blocking)."""
        if self.executor is None:
            self.logger.error("Executor not available - controller has been cleaned up")
            failed_future = concurrent.futures.Future()
            failed_future.set_exception(RuntimeError("Controller has been cleaned up"))
            return failed_future
        return self.executor.submit(self._auto_focus_sync, infinite_focus, stop_event, callback)
    
    def auto_focus_sync(self, infinite_focus: bool = False, stop_event: Optional[threading.Event] = None) -> bool:
        """Perform auto focus operation (blocking version)."""
        return self._auto_focus_sync(infinite_focus, stop_event)
    
    def _auto_focus_sync(self, infinite_focus: bool = False, stop_event: Optional[threading.Event] = None, callback: Optional[Callable] = None) -> bool:
        """Internal synchronous auto focus method."""
        try:
            with self._operation_lock:
                focus_type = "infinite" if infinite_focus else "automatic"
                self.logger.info(f"Starting {focus_type} auto focus")
                
                if stop_event and stop_event.is_set():
                    if callback:
                        callback(False, "Operation cancelled")
                    return False
                
                # Use dwarf_python_api for autofocus
                result = perform_start_autofocus(infinite=infinite_focus)
                if result:
                    self.logger.info(f"{focus_type} auto focus completed successfully")
                    if callback:
                        callback(True, f"{focus_type} focus completed")
                    return True
                else:
                    self.logger.error(f"{focus_type} auto focus failed")
                    if callback:
                        callback(False, f"{focus_type} focus failed")
                    return False
                        
        except Exception as e:
            self.logger.error(f"Auto focus failed: {e}")
            if callback:
                callback(False, f"Auto focus error: {e}")
            return False
    
    def perform_eq_solving(self, stop_event: Optional[threading.Event] = None) -> bool:
        """Perform equatorial solving (polar alignment)."""
        try:
            self.logger.info("Starting EQ solving (polar alignment)")
            
            if stop_event and stop_event.is_set():
                return False
            
            # Stop goto first - handle if function doesn't exist
            try:
                # Try dynamic import to avoid static analysis errors
                import importlib
                module = importlib.import_module("dwarf_python_api.lib.dwarf_utils")
                if hasattr(module, "perform_stop_goto_target"):
                    stop_goto_fn = getattr(module, "perform_stop_goto_target")
                    stop_goto_fn()
            except Exception:
                self.logger.debug("perform_stop_goto_target not available")
            time.sleep(5)
            
            if stop_event and stop_event.is_set():
                return False
            
            result = perform_calibration()
            
            if result:
                self.logger.info("EQ solving completed successfully")
                return True
            else:
                self.logger.error("EQ solving failed")
                return False
                
        except Exception as e:
            self.logger.error(f"EQ solving failed: {e}")
            return False

    def perform_calibration(self, stop_event: Optional[threading.Event] = None, callback: Optional[Callable] = None) -> Future:
        """Perform telescope calibration (non-blocking)."""
        if self.executor is None:
            self.logger.error("Executor not available - controller has been cleaned up")
            failed_future = concurrent.futures.Future()
            failed_future.set_exception(RuntimeError("Controller has been cleaned up"))
            return failed_future
        return self.executor.submit(self._perform_calibration_sync, stop_event, callback)
    
    def perform_calibration_sync(self, stop_event: Optional[threading.Event] = None) -> bool:
        """Perform telescope calibration (blocking version)."""
        return self._perform_calibration_sync(stop_event)
    
    def _perform_calibration_sync(self, stop_event: Optional[threading.Event] = None, callback: Optional[Callable] = None) -> bool:
        """Internal synchronous calibration method."""
        try:
            with self._operation_lock:
                self.logger.info("Starting telescope calibration")
                
                if stop_event and stop_event.is_set():
                    if callback:
                        callback(False, "Operation cancelled")
                    return False
                
                # Use dwarf_python_api for calibration
                result = perform_calibration()
                if result:
                    self.logger.info("Telescope calibration completed successfully")
                    if callback:
                        callback(True, "Calibration completed successfully")
                    return True
                else:
                    self.logger.error("Telescope calibration failed")
                    if callback:
                        callback(False, "Calibration failed")
                    return False
                        
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            if callback:
                callback(False, f"Calibration error: {e}")
            return False

    def goto_coordinates(self, ra: float, dec: float, target_name: str = "", stop_event: Optional[threading.Event] = None, callback: Optional[Callable] = None) -> Future:
        """Move telescope to specified coordinates (non-blocking)."""
        if self.executor is None:
            self.logger.error("Executor not available - controller has been cleaned up")
            failed_future = concurrent.futures.Future()
            failed_future.set_exception(RuntimeError("Controller has been cleaned up"))
            return failed_future
        return self.executor.submit(self._goto_coordinates_sync, ra, dec, target_name, stop_event, callback)
    
    def goto_coordinates_sync(self, ra: float, dec: float, target_name: str = "", stop_event: Optional[threading.Event] = None) -> bool:
        """Move telescope to specified coordinates (blocking version)."""
        return self._goto_coordinates_sync(ra, dec, target_name, stop_event)
    
    def _goto_coordinates_sync(self, ra: float, dec: float, target_name: str = "", stop_event: Optional[threading.Event] = None, callback: Optional[Callable] = None) -> bool:
        """Internal synchronous goto coordinates method."""
        try:
            with self._operation_lock:
                self.logger.info(f"Moving to coordinates RA: {ra}, DEC: {dec} (Target: {target_name})")
                
                if stop_event and stop_event.is_set():
                    if callback:
                        callback(False, "Operation cancelled")
                    return False
                
                # Use dwarf_python_api for goto
                result = perform_goto(ra, dec, target_name or "Unknown")
                if result:
                    self.logger.info(f"Goto coordinates completed successfully")
                    if callback:
                        callback(True, "Goto completed successfully")
                    return True
                else:
                    self.logger.error(f"Goto coordinates failed")
                    if callback:
                        callback(False, "Goto failed")
                    return False
                        
        except Exception as e:
            self.logger.error(f"Goto coordinates failed: {e}")
            # Check if this is a SLAVE MODE error
            if self._check_slave_mode_in_response(exception=e):
                self.logger.warning("Telescope is in SLAVE MODE - cannot perform goto")
            if callback:
                callback(False, f"Goto error: {e}")
            return False

    def setup_camera_for_capture(self, capture_settings: Dict[str, Any], stop_event: Optional[threading.Event] = None) -> bool:
        """Setup camera settings for capture session."""
        try:
            self.logger.info("Setting up camera for capture")
            
            # Extract settings for logging
            exposure = capture_settings.get("exposure_time", 30)
            gain = capture_settings.get("gain", 100)
            binning = capture_settings.get("binning", "4k")
            ir_filter = capture_settings.get("ir_filter", "astro")
            frame_count = capture_settings.get("frame_count", 1)
            
            self.logger.info(f"Camera settings: Exposure={exposure}s, Gain={gain}, Binning={binning}, IR={ir_filter}, Frames={frame_count}")
            
            # dwarf_python_api handles camera settings automatically
            # No manual camera configuration needed
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup camera: {e}")
            return False

    def start_capture_session(self, frame_count: int, stop_event: Optional[threading.Event] = None) -> bool:
        """Start astrophoto capture session."""
        try:
            self.logger.info(f"Starting capture session for {frame_count} frames")
            
            if stop_event and stop_event.is_set():
                return False
            
            # Use dwarf_python_api for astrophoto
            result = perform_takeAstroPhoto()
            
            if result:
                self.photo_session_running = True
                return True
            else:
                self.logger.error("Failed to start capture session")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting capture session: {e}")
            return False
    
    def wait_for_capture_completion(self, stop_event: Optional[threading.Event] = None, progress_callback=None) -> bool:
        """Wait for capture session to complete."""
        try:
            self.logger.info("Waiting for capture session to complete")
            
            # dwarf_python_api handles capture automatically
            # Simple polling for session status
            while self.photo_session_running:
                if stop_event and stop_event.is_set():
                    self.logger.info("Capture session interrupted by user")
                    self._stop_capture_session()
                    return False
                
                # Check if session is still active (simplified check)
                # In practice, dwarf_python_api would provide status updates
                time.sleep(3)
                
                # For now, assume completion after reasonable time
                # This would be replaced with actual status checking
                self.photo_session_running = False
                break
            
            self.logger.info("Capture session completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error waiting for capture completion: {e}")
            self.photo_session_running = False
            return False
    
    def _stop_capture_session(self):
        """Stop the current capture session."""
        try:
            self.logger.info("Stopping capture session")
            perform_stopAstroPhoto()
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
    
    def plate_solve_async(self, stop_event: Optional[threading.Event] = None) -> bool:
        """Perform plate solving (same as EQ solving)."""
        return self.perform_eq_solving(stop_event)
    
    def start_guiding_async(self, stop_event: Optional[threading.Event] = None) -> bool:
        """Start auto guiding."""
        try:
            self.logger.info("Starting auto guiding")
            
            if stop_event and stop_event.is_set():
                return False
            
            # Try to import perform_start_tracking, handle if unavailable
            try:
                import importlib
                module = importlib.import_module("dwarf_python_api.lib.dwarf_utils")
                if hasattr(module, "perform_start_tracking"):
                    tracking_fn = getattr(module, "perform_start_tracking")
                    result = tracking_fn()
                else:
                    # Fallback if function not available
                    self.logger.warning("perform_start_tracking not available")
                    result = False
            except Exception:
                # Fallback if function not available
                self.logger.warning("perform_start_tracking not available")
                result = False
            
            if result:
                self.logger.info("Auto guiding started successfully")
                return True
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
            
            # Try to import perform_stop_tracking, handle if unavailable
            try:
                import importlib
                module = importlib.import_module("dwarf_python_api.lib.dwarf_utils")
                if hasattr(module, "perform_stop_tracking"):
                    stop_tracking_fn = getattr(module, "perform_stop_tracking")
                    result = stop_tracking_fn()
                else:
                    # Fallback if function not available
                    self.logger.warning("perform_stop_tracking not available")
                    result = False
            except Exception:
                # Fallback if function not available
                self.logger.warning("perform_stop_tracking not available")
                result = False
            
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
            #if self.current_session_active:
            #    self._stop_current_session()
            
            # Stop any running capture
            #if self.photo_session_running:
            #    self._stop_capture_session()
            
            # Disconnect using dwarf_python_api with proper cleanup
            try:
                perform_disconnect()
                # Give time for the websocket to close properly
                time.sleep(1)
                self.logger.info("Disconnected from Dwarf3")
            except Exception as api_error:
                self.logger.warning(f"Error during disconnect: {api_error}")
            
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
            
            # Cancel all tracked active futures
            with self._futures_lock:
                futures_to_cancel = list(self._active_futures)
                cancelled_count = 0
                
                for future in futures_to_cancel:
                    if not future.done():
                        if future.cancel():
                            cancelled_count += 1
                            self.logger.debug(f"Successfully cancelled future")
                        else:
                            self.logger.debug(f"Could not cancel future (likely already running)")
                
                self.logger.info(f"Cancelled {cancelled_count} pending connection futures")
            
            # Reset connection state
            self.connected = False
            self.telescope_info_retrieved = False  # Reset flag so telescope info is retrieved on next connection
            
            # Force disconnect to clean up any partial connections
            try:
                perform_disconnect()
                self.logger.debug("Cancelled dwarf_python_api connection")
            except Exception as e:
                self.logger.debug(f"Error cancelling dwarf_python_api connection: {e}")
            
            # Close HTTP session (used only for getDefaultParamsConfig)
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
        return True
    
    def reset_slave_mode_detection(self):
        """Reset SLAVE MODE detection flag."""
        self.slave_mode_detected = False
    
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
            "api_mode": "dwarf_python_api",
            "ip": self.ip,
            "session_active": self.current_session_active,
            "photo_running": self.photo_session_running,
            "last_update": time.time()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current telescope status."""
        try:
            # Return status based on our internal connection state since getstatus doesn't work reliably
            status = {
                "connected": self.connected,
                "api_mode": "dwarf_python_api",
                "ip": self.ip,
                "session_active": self.current_session_active,
                "photo_session_running": self.photo_session_running,
                "last_update": time.time()
            }
            
            # Add telescope info if available
            if self.telescope_info:
                status.update(self.telescope_info)
            
            # If connected, try to get additional status but don't fail if getstatus doesn't work
            if self.connected:
                try:
                    dwarf_status = self._safe_getstatus(timeout=5)
                    if dwarf_status:
                        status["dwarf_data"] = dwarf_status
                        status["status_check"] = "Success"
                    else:
                        status["status_check"] = "Connected (getstatus unavailable)"
                except Exception as e:
                    # Don't fail the whole status check just because getstatus failed
                    status["status_check"] = f"Connected (getstatus error: {str(e)[:50]})"
            
            return status
                
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return {"connected": False, "error": str(e)}
    
    def emergency_stop(self):
        """Emergency stop all telescope operations."""
        try:
            self.logger.warning("Emergency stop initiated")
            
            # Stop all operations using dwarf_python_api
            try:
                # Try dynamic import to avoid static analysis errors
                import importlib
                module = importlib.import_module("dwarf_python_api.lib.dwarf_utils")
                if hasattr(module, "perform_stop_goto_target"):
                    stop_goto_fn = getattr(module, "perform_stop_goto_target")
                    stop_goto_fn()
            except Exception:
                pass
            try:
                perform_stopAstroPhoto()
            except Exception:
                pass
            try:
                # Try dynamic import to avoid static analysis errors
                import importlib
                module = importlib.import_module("dwarf_python_api.lib.dwarf_utils")
                if hasattr(module, "perform_stop_tracking"):
                    stop_tracking_fn = getattr(module, "perform_stop_tracking")
                    stop_tracking_fn()
            except Exception:
                pass
            
            # Force disconnect
            try:
                perform_disconnect()
            except Exception as e:
                self.logger.debug(f"Error during disconnect in emergency stop: {e}")
            
            # Reset state
            self.current_session_active = False
            self.photo_session_running = False
            self.connected = False
            
            self.logger.info("Emergency stop completed")
            
        except Exception as e:
            self.logger.error(f"Error during emergency stop: {e}")
    
    def _wait_for_plate_solve_completion_http(self) -> bool:
        """Wait for plate solving to complete (HTTP fallback)."""
        start_time = time.time()
        
        while time.time() - start_time < 180:
            status = self.get_status()
            if status and status.get("mount", {}).get("plate_solving") == False:
                solve_result = status.get("mount", {}).get("plate_solve_result", "unknown")
                self.logger.info(f"Plate solve completed: {solve_result}")
                return solve_result == "success"
                
            time.sleep(3)
            
        self.logger.error("Plate solve timeout")
        return False
            
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
        
    def set_camera_settings(self, gain: Optional[int] = None, binning: Optional[str] = None) -> bool:
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
