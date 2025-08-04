"""
Scheduler engine for managing telescope session execution.
"""

import threading
import time
import datetime
import logging
import os
from typing import Dict, Any, Optional, Callable
from .session_manager import SessionManager
from .dwarf_controller import DwarfController
from .history_manager import HistoryManager

class Scheduler:
    """Main scheduler for managing telescope session execution."""
    
    def __init__(self, session_manager: SessionManager, config_manager):
        self.session_manager = session_manager
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize controllers
        self.dwarf_controller = DwarfController(config_manager)
        self.telescope_controller = self.dwarf_controller  # Alias for threaded access
        self.history_manager = HistoryManager()
        
        # Scheduler state
        self.is_running = False
        self.current_session = None
        self.scheduler_thread = None
        self.stop_event = threading.Event()
        
        # Callbacks for UI updates
        self.status_callback: Optional[Callable[[str], None]] = None
        self.session_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Check for orphaned running sessions on startup
        self.check_orphaned_sessions()
        
    def set_status_callback(self, callback: Callable[[str], None]):
        """Set callback function for status updates."""
        self.status_callback = callback
        
    def set_session_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback function for session updates."""
        self.session_callback = callback
        
    def start(self):
        """Start the scheduler."""
        if self.is_running:
            self.logger.warning("Scheduler is already running")
            return
            
        self.is_running = True
        self.stop_event.clear()
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info("Scheduler started")
        self._update_status("Scheduler started - monitoring for sessions")
        
    def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            self.logger.warning("Scheduler is not running")
            return
            
        self.is_running = False
        self.stop_event.set()
        
        # Wait for thread to finish
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
            
        self.logger.info("Scheduler stopped")
        self._update_status("Scheduler stopped")
        
    def _scheduler_loop(self):
        """Main scheduler loop."""
        slave_mode_pause_count = 0
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # Check if telescope is in SLAVE MODE
                if self.dwarf_controller.is_slave_mode_detected():
                    slave_mode_pause_count += 1
                    
                    # Report SLAVE MODE every 5 minutes (10 cycles of 30 seconds)
                    if slave_mode_pause_count % 10 == 1:
                        self._update_status("Scheduler paused - telescope in SLAVE MODE (being used by another application)")
                        self.logger.warning("Scheduler paused - telescope is in SLAVE MODE, will retry when available")
                    
                    # Reset SLAVE MODE detection every 10 minutes to allow retry
                    if slave_mode_pause_count >= 20:  # 20 * 30 seconds = 10 minutes
                        self.logger.info("Resetting SLAVE MODE detection after 10 minutes, will attempt to reconnect")
                        self.dwarf_controller.reset_slave_mode_detection()
                        slave_mode_pause_count = 0
                        
                    # Skip session execution while in SLAVE MODE
                    self.stop_event.wait(30)
                    continue
                else:
                    # Reset counter when not in SLAVE MODE
                    slave_mode_pause_count = 0
                
                # Check for scheduled sessions
                scheduled_sessions = self.session_manager.get_scheduled_sessions()
                
                for session in scheduled_sessions:
                    if self.stop_event.is_set():
                        break
                        
                    # Check if session is due
                    if self._is_session_due(session):
                        self._execute_session(session)
                        
                # Sleep before next check
                self.stop_event.wait(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                self.stop_event.wait(60)  # Wait longer on error
                
    def _is_session_due(self, session: Dict[str, Any]) -> bool:
        """Check if a session is due for execution."""
        try:
            start_time_str = session.get("start_time")
            if not start_time_str:
                return False
                
            start_time = datetime.datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            current_time = datetime.datetime.now()
            
            # Session is due if start time has passed
            return current_time >= start_time
            
        except Exception as e:
            self.logger.error(f"Error checking session due time: {e}")
            return False
            
    def _execute_session(self, session: Dict[str, Any]):
        """Execute a telescope session with enhanced error handling."""
        session_name = session.get("session_name", "Unknown")
        self.logger.info(f"Starting execution of session: {session_name}")
        
        try:
            # Move session to Running
            filename = self._get_session_filename(session)
            if filename:
                self.session_manager.move_session(filename, "ToDo", "Running")
                
            self.current_session = session
            self._update_status(f"Executing session: {session_name}")
            
            # Connect to telescope first
            self._update_status("Connecting to telescope")
            if not self.dwarf_controller.connect():
                # Check if SLAVE MODE was detected
                if self.dwarf_controller.is_slave_mode_detected():
                    raise Exception("Telescope is in SLAVE MODE - being used by another application")
                else:
                    raise Exception("Failed to connect to telescope")
                
            self._update_status("Connected to telescope")
            
            # Execute session steps with the enhanced flow
            success = self._run_session_steps(session)
            
            if success:
                # Move to Done and record in history
                if filename:
                    self.session_manager.move_session(filename, "Running", "Done")
                self._record_session_completion(session, "Completed")
                self._update_status(f"Session completed: {session_name}")
                self.logger.info(f"Session completed successfully: {session_name}")
            else:
                # Move to Failed
                if filename:
                    self.session_manager.move_session(filename, "Running", "Failed")
                self._record_session_completion(session, "Failed")
                self._update_status(f"Session failed: {session_name}")
                self.logger.warning(f"Session failed: {session_name}")
                
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Error executing session {session_name}: {error_message}")
            
            # Check if this was a SLAVE MODE error
            if "slave mode" in error_message.lower():
                self.logger.warning(f"Session {session_name} failed due to SLAVE MODE - telescope being used by another application")
                # Move back to ToDo for retry later when telescope becomes available
                filename = self._get_session_filename(session)
                if filename:
                    try:
                        self.session_manager.move_session(filename, "Running", "ToDo")
                    except Exception as move_error:
                        self.logger.error(f"Failed to move session back to ToDo folder: {move_error}")
                self._record_session_completion(session, "Postponed", "Telescope in SLAVE MODE - moved back to ToDo for retry")
                self._update_status(f"Session postponed due to SLAVE MODE: {session_name}")
            else:
                # Move to Failed on other exceptions
                filename = self._get_session_filename(session)
                if filename:
                    try:
                        self.session_manager.move_session(filename, "Running", "Failed")
                    except Exception as move_error:
                        self.logger.error(f"Failed to move session to Failed folder: {move_error}")
                self._record_session_completion(session, "Failed", error_message)
                self._update_status(f"Session error: {session_name}")
            
        finally:
            self.current_session = None
            # Ensure telescope is disconnected
            try:
                if self.dwarf_controller.is_connected():
                    self.dwarf_controller.disconnect()
            except Exception as disconnect_error:
                self.logger.error(f"Error during disconnect: {disconnect_error}")
            
    def _run_session_steps(self, session: Dict[str, Any]) -> bool:
        """Run all steps for a session using enhanced Dwarf API flow."""
        try:
            # Step 1: Start imaging session (Go Live)
            self._update_status("Starting imaging session")
            if not self.dwarf_controller.start_session(self.stop_event):
                self.logger.error("Failed to start imaging session")
                return False
            
            if self.stop_event.is_set():
                return False
                
            # Step 2: Calibration steps
            calibration = session.get("calibration", {})
            
            # Auto focus
            if calibration.get("auto_focus", False):
                self._update_status("Performing auto focus")
                infinite_focus = calibration.get("infinite_focus", False)
                if not self.dwarf_controller.auto_focus(infinite_focus, self.stop_event):
                    self.logger.warning("Auto focus failed, continuing anyway")
                    
            if self.stop_event.is_set():
                return False
                    
            # EQ Solving (Polar Alignment)
            if calibration.get("eq_solving", False):
                self._update_status("Performing EQ solving")
                if not self.dwarf_controller.perform_eq_solving(self.stop_event):
                    self.logger.warning("EQ solving failed, continuing anyway")
                    
            if self.stop_event.is_set():
                return False
                    
            # Telescope calibration
            if calibration.get("calibrate", False):
                self._update_status("Performing telescope calibration")
                if not self.dwarf_controller.perform_calibration(self.stop_event):
                    self.logger.warning("Calibration failed, continuing anyway")
                    
            if self.stop_event.is_set():
                return False
                
            # Step 3: Move to target coordinates
            coordinates = session.get("coordinates", {})
            ra = coordinates.get("ra")
            dec = coordinates.get("dec")
            target_name = session.get("target_name", "Unknown")
            
            if ra and dec:
                self._update_status("Moving to target coordinates")
                # Convert string coordinates to float if needed
                try:
                    ra_float = float(ra) if isinstance(ra, str) else ra
                    dec_float = float(dec) if isinstance(dec, str) else dec
                except (ValueError, TypeError):
                    self.logger.error(f"Invalid coordinates format: RA={ra}, DEC={dec}")
                    return False
                    
                if not self.dwarf_controller.goto_coordinates(ra_float, dec_float, target_name, self.stop_event):
                    self.logger.error("Failed to move to target coordinates")
                    return False
                    
            if self.stop_event.is_set():
                return False
                
            # Step 4: Auto guiding
            if calibration.get("auto_guide", False):
                self._update_status("Starting auto guiding")
                if not self.dwarf_controller.start_guiding(self.stop_event):
                    self.logger.warning("Auto guiding failed, continuing anyway")
                    
            if self.stop_event.is_set():
                return False
                    
            # Step 5: Settling time
            settling_time = calibration.get("settling_time", 10)
            if settling_time > 0:
                self._update_status(f"Settling for {settling_time} seconds")
                for i in range(settling_time):
                    if self.stop_event.is_set():
                        return False
                    time.sleep(1)
                    
            # Step 6: Setup camera and capture images
            capture_settings = session.get("capture_settings", {})
            
            # Setup camera for capture
            self._update_status("Setting up camera for capture")
            if not self.dwarf_controller.setup_camera_for_capture(capture_settings, self.stop_event):
                self.logger.error("Failed to setup camera")
                return False
                
            if self.stop_event.is_set():
                return False
            
            # Start capture session
            frame_count = capture_settings.get("frame_count", 1)
            self._update_status(f"Starting capture session for {frame_count} frames")
            
            if not self.dwarf_controller.start_capture_session(frame_count, self.stop_event):
                self.logger.error("Failed to start capture session")
                return False
                
            if self.stop_event.is_set():
                return False
            
            # Wait for capture completion with progress updates
            self._update_status("Capturing frames...")
            
            def progress_callback(captured, total):
                if not self.stop_event.is_set():
                    self._update_status(f"Capturing frame {captured}/{total}")
            
            success = self.dwarf_controller.wait_for_capture_completion(
                self.stop_event, 
                progress_callback
            )
            
            if not success:
                self.logger.warning("Capture session completed with issues")
                
            # Step 7: Cleanup
            if calibration.get("auto_guide", False):
                self._update_status("Stopping auto guiding")
                self.dwarf_controller.stop_guiding()
                
            self._update_status("Session capture completed")
            
            # Consider session successful if we got through the capture phase
            return True
            
        except Exception as e:
            self.logger.error(f"Error in session steps: {e}")
            return False
            
        finally:
            # Always disconnect and cleanup
            try:
                self.dwarf_controller.disconnect()
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
            
    def _get_session_filename(self, session: Dict[str, Any]) -> Optional[str]:
        """Get the filename for a session."""
        # Try to reconstruct the filename from session data
        created_date = session.get("created_date", "")
        target_name = session.get("target_name", "Unknown").replace(" ", "_")
        
        if created_date:
            # Parse the ISO format datetime and convert to filename format
            try:
                dt = datetime.datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                timestamp = dt.strftime("%Y%m%d_%H%M%S")
            except:
                # Fallback to current timestamp if parsing fails
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        else:
            # Fallback to current timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
        # Remove any invalid filename characters from target name
        target_name = "".join(c for c in target_name if c.isalnum() or c in "._-")
        
        filename = f"{timestamp}_{target_name}.json"
        
        # Try to find the actual file if the generated name doesn't exist
        for status_dir in ["ToDo", "Running", "Available"]:
            full_path = os.path.join("Sessions", status_dir, filename)
            if os.path.exists(full_path):
                return filename
                
        # If exact match not found, try to find by pattern matching
        session_name = session.get("session_name", "")
        session_id = session.get("session_id", "")
        
        for status_dir in ["ToDo", "Running", "Available"]:
            dir_path = f"Sessions/{status_dir}"
            if os.path.exists(dir_path):
                for file in os.listdir(dir_path):
                    if file.endswith('.json'):
                        # Try to match by loading the file and comparing session data
                        try:
                            file_session = self.session_manager.load_session(file, dir_path)
                            if file_session and (
                                (session_id and file_session.get("session_id") == session_id) or
                                (session_name and file_session.get("session_name") == session_name) or
                                (file_session.get("target_name") == session.get("target_name") and
                                 file_session.get("session_name") == session_name)
                            ):
                                return file
                        except:
                            continue
        
        return filename  # Return generated filename as fallback
        
    def _record_session_completion(self, session: Dict[str, Any], status: str, error_msg: str = ""):
        """Record session completion in history."""
        try:
            history_record = {
                "session_name": session.get("session_name", ""),
                "target_name": session.get("target_name", ""),
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "status": status,
                "coordinates": session.get("coordinates", {}),
                "capture_settings": session.get("capture_settings", {}),
                "calibration": session.get("calibration", {}),
                "error_message": error_msg,
                "completed_date": datetime.datetime.now().isoformat()
            }
            
            self.history_manager.add_record(history_record)
            
        except Exception as e:
            self.logger.error(f"Failed to record session completion: {e}")
            
    def _update_status(self, message: str):
        """Update status and notify callbacks."""
        if self.status_callback:
            self.status_callback(message)
            
    def get_current_session(self) -> Optional[Dict[str, Any]]:
        """Get currently executing session."""
        return self.current_session
        
    def is_session_running(self) -> bool:
        """Check if a session is currently running."""
        return self.current_session is not None
        
    def get_telescope_status(self, timeout: int = 10) -> Dict[str, Any]:
        """Get telescope connection status and information (with timeout)."""
        try:
            # Use quick status check first (non-blocking)
            if self.dwarf_controller.connected:
                # Return quick status for immediate response
                quick_status = self.dwarf_controller.quick_status_check()
                
                # Get cached telescope info if available
                telescope_info = self.dwarf_controller.get_telescope_info()
                if telescope_info:
                    quick_status.update({
                        "model": telescope_info.get("model", "DWARF3"),
                        "firmware_version": telescope_info.get("firmware_version", "Connected via API"),
                        "status": telescope_info.get("status", "Connected"),
                        "stream_type": telescope_info.get("stream_type", ""),
                        "status_check": telescope_info.get("status_check", "Available")
                    })
                
                return quick_status
            
            # Only attempt connection test if not already connected
            # Use a very short timeout to prevent GUI blocking
            elif hasattr(self.dwarf_controller, 'test_connection_sync'):
                # Quick connection test with minimal timeout
                try:
                    # This should be fast and non-blocking
                    connected = self.dwarf_controller._test_connection()
                    if connected:
                        return {
                            "connected": True, 
                            "model": "DWARF3", 
                            "api_mode": "HTTP",
                            "status": "Connected via HTTP",
                            "last_update": time.time()
                        }
                    else:
                        return {"connected": False, "status": "Unable to connect"}
                except Exception as e:
                    self.logger.debug(f"Quick connection test failed: {e}")
                    return {"connected": False, "status": f"Connection test failed"}
            else:
                return {"connected": False, "status": "No connection available"}
                
        except Exception as e:
            self.logger.error(f"Failed to get telescope status: {e}")
            return {"connected": False, "status": f"Error: {str(e)}"}
            
    def abort_current_session(self):
        """Abort the currently running session."""
        if self.current_session:
            self.logger.info(f"Aborting session: {self.current_session.get('session_name', 'Unknown')}")
            
            # Emergency stop all telescope operations
            try:
                if self.dwarf_controller.is_connected():
                    self.dwarf_controller.emergency_stop()
            except Exception as e:
                self.logger.error(f"Error during emergency stop: {e}")
            
            # Set stop event to interrupt session
            self.stop_event.set()
            
            # Move session to Failed
            filename = self._get_session_filename(self.current_session)
            if filename:
                try:
                    self.session_manager.move_session(filename, "Running", "Failed")
                except Exception as e:
                    self.logger.error(f"Failed to move aborted session to Failed folder: {e}")
                
            self._record_session_completion(self.current_session, "Aborted", "Session aborted by user")
            self._update_status("Session aborted")
            
            self.current_session = None
            
            # Ensure telescope is disconnected
            try:
                if self.dwarf_controller.is_connected():
                    self.dwarf_controller.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting after abort: {e}")
            
        # Restart the stop event for future sessions
        time.sleep(1)
        self.stop_event.clear()
        
    def check_orphaned_sessions(self):
        """Check for orphaned running sessions on startup and provide recovery options."""
        try:
            running_sessions = self.session_manager.get_session_by_status("Running")
            
            if running_sessions:
                self.logger.warning(f"Found {len(running_sessions)} orphaned running sessions from previous startup")
                
                for session in running_sessions:
                    session_name = session.get("session_name", "Unknown")
                    filename = self._get_session_filename(session)
                    
                    if filename:
                        self.logger.info(f"Moving orphaned session '{session_name}' to Failed status")
                        
                        # Move to Failed and record in history
                        try:
                            self.session_manager.move_session(filename, "Running", "Failed")
                            self._record_session_completion(
                                session, 
                                "Failed", 
                                "Session interrupted - application was closed while running"
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to move orphaned session {session_name}: {e}")
                
                # Update status callback if available
                if self.status_callback:
                    self.status_callback(f"Recovered {len(running_sessions)} orphaned sessions")
                    
        except Exception as e:
            self.logger.error(f"Error checking orphaned sessions: {e}")
            
    def recover_running_sessions(self, action: str = "fail"):
        """Manually recover running sessions with specified action.
        
        Args:
            action: 'fail', 'todo', or 'available' - where to move the sessions
        """
        try:
            running_sessions = self.session_manager.get_session_by_status("Running")
            
            if not running_sessions:
                self.logger.info("No running sessions to recover")
                return []
                
            recovered = []
            target_status = {
                "fail": "Failed",
                "todo": "ToDo", 
                "available": "Available"
            }.get(action, "Failed")
            
            for session in running_sessions:
                session_name = session.get("session_name", "Unknown")
                filename = self._get_session_filename(session)
                
                if filename:
                    try:
                        self.session_manager.move_session(filename, "Running", target_status)
                        
                        # Record in history if moving to Failed
                        if target_status == "Failed":
                            self._record_session_completion(
                                session, 
                                "Failed", 
                                "Session manually recovered from orphaned state"
                            )
                            
                        recovered.append(session_name)
                        self.logger.info(f"Recovered session '{session_name}' to {target_status}")
                        
                    except Exception as e:
                        self.logger.error(f"Failed to recover session {session_name}: {e}")
                        
            return recovered
            
        except Exception as e:
            self.logger.error(f"Error recovering running sessions: {e}")
            return []