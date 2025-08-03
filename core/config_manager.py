"""
Configuration manager for the Dwarf3 Telescope Scheduler.
"""

import json
import os
import logging
from typing import Dict, Any

class ConfigManager:
    """Manages application configuration settings."""
    
    def __init__(self, config_file="config/settings.json"):
        self.config_file = config_file
        self.logger = logging.getLogger(__name__)
        self.config_dir = os.path.dirname(config_file)
        
        # Ensure config directory exists
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        self.settings = self.load_settings()
        
    def get_default_settings(self) -> Dict[str, Any]:
        """Get default configuration settings."""
        return {
            "telescope": {
                "ip": "192.168.4.1",
                "port": 80,
                "timeout": 10,
                "auto_connect": True,
                "camera_model": "Dwarf3",
                "mount_type": "Alt-Az"
            },
            "location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "elevation": 10,
                "name": "New York, NY",
                "timezone": "America/New_York",
                "utc_offset": -5
            },
            "defaults": {
                "frame_count": 50,
                "exposure_time": 30,
                "gain": 100,
                "binning": "1x1",
                "session_wait": 60,
                "settling_time": 10,
                "focus_timeout": 300
            },
            "advanced": {
                "log_level": "INFO",
                "log_to_file": True,
                "auto_archive": True,
                "archive_days": 30,
                "auto_backup": False,
                "backup_location": ""
            }
        }
        
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from configuration file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    settings = json.load(f)
                self.logger.info("Settings loaded from file")
                return settings
            else:
                self.logger.info("No config file found, using defaults")
                return self.get_default_settings()
        except Exception as e:
            self.logger.error(f"Failed to load settings: {e}")
            return self.get_default_settings()
            
    def save_settings(self, settings: Dict[str, Any] = None):
        """Save settings to configuration file."""
        try:
            if settings:
                self.settings = settings
                
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            self.logger.info("Settings saved to file")
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            raise
            
    def get_setting(self, category: str, key: str, default=None):
        """Get a specific setting value."""
        return self.settings.get(category, {}).get(key, default)
        
    def set_setting(self, category: str, key: str, value):
        """Set a specific setting value."""
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category][key] = value
        
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings."""
        return self.settings.copy()
        
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.settings = self.get_default_settings()
        self.save_settings()
        self.logger.info("Settings reset to defaults")
        
    def get_telescope_settings(self) -> Dict[str, Any]:
        """Get telescope-specific settings."""
        return self.settings.get("telescope", {})
        
    def get_location_settings(self) -> Dict[str, Any]:
        """Get location-specific settings."""
        return self.settings.get("location", {})
        
    def get_default_capture_settings(self) -> Dict[str, Any]:
        """Get default capture settings."""
        return self.settings.get("defaults", {})
