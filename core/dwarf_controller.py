"""
Controller for communicating with Dwarf3 smart telescope.
"""

import requests
import time
import logging
from typing import Dict, Any, Optional, Tuple

class DwarfController:
    """Controls Dwarf3 telescope via API."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Connection settings
        telescope_config = config_manager.get_telescope_settings()
        self.ip = telescope_config.get("ip", "192.168.4.1")
        self.port = telescope_config.get("port", 80)
        self.timeout = telescope_config.get("timeout", 10)
        
        self.base_url = f"http://{self.ip}:{self.port}"
        self.connected = False
        self.session = requests.Session()
        
    def connect(self) -> bool:
        """Connect to the Dwarf3 telescope."""
        try:
            self.logger.info(f"Connecting to Dwarf3 at {self.base_url}")
            
            # Test connection with a simple status request
            response = self.session.get(
                f"{self.base_url}/api/status",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                self.connected = True
                self.logger.info("Successfully connected to Dwarf3")
                return True
            else:
                self.logger.error(f"Connection failed with status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to connect to Dwarf3: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from the telescope."""
        self.connected = False
        self.session.close()
        self.logger.info("Disconnected from Dwarf3")
        
    def is_connected(self) -> bool:
        """Check if connected to telescope."""
        return self.connected
        
    def goto_coordinates(self, ra: str, dec: str) -> bool:
        """Move telescope to specified coordinates."""
        try:
            if not self.connected:
                self.logger.error("Not connected to telescope")
                return False
                
            self.logger.info(f"Moving to coordinates RA: {ra}, DEC: {dec}")
            
            # Convert RA/DEC to format expected by Dwarf3 API
            ra_degrees, dec_degrees = self._parse_coordinates(ra, dec)
            
            payload = {
                "command": "goto",
                "ra": ra_degrees,
                "dec": dec_degrees
            }
            
            response = self.session.post(
                f"{self.base_url}/api/mount/goto",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                # Wait for slew to complete
                return self._wait_for_slew_completion()
            else:
                self.logger.error(f"GoTo command failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in goto_coordinates: {e}")
            return False
            
    def auto_focus(self) -> bool:
        """Perform auto focus."""
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
