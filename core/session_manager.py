"""
Session manager for handling telescope observation sessions.
"""

import json
import os
import datetime
import shutil
import logging
from typing import List, Dict, Any, Optional

class SessionManager:
    """Manages telescope observation sessions."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sessions_dir = "Sessions"
        self.ensure_directories()
        
    def ensure_directories(self):
        """Ensure all session directories exist."""
        directories = [
            "Sessions/Available",
            "Sessions/ToDo", 
            "Sessions/Done",
            "Sessions/Running",
            "Sessions/Failed",
            "Sessions/History"
        ]
        
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                self.logger.info(f"Created directory: {directory}")
                
    def generate_session_filename(self, session_data: Dict[str, Any]) -> str:
        """Generate a filename for the session using the session name."""
        # Use session_name as the filename, sanitized for filesystem
        session_name = session_data.get("session_name", "Unknown").replace(" ", "_")
        # Remove any invalid filename characters
        session_name = "".join(c for c in session_name if c.isalnum() or c in "._-")
        return f"{session_name}.json"
        
    def load_session_with_filename(self, session_name: str, directory: str = "Sessions/Available"):
        """
        Load session data and return (data, filename).
        """
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                filepath = os.path.join(directory, filename)
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    if data.get('session_name') == session_name:
                        return data, filepath
        return None, None

    def save_session(self, session_data: dict, filename: str = None, status: str = "Available") -> str:
        """
        Save session data. If filename is provided, overwrite it.
        """
        if filename:
            with open(filename, 'w') as f:
                json.dump(session_data, f, indent=2)
            return filename
        else:
            try:
                # Add metadata
                session_data["created_date"] = datetime.datetime.now().isoformat()
                session_data["status"] = status
                
                # Add unique session ID if not present
                if "session_id" not in session_data:
                    import uuid
                    session_data["session_id"] = str(uuid.uuid4())
                
                # Generate filename
                filename = self.generate_session_filename(session_data)
                
                # Determine directory based on status
                if status == "Available":
                    directory = "Sessions/Available"
                elif status == "ToDo":
                    directory = "Sessions/ToDo"
                elif status == "Running":
                    directory = "Sessions/Running"
                elif status == "Done":
                    directory = "Sessions/Done"
                elif status == "Failed":
                    directory = "Sessions/Failed"
                else:
                    directory = "Sessions/Available"
                    
                filepath = os.path.join(directory, filename)
                
                # Save to file
                with open(filepath, 'w') as f:
                    json.dump(session_data, f, indent=4)
                    
                self.logger.info(f"Session saved: {filepath}")
                return filepath
                
            except Exception as e:
                self.logger.error(f"Failed to save session: {e}")
                raise
            
    def load_session(self, filename: str, directory: str = "Sessions/Available") -> Optional[Dict[str, Any]]:
        """Load a session from file."""
        try:
            if not filename.endswith('.json'):
                filename += '.json'
                
            filepath = os.path.join(directory, filename)
            
            if not os.path.exists(filepath):
                # Try to find in all directories
                for subdir in ["Available", "ToDo", "Done", "Running", "Failed"]:
                    test_path = os.path.join("Sessions", subdir, filename)
                    if os.path.exists(test_path):
                        filepath = test_path
                        break
                else:
                    self.logger.warning(f"Session file not found: {filename}")
                    return None
                    
            with open(filepath, 'r') as f:
                session_data = json.load(f)
                
            self.logger.info(f"Session loaded: {filepath}")
            return session_data
            
        except Exception as e:
            self.logger.error(f"Failed to load session: {e}")
            raise
            
    def get_available_sessions(self) -> List[str]:
        """Get list of available session files."""
        try:
            directory = "Sessions/Available"
            if not os.path.exists(directory):
                return []
                
            sessions = []
            for filename in os.listdir(directory):
                if filename.endswith('.json'):
                    sessions.append(filename[:-5])  # Remove .json extension
                    
            return sorted(sessions)
            
        except Exception as e:
            self.logger.error(f"Failed to get available sessions: {e}")
            return []
            
    def get_scheduled_sessions(self) -> List[Dict[str, Any]]:
        """Get list of scheduled sessions from ToDo directory."""
        try:
            directory = "Sessions/ToDo"
            sessions = []
            
            if not os.path.exists(directory):
                return sessions
                
            for filename in os.listdir(directory):
                if filename.endswith('.json'):
                    session_data = self.load_session(filename, directory)
                    if session_data:
                        sessions.append(session_data)
                        
            # Sort by start time
            sessions.sort(key=lambda x: x.get("start_time", ""))
            return sessions
            
        except Exception as e:
            self.logger.error(f"Failed to get scheduled sessions: {e}")
            return []
            
    def move_session(self, filename: str, from_status: str, to_status: str) -> bool:
        """Move a session between directories."""
        try:
            filename = filename.replace(" ", "_")

            if not filename.endswith('.json'):
                filename += '.json'
                
            status_dirs = {
                "Available": "Sessions/Available",
                "ToDo": "Sessions/ToDo",
                "Running": "Sessions/Running", 
                "Done": "Sessions/Done",
                "Failed": "Sessions/Failed"
            }
            
            from_dir = status_dirs.get(from_status)
            to_dir = status_dirs.get(to_status)
            
            if not from_dir or not to_dir:
                raise ValueError(f"Invalid status: {from_status} or {to_status}")
                
            from_path = os.path.join(from_dir, filename)
            to_path = os.path.join(to_dir, filename)
            
            if not os.path.exists(from_path):
                raise FileNotFoundError(f"Session file not found: {from_path}")
                
            # Update status in session data
            session_data = self.load_session(filename, from_dir)
            if session_data:
                session_data["status"] = to_status
                session_data["status_changed"] = datetime.datetime.now().isoformat()
                
                # Save to new location
                with open(to_path, 'w') as f:
                    json.dump(session_data, f, indent=4)
                    
                # Remove from old location
                os.remove(from_path)
                
                self.logger.info(f"Session moved from {from_status} to {to_status}: {filename}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to move session: {e}")
            return False
            
    def delete_session(self, filename: str, directory: str = "Sessions/Available") -> bool:
        """Delete a session file."""
        try:
            filename = filename.replace(" ", "_")

            if not filename.endswith('.json'):
                filename += '.json'

            filepath = os.path.join(directory, filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                self.logger.info(f"Session deleted: {filepath}")
                return True
            else:
                self.logger.warning(f"Session file not found for deletion: {filepath}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to delete session: {e}")
            return False
            
    def duplicate_session(self, source_filename: str, new_name: str) -> bool:
        """Duplicate a session with a new name."""
        try:
            session_data = self.load_session(source_filename)
            if not session_data:
                return False
                
            # Update session data for duplicate
            session_data["session_name"] = new_name
            session_data["created_date"] = datetime.datetime.now().isoformat()
            
            # Save as new session
            self.save_session(session_data)
            self.logger.info(f"Session duplicated: {source_filename} -> {new_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to duplicate session: {e}")
            return False
            
    def add_to_schedule(self, session_data: Dict[str, Any]) -> bool:
        """Add a session to the schedule (ToDo directory)."""
        try:
            # Save to ToDo directory
            self.save_session(session_data, "ToDo")
            self.logger.info(f"Session added to schedule: {session_data.get('session_name', 'Unknown')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add session to schedule: {e}")
            return False
            
    def get_session_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all sessions with a specific status."""
        try:
            status_dirs = {
                "Available": "Sessions/Available",
                "ToDo": "Sessions/ToDo", 
                "Running": "Sessions/Running",
                "Done": "Sessions/Done",
                "Failed": "Sessions/Failed"
            }
            
            directory = status_dirs.get(status)
            if not directory or not os.path.exists(directory):
                return []
                
            sessions = []
            for filename in os.listdir(directory):
                if filename.endswith('.json'):
                    session_data = self.load_session(filename, directory)
                    if session_data:
                        sessions.append(session_data)
                        
            return sessions
            
        except Exception as e:
            self.logger.error(f"Failed to get sessions by status {status}: {e}")
            return []
            
    def cleanup_old_sessions(self, days: int = 30):
        """Clean up old completed sessions."""
        try:
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
            
            for status in ["Done", "Failed"]:
                directory = f"Sessions/{status}"
                if not os.path.exists(directory):
                    continue
                    
                for filename in os.listdir(directory):
                    if filename.endswith('.json'):
                        filepath = os.path.join(directory, filename)
                        
                        # Check file modification time
                        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                        
                        if mod_time < cutoff_date:
                            # Archive or delete old session
                            archive_dir = f"Sessions/Archived/{status}"
                            if not os.path.exists(archive_dir):
                                os.makedirs(archive_dir)
                                
                            archive_path = os.path.join(archive_dir, filename)
                            shutil.move(filepath, archive_path)
                            
                            self.logger.info(f"Archived old session: {filename}")
                            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old sessions: {e}")
            
    def get_running_sessions_count(self) -> int:
        """Get count of sessions currently in Running status."""
        try:
            running_sessions = self.get_session_by_status("Running")
            return len(running_sessions)
        except Exception as e:
            self.logger.error(f"Failed to get running sessions count: {e}")
            return 0
