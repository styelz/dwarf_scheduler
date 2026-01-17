"""
History manager for tracking completed telescope sessions.
"""

import csv
import os
import datetime
import logging
import glob
from typing import List, Dict, Any, Optional

class HistoryManager:
    """Manages session history tracking and statistics with daily file rotation."""
    
    def __init__(self, config_manager=None, history_dir="Sessions/History"):
        self.config_manager = config_manager
        self.history_dir = history_dir
        self.logger = logging.getLogger(__name__)
        self.active_files = None  # None means all files, list means specific files
        
        # Ensure history directory exists
        if not os.path.exists(history_dir):
            os.makedirs(history_dir)
            
        # CSV headers
        self.csv_headers = [
            "date", "time", "session_name", "target_name", "status",
            "ra", "dec", "frame_count", "frames_captured", "exposure_time",
            "total_exposure", "gain", "binning", "filter", "duration",
            "file_size", "auto_focus", "plate_solve", "auto_guide",
            "temperature", "humidity", "seeing", "notes", "error_message"
        ]
            
    def _get_day_change_hour(self):
        """Get the hour when the day changes (default 18:00 / 6 PM)."""
        if self.config_manager:
            return self.config_manager.get_setting("CONFIG", "day_change_hour", 18)
        return 18
        
    def _get_session_date(self, timestamp=None):
        """Get the session date considering day change hour."""
        if timestamp is None:
            timestamp = datetime.datetime.now()
        elif isinstance(timestamp, str):
            timestamp = datetime.datetime.fromisoformat(timestamp)
            
        day_change_hour = self._get_day_change_hour()
        
        # If before day change hour, use previous day
        if timestamp.hour < day_change_hour:
            session_date = timestamp.date() - datetime.timedelta(days=1)
        else:
            session_date = timestamp.date()
            
        return session_date.strftime("%Y-%m-%d")
        
    def _get_history_filename(self, session_date):
        """Get history filename for a specific date."""
        return os.path.join(self.history_dir, f"session_history_{session_date}.csv")
        
    def _initialize_csv(self, filename):
        """Initialize CSV file with headers if it doesn't exist."""
        if not os.path.exists(filename):
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.csv_headers)
                
            self.logger.info(f"Initialized history file: {filename}")
            
    def get_history_files(self):
        """Get list of available history files with metadata."""
        try:
            pattern = os.path.join(self.history_dir, "session_history_*.csv")
            files = glob.glob(pattern)
            
            file_list = []
            for file_path in sorted(files, reverse=True):  # Newest first
                filename = os.path.basename(file_path)
                
                # Extract date from filename
                date_part = filename.replace("session_history_", "").replace(".csv", "")
                
                # Get file stats
                stat = os.stat(file_path)
                size = f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1024*1024 else f"{stat.st_size / (1024*1024):.1f} MB"
                modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                
                # Count sessions in file
                session_count = 0
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        next(reader)  # Skip header
                        session_count = sum(1 for _ in reader)
                except (IOError, csv.Error) as e:
                    self.logger.warning(f"Could not count sessions in {filename}: {e}")
                    session_count = 0
                
                file_list.append({
                    'filename': filename,
                    'filepath': file_path,
                    'date': date_part,
                    'sessions': session_count,
                    'size': size,
                    'modified': modified
                })
                
            return file_list
            
        except Exception as e:
            self.logger.error(f"Failed to get history files: {e}")
            return []
            
    def set_active_files(self, file_list):
        """Set which files to load history from. None means all files."""
        self.active_files = file_list
        
    def delete_history_file(self, filename):
        """Delete a specific history file."""
        try:
            file_path = os.path.join(self.history_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"Deleted history file: {filename}")
            else:
                raise FileNotFoundError(f"History file not found: {filename}")
                
        except Exception as e:
            self.logger.error(f"Failed to delete history file {filename}: {e}")
            raise
            
    def add_record(self, record: Dict[str, Any]):
        """Add a session record to history."""
        try:
            # Determine which file to use based on session date
            session_date = self._get_session_date(record.get("timestamp"))
            history_file = self._get_history_filename(session_date)
            
            # Initialize file if needed
            self._initialize_csv(history_file)
            
            # Prepare record data
            coordinates = record.get("coordinates", {})
            capture_settings = record.get("capture_settings", {})
            calibration = record.get("calibration", {})
            
            # Calculate derived values
            frame_count = capture_settings.get("frame_count", 0)
            frames_captured = record.get("frames_captured", frame_count)
            exposure_time = capture_settings.get("exposure_time", 0)
            total_exposure = frames_captured * exposure_time
            
            # Prepare CSV row
            row_data = [
                record.get("date", datetime.datetime.now().strftime("%Y-%m-%d")),
                record.get("time", datetime.datetime.now().strftime("%H:%M:%S")),
                record.get("session_name", ""),
                record.get("target_name", ""),
                record.get("status", ""),
                coordinates.get("ra", ""),
                coordinates.get("dec", ""),
                frame_count,
                frames_captured,
                exposure_time,
                total_exposure,
                capture_settings.get("gain", ""),
                capture_settings.get("binning", ""),
                capture_settings.get("filter", ""),
                record.get("duration", ""),
                record.get("file_size", ""),
                calibration.get("auto_focus", False),
                calibration.get("plate_solve", False),
                calibration.get("auto_guide", False),
                record.get("temperature", ""),
                record.get("humidity", ""),
                record.get("seeing", ""),
                record.get("notes", ""),
                record.get("error_message", "")
            ]
            
            # Append to appropriate CSV file
            with open(history_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row_data)
                
            self.logger.info(f"Added history record for session: {record.get('session_name', 'Unknown')} to {os.path.basename(history_file)}")
            
        except Exception as e:
            self.logger.error(f"Failed to add history record: {e}")
            raise
            
    def get_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get session history records from active files."""
        try:
            records = []
            
            # Determine which files to read
            if self.active_files is None:
                # Read all files
                history_files = self.get_history_files()
                file_paths = [f['filepath'] for f in history_files]
            else:
                # Read only specified files
                file_paths = [os.path.join(self.history_dir, f) for f in self.active_files]
                file_paths = [f for f in file_paths if os.path.exists(f)]
            
            # Read records from all relevant files
            for file_path in file_paths:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        
                        for row in reader:
                            # Convert row to more convenient format
                            record = {
                                "date": row["date"],
                                "time": row["time"],
                                "target": row["target_name"],
                                "status": row["status"],
                                "frames_captured": row["frames_captured"],
                                "exposure_time": row["exposure_time"],
                                "duration": row["duration"],
                                "file_size": row["file_size"]
                            }
                            records.append(record)
                except Exception as e:
                    self.logger.warning(f"Failed to read history file {file_path}: {e}")
                    continue
                    
            # Sort by date/time (newest first)
            records.sort(key=lambda x: f"{x['date']} {x['time']}", reverse=True)
            
            if limit:
                records = records[:limit]
                
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to get history: {e}")
            return []
            
    def get_filtered_history(self, date_from: str = None, date_to: str = None,
                           target_filter: str = None, status_filter: str = None) -> List[Dict[str, Any]]:
        """Get filtered history records."""
        try:
            all_records = self.get_history()
            filtered_records = []
            
            for record in all_records:
                # Date filter
                if date_from and record["date"] < date_from:
                    continue
                if date_to and record["date"] > date_to:
                    continue
                    
                # Target filter
                if target_filter and target_filter.lower() not in record["target"].lower():
                    continue
                    
                # Status filter
                if status_filter and status_filter != "All" and record["status"] != status_filter:
                    continue
                    
                filtered_records.append(record)
                
            return filtered_records
            
        except Exception as e:
            self.logger.error(f"Failed to filter history: {e}")
            return []
            
    def get_session_details(self, date: str, time: str, target: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific session."""
        try:
            # Get list of files to process
            if self.active_files is not None:
                files_to_process = self.active_files
            else:
                history_files = self.get_history_files()
                files_to_process = [f['filename'] for f in history_files]
            
            # Search through all active history files
            for history_file in files_to_process:
                file_path = os.path.join(self.history_dir, history_file)
                if not os.path.exists(file_path):
                    continue
                    
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    
                    for row in reader:
                        if (row["date"] == date and 
                            row["time"] == time and 
                            row["target_name"] == target):
                            
                            # Return full session details
                            return {
                                "session_name": row["session_name"],
                                "ra": row["ra"],
                                "dec": row["dec"],
                                "total_exposure": row["total_exposure"],
                                "gain": row["gain"],
                                "binning": row["binning"],
                                "filter": row["filter"],
                                "auto_focus": row["auto_focus"],
                                "plate_solve": row["plate_solve"],
                                "auto_guide": row["auto_guide"],
                                "temperature": row["temperature"],
                                "humidity": row["humidity"],
                                "seeing": row["seeing"],
                                "notes": row["notes"]
                            }
                        
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get session details: {e}")
            return None
            
    def get_statistics(self) -> Dict[str, Any]:
        """Calculate and return session statistics."""
        try:
            all_records = []
            
            # Get list of files to process
            if self.active_files is not None:
                files_to_process = self.active_files
            else:
                history_files = self.get_history_files()
                files_to_process = [f['filename'] for f in history_files]
            
            # Collect records from all active history files
            for history_file in files_to_process:
                file_path = os.path.join(self.history_dir, history_file)
                if not os.path.exists(file_path):
                    continue
                    
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    all_records.extend(list(reader))
                
            if not all_records:
                return self._empty_statistics()
                
            # Calculate basic statistics
            total_sessions = len(all_records)
            successful_sessions = len([r for r in all_records if r["status"] == "Completed"])
            
            # Calculate total frames and exposure
            total_frames = sum(int(r["frames_captured"] or 0) for r in all_records)
            total_exposure_seconds = sum(float(r["total_exposure"] or 0) for r in all_records)
            total_exposure_hours = total_exposure_seconds / 3600
            
            # Find most captured target
            target_counts = {}
            for record in all_records:
                target = record["target_name"]
                target_counts[target] = target_counts.get(target, 0) + 1
                
            most_captured_target = max(target_counts.items(), key=lambda x: x[1])[0] if target_counts else "-"
            
            # Calculate average duration (placeholder)
            avg_duration_minutes = 45  # Would calculate from actual duration data
            
            # Monthly breakdown
            monthly_stats = self._calculate_monthly_stats(all_records)
            
            return {
                "total_sessions": total_sessions,
                "successful_sessions": successful_sessions,
                "total_frames": total_frames,
                "total_exposure_hours": total_exposure_hours,
                "most_captured_target": most_captured_target,
                "avg_duration_minutes": avg_duration_minutes,
                "monthly_breakdown": monthly_stats
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate statistics: {e}")
            return self._empty_statistics()
            
    def _empty_statistics(self) -> Dict[str, Any]:
        """Return empty statistics structure."""
        return {
            "total_sessions": 0,
            "successful_sessions": 0,
            "total_frames": 0,
            "total_exposure_hours": 0,
            "most_captured_target": "-",
            "avg_duration_minutes": 0,
            "monthly_breakdown": []
        }
        
    def _calculate_monthly_stats(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate monthly breakdown statistics."""
        monthly_data = {}
        
        for record in records:
            try:
                date_obj = datetime.datetime.strptime(record["date"], "%Y-%m-%d")
                month_key = date_obj.strftime("%Y-%m")
                
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "sessions": 0,
                        "frames": 0,
                        "exposure_hours": 0,
                        "successful": 0
                    }
                    
                monthly_data[month_key]["sessions"] += 1
                monthly_data[month_key]["frames"] += int(record["frames_captured"] or 0)
                monthly_data[month_key]["exposure_hours"] += float(record["total_exposure"] or 0) / 3600
                
                if record["status"] == "Completed":
                    monthly_data[month_key]["successful"] += 1
                    
            except (ValueError, KeyError):
                continue
                
        # Convert to list format with success rate
        monthly_list = []
        for month, data in sorted(monthly_data.items(), reverse=True):
            success_rate = (data["successful"] / data["sessions"] * 100) if data["sessions"] > 0 else 0
            
            monthly_list.append({
                "month": month,
                "sessions": data["sessions"],
                "frames": data["frames"],
                "exposure_hours": data["exposure_hours"],
                "success_rate": success_rate
            })
            
        return monthly_list[:12]  # Return last 12 months
        
    def export_to_csv(self, filename: str):
        """Export history to a new CSV file."""
        try:
            # Get list of files to process
            if self.active_files is not None:
                files_to_process = self.active_files
            else:
                history_files = self.get_history_files()
                files_to_process = [f['filename'] for f in history_files]
            
            # Collect all records from active files
            all_records = []
            for history_file in files_to_process:
                file_path = os.path.join(self.history_dir, history_file)
                if not os.path.exists(file_path):
                    continue
                    
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    all_records.extend(list(reader))
            
            # Write to new file
            if all_records:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = all_records[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_records)
                    
            self.logger.info(f"History exported to: {filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to export history: {e}")
            raise
            
    def clear_history(self):
        """Clear all history data."""
        try:
            # Backup all current files before clearing
            backup_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            history_files = self.get_history_files()
            for file_info in history_files:
                file_path = file_info['filepath']
                if os.path.exists(file_path):
                    backup_file = f"{file_path}.backup_{backup_timestamp}"
                    import shutil
                    shutil.copy2(file_path, backup_file)
                    # Remove the original file
                    os.remove(file_path)
                
            # Reset active files to current day only
            current_session_date = self._get_session_date()
            current_file = f"session_history_{current_session_date}.csv"
            self.active_files = [current_file]
            
            # Initialize empty CSV file for current day
            current_file_path = self._get_history_filename(current_session_date)
            self._initialize_csv(current_file_path)
            self.logger.info("History cleared (backups created)")
            
        except Exception as e:
            self.logger.error(f"Failed to clear history: {e}")
            raise
            
    def delete_entry(self, date: str, time: str, target: str):
        """Delete a specific history entry."""
        try:
            # Get list of files to process
            if self.active_files is not None:
                files_to_process = self.active_files
            else:
                history_files = self.get_history_files()
                files_to_process = [f['filename'] for f in history_files]
            
            # Search through all active history files
            for history_file in files_to_process:
                file_path = os.path.join(self.history_dir, history_file)
                if not os.path.exists(file_path):
                    continue
                    
                # Read all records from this file
                records = []
                found_entry = False
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if (row["date"] == date and 
                            row["time"] == time and 
                            row["target_name"] == target):
                            found_entry = True
                            # Skip this record (delete it)
                            continue
                        records.append(row)
                
                if found_entry:
                    # Write back without the deleted record
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        if records:
                            fieldnames = records[0].keys()
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(records)
                        else:
                            # File is empty, reinitialize
                            self._initialize_csv(file_path)
                            
                    self.logger.info(f"Deleted history entry: {target} on {date} {time}")
                    return
                    
            self.logger.warning(f"History entry not found: {target} on {date} {time}")
            
        except Exception as e:
            self.logger.error(f"Failed to delete history entry: {e}")
            raise
