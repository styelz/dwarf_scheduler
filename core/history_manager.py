"""
History manager for tracking completed telescope sessions.
"""

import csv
import os
import datetime
import logging
from typing import List, Dict, Any, Optional

class HistoryManager:
    """Manages session history tracking and statistics."""
    
    def __init__(self, history_file="Sessions/History/session_history.csv"):
        self.history_file = history_file
        self.logger = logging.getLogger(__name__)
        
        # Ensure history directory exists
        history_dir = os.path.dirname(history_file)
        if not os.path.exists(history_dir):
            os.makedirs(history_dir)
            
        # Initialize CSV file if it doesn't exist
        self._initialize_csv()
        
    def _initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.history_file):
            headers = [
                "date", "time", "session_name", "target_name", "status",
                "ra", "dec", "frame_count", "frames_captured", "exposure_time",
                "total_exposure", "gain", "binning", "filter", "duration",
                "file_size", "auto_focus", "plate_solve", "auto_guide",
                "temperature", "humidity", "seeing", "notes", "error_message"
            ]
            
            with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                
            self.logger.info(f"Initialized history file: {self.history_file}")
            
    def add_record(self, record: Dict[str, Any]):
        """Add a session record to history."""
        try:
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
            
            # Append to CSV file
            with open(self.history_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row_data)
                
            self.logger.info(f"Added history record for session: {record.get('session_name', 'Unknown')}")
            
        except Exception as e:
            self.logger.error(f"Failed to add history record: {e}")
            raise
            
    def get_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get session history records."""
        try:
            if not os.path.exists(self.history_file):
                return []
                
            records = []
            with open(self.history_file, 'r', encoding='utf-8') as f:
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
            if not os.path.exists(self.history_file):
                return None
                
            with open(self.history_file, 'r', encoding='utf-8') as f:
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
            if not os.path.exists(self.history_file):
                return self._empty_statistics()
                
            with open(self.history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                records = list(reader)
                
            if not records:
                return self._empty_statistics()
                
            # Calculate basic statistics
            total_sessions = len(records)
            successful_sessions = len([r for r in records if r["status"] == "Completed"])
            
            # Calculate total frames and exposure
            total_frames = sum(int(r["frames_captured"] or 0) for r in records)
            total_exposure_seconds = sum(float(r["total_exposure"] or 0) for r in records)
            total_exposure_hours = total_exposure_seconds / 3600
            
            # Find most captured target
            target_counts = {}
            for record in records:
                target = record["target_name"]
                target_counts[target] = target_counts.get(target, 0) + 1
                
            most_captured_target = max(target_counts.items(), key=lambda x: x[1])[0] if target_counts else "-"
            
            # Calculate average duration (placeholder)
            avg_duration_minutes = 45  # Would calculate from actual duration data
            
            # Monthly breakdown
            monthly_stats = self._calculate_monthly_stats(records)
            
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
            # Simply copy the existing file
            import shutil
            shutil.copy2(self.history_file, filename)
            self.logger.info(f"History exported to: {filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to export history: {e}")
            raise
            
    def clear_history(self):
        """Clear all history data."""
        try:
            # Backup current file before clearing
            backup_file = f"{self.history_file}.backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(self.history_file):
                import shutil
                shutil.copy2(self.history_file, backup_file)
                
            # Reinitialize empty CSV file
            self._initialize_csv()
            self.logger.info("History cleared (backup created)")
            
        except Exception as e:
            self.logger.error(f"Failed to clear history: {e}")
            raise
            
    def delete_entry(self, date: str, time: str, target: str):
        """Delete a specific history entry."""
        try:
            if not os.path.exists(self.history_file):
                return
                
            # Read all records
            records = []
            with open(self.history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                records = [row for row in reader 
                          if not (row["date"] == date and 
                                 row["time"] == time and 
                                 row["target_name"] == target)]
                                 
            # Write back without the deleted record
            with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
                if records:
                    fieldnames = records[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(records)
                else:
                    # File is empty, reinitialize
                    self._initialize_csv()
                    
            self.logger.info(f"Deleted history entry: {target} on {date} {time}")
            
        except Exception as e:
            self.logger.error(f"Failed to delete history entry: {e}")
            raise
