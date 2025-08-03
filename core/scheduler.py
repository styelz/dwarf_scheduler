"""
Scheduler engine for managing telescope session execution.
"""

import threading
import time
import datetime
import logging
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
        self.history_manager = HistoryManager()
        
        # Scheduler state
        self.is_running = False
        self.current_session = None
        self.scheduler_thread = None
        self.stop_event = threading.Event()
        
        # Callbacks for UI updates
        self.status_callback: Optional[Callable[[str], None]] = None
        self.session_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
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
        while self.is_running and not self.stop_event.is_set():
            try:
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
        """Execute a telescope session."""
        session_name = session.get("session_name", "Unknown")
        self.logger.info(f"Starting execution of session: {session_name}")
        
        try:
            # Move session to Running
            filename = self._get_session_filename(session)
            if filename:
                self.session_manager.move_session(filename, "ToDo", "Running")
                
            self.current_session = session
            self._update_status(f"Executing session: {session_name}")
            
            # Execute session steps
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
            self.logger.error(f"Error executing session {session_name}: {e}")
            # Move to Failed on exception
            filename = self._get_session_filename(session)
            if filename:
                self.session_manager.move_session(filename, "Running", "Failed")
            self._record_session_completion(session, "Failed", str(e))
            self._update_status(f"Session error: {session_name}")
            
        finally:
            self.current_session = None
            
    def _run_session_steps(self, session: Dict[str, Any]) -> bool:
        """Run all steps for a session."""
        try:
            # Connect to telescope
            if not self.dwarf_controller.connect():
                self.logger.error("Failed to connect to telescope")
                return False
                
            self._update_status("Connected to telescope")
            
            # Step 1: Move to target coordinates
            coordinates = session.get("coordinates", {})
            ra = coordinates.get("ra")
            dec = coordinates.get("dec")
            
            if ra and dec:
                self._update_status("Moving to target coordinates")
                if not self.dwarf_controller.goto_coordinates(ra, dec):
                    self.logger.error("Failed to move to target coordinates")
                    return False
                    
            # Step 2: Calibration steps
            calibration = session.get("calibration", {})
            
            # Auto focus
            if calibration.get("auto_focus", False):
                self._update_status("Performing auto focus")
                if not self.dwarf_controller.auto_focus():
                    self.logger.warning("Auto focus failed, continuing anyway")
                    
            # Plate solving
            if calibration.get("plate_solve", False):
                self._update_status("Plate solving")
                if not self.dwarf_controller.plate_solve():
                    self.logger.warning("Plate solving failed, continuing anyway")
                    
            # Auto guiding
            if calibration.get("auto_guide", False):
                self._update_status("Starting auto guiding")
                if not self.dwarf_controller.start_guiding():
                    self.logger.warning("Auto guiding failed, continuing anyway")
                    
            # Settling time
            settling_time = calibration.get("settling_time", 10)
            if settling_time > 0:
                self._update_status(f"Settling for {settling_time} seconds")
                time.sleep(settling_time)
                
            # Step 3: Capture images
            capture_settings = session.get("capture_settings", {})
            frame_count = capture_settings.get("frame_count", 1)
            exposure_time = capture_settings.get("exposure_time", 30)
            
            self._update_status(f"Capturing {frame_count} frames")
            
            captured_frames = 0
            for frame_num in range(frame_count):
                if self.stop_event.is_set():
                    self.logger.info("Session interrupted by stop signal")
                    break
                    
                self._update_status(f"Capturing frame {frame_num + 1}/{frame_count}")
                
                if self.dwarf_controller.capture_frame(exposure_time):
                    captured_frames += 1
                else:
                    self.logger.warning(f"Failed to capture frame {frame_num + 1}")
                    
            # Step 4: Cleanup
            if calibration.get("auto_guide", False):
                self.dwarf_controller.stop_guiding()
                
            self._update_status("Session capture completed")
            
            # Check if we captured at least some frames
            success_threshold = 0.8  # 80% of frames must be captured
            success = captured_frames >= (frame_count * success_threshold)
            
            self.logger.info(f"Captured {captured_frames}/{frame_count} frames")
            return success
            
        except Exception as e:
            self.logger.error(f"Error in session steps: {e}")
            return False
            
        finally:
            # Always disconnect
            self.dwarf_controller.disconnect()
            
    def _get_session_filename(self, session: Dict[str, Any]) -> Optional[str]:
        """Get the filename for a session."""
        # This would need to match the session with its file
        # For now, generate based on session data
        timestamp = session.get("created_date", "").replace(":", "").replace("-", "")[:8]
        target_name = session.get("target_name", "Unknown").replace(" ", "_")
        return f"{timestamp}_{target_name}.json"
        
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
        
    def abort_current_session(self):
        """Abort the currently running session."""
        if self.current_session:
            self.logger.info(f"Aborting session: {self.current_session.get('session_name', 'Unknown')}")
            
            # Set stop event to interrupt session
            self.stop_event.set()
            
            # Move session to Failed
            filename = self._get_session_filename(self.current_session)
            if filename:
                self.session_manager.move_session(filename, "Running", "Failed")
                
            self._record_session_completion(self.current_session, "Aborted", "Session aborted by user")
            self._update_status("Session aborted")
            
            self.current_session = None
            
            # Restart the stop event for future sessions
            time.sleep(1)
            self.stop_event.clear()
