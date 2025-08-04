"""
Controller for communicating with Dwarf3 smart telescope.
Enhanced with proper API flow based on dwarf_python_api implementation.
"""

import requests
import time
import logging
import threading
from typing import Dict, Any, Optional, Tuple

class DwarfController:
    """Controls Dwarf3 telescope via API with enhanced session management."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Connection settings
        telescope_config = config_manager.get_telescope_settings()
        self.ip = telescope_config.get("ip", "192.168.4.1")
        self.port = telescope_config.get("port", 80)
        self.timeout = telescope_config.get("timeout", 10)
        
        self.base_url = f"http://{self.ip}:{self.port}/api"
        self.connected = False
        self.session = requests.Session()
        
        # Session state tracking
        self.current_session_active = False
        self.photo_session_running = False
        
    def connect(self) -> bool:
        """Connect to the Dwarf3 telescope."""
        try:
            self.logger.info(f"Connecting to Dwarf3 at {self.base_url}")
            
            # Test connection with time sync (similar to perform_time)
            if self._perform_time_sync():
                self.connected = True
                self.logger.info("Successfully connected to Dwarf3")
                return True
            else:
                self.logger.error("Failed to establish proper connection")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to Dwarf3: {e}")
            return False
    
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
            
            result = self._make_request("POST", "/go_live", {})
            if result:
                self.current_session_active = True
                self.logger.info("Imaging session started successfully")
                return True
            else:
                self.logger.error("Failed to start imaging session")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting session: {e}")
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
    
    def auto_focus(self, infinite_focus: bool = False, stop_event: threading.Event = None) -> bool:
        """Perform auto focus operation."""
        try:
            focus_type = "infinite" if infinite_focus else "automatic"
            self.logger.info(f"Starting {focus_type} auto focus")
            
            if stop_event and stop_event.is_set():
                return False
            
            result = self._make_request("POST", "/autofocus", {
                "infinite": infinite_focus
            })
            
            if result:
                # Wait for autofocus to complete
                return self._wait_for_autofocus_completion(stop_event)
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Auto focus failed: {e}")
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
    
    def perform_calibration(self, stop_event: threading.Event = None) -> bool:
        """Perform telescope calibration."""
        try:
            self.logger.info("Starting telescope calibration")
            
            # Set calibration camera settings
            if not self._set_calibration_settings(stop_event):
                return False
            
            if stop_event and stop_event.is_set():
                return False
            
            # Stop goto before calibration
            self._make_request("POST", "/stop_goto", {})
            time.sleep(5)
            
            if stop_event and stop_event.is_set():
                return False
            
            # Start calibration
            result = self._make_request("POST", "/calibration", {})
            
            if result:
                return self._wait_for_calibration_completion(stop_event)
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
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
    
    def goto_coordinates(self, ra: float, dec: float, target_name: str = "", stop_event: threading.Event = None) -> bool:
        """Move telescope to specified coordinates."""
        try:
            self.logger.info(f"Moving to coordinates RA: {ra}, DEC: {dec} (Target: {target_name})")
            
            if stop_event and stop_event.is_set():
                return False
            
            result = self._make_request("POST", "/goto", {
                "ra": ra,
                "dec": dec,
                "target_name": target_name or "Unknown"
            })
            
            if result:
                return self._wait_for_goto_completion(stop_event)
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Goto coordinates failed: {e}")
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
            
            # Close connection
            self.connected = False
            self.session.close()
            self.logger.info("Disconnected from Dwarf3")
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to telescope."""
        return self.connected
    
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
