"""
Configuration manager for the Dwarf3 Telescope Scheduler.
"""

import configparser
import os
import logging
from typing import Dict, Any

class ConfigManager:
    """Manages application configuration settings."""
    
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.logger = logging.getLogger(__name__)
        self.config = configparser.ConfigParser()
        
        # Load configuration
        self.load_settings()
        
    def get_default_settings(self) -> configparser.ConfigParser:
        """Get default configuration settings."""
        config = configparser.ConfigParser()
        
        # CONFIG section - all settings consolidated here
        config['CONFIG'] = {
            # Location settings
            'address': 'New York, NY',
            'longitude': '-74.006',
            'latitude': '40.7128',
            'timezone': 'America/New_York',
            'utc_offset': '-5',
            
            # Telescope connection settings
            'telescope_ip': '192.168.4.1',
            'telescope_port': '9900',
            'telescope_timeout': '10',
            'auto_connect': 'false',
            
            # Stellarium connection settings
            'stellarium_ip': '192.168.1.20',
            'stellarium_port': '8090',
            
            # Device settings
            'device_type': 'Dwarf 3 Tele Lens',
            'camera_model': 'Dwarf3',
            'mount_type': 'Equatorial',
            
            # Default capture settings
            'exposure': '30',
            'gain': '60',
            'count': '50',
            'binning': '0',
            'ircut': '1',
            
            # Session settings
            'session_wait': '60',
            'settling_time': '10',
            'focus_timeout': '300',
            
            # Bluetooth/WiFi settings
            'ble_psd': 'DWARF_12345678',
            'ble_sta_ssid': '',
            'ble_sta_pwd': '',
            
            # Advanced settings
            'log_level': 'INFO',
            'log_to_file': 'true',
            'auto_archive': 'true',
            'archive_days': '30',
            'day_change_hour': '18'
        }
        
        return config
        
    def load_settings(self):
        """Load settings from configuration file."""
        try:
            if os.path.exists(self.config_file):
                self.config.read(self.config_file)
                self.logger.info("Settings loaded from file")
                
                # Migrate old format if needed
                self._migrate_config_if_needed()
            else:
                self.logger.info("No config file found, using defaults")
                self.config = self.get_default_settings()
                self.save_settings()
        except Exception as e:
            self.logger.error(f"Failed to load settings: {e}")
            self.config = self.get_default_settings()
    
    def _migrate_config_if_needed(self):
        """Migrate old configuration format to new format if needed."""
        try:
            migration_needed = False
            
            # Check if old sections exist (telescope, stellarium, location, defaults, advanced, history, device)
            old_sections = ['telescope', 'stellarium', 'location', 'defaults', 'advanced', 'history', 'device', 'DEVICE', 'SETTINGS']
            
            for section in old_sections:
                if self.config.has_section(section):
                    migration_needed = True
                    break
            
            if migration_needed:
                self.logger.info("Migrating configuration to new format...")
                
                # Create new CONFIG section if it doesn't exist
                if not self.config.has_section('CONFIG'):
                    self.config.add_section('CONFIG')
                
                # Migrate telescope settings to CONFIG
                if self.config.has_section('telescope'):
                    for key, value in self.config.items('telescope'):
                        if key == 'ip':
                            self.config.set('CONFIG', 'telescope_ip', value)
                        elif key == 'port':
                            self.config.set('CONFIG', 'telescope_port', value)
                        elif key == 'timeout':
                            self.config.set('CONFIG', 'telescope_timeout', value)
                        elif key == 'auto_connect':
                            self.config.set('CONFIG', 'auto_connect', value)
                
                # Migrate stellarium settings to CONFIG
                if self.config.has_section('stellarium'):
                    for key, value in self.config.items('stellarium'):
                        if key == 'ip':
                            self.config.set('CONFIG', 'stellarium_ip', value)
                        elif key == 'port':
                            self.config.set('CONFIG', 'stellarium_port', value)
                
                # Migrate device settings to CONFIG
                if self.config.has_section('device') or self.config.has_section('DEVICE'):
                    device_section = 'device' if self.config.has_section('device') else 'DEVICE'
                    for key, value in self.config.items(device_section):
                        self.config.set('CONFIG', key, value)
                
                # Migrate location settings to CONFIG
                if self.config.has_section('location'):
                    for key, value in self.config.items('location'):
                        if key == 'name':
                            self.config.set('CONFIG', 'address', value)
                        else:
                            self.config.set('CONFIG', key, value)
                
                # Migrate defaults settings to CONFIG
                if self.config.has_section('defaults'):
                    for key, value in self.config.items('defaults'):
                        if key == 'frame_count':
                            self.config.set('CONFIG', 'count', value)
                        elif key == 'exposure_time':
                            self.config.set('CONFIG', 'exposure', value)
                        else:
                            self.config.set('CONFIG', key, value)
                
                # Migrate advanced settings to CONFIG
                if self.config.has_section('advanced'):
                    for key, value in self.config.items('advanced'):
                        self.config.set('CONFIG', key, value)
                
                # Migrate history settings to CONFIG
                if self.config.has_section('history'):
                    for key, value in self.config.items('history'):
                        self.config.set('CONFIG', key, value)
                
                # Remove old sections
                for section in old_sections:
                    if self.config.has_section(section):
                        self.config.remove_section(section)
                
                # Save migrated config
                self.save_settings()
                self.logger.info("Configuration migration completed")
        
        except Exception as e:
            self.logger.error(f"Failed to migrate configuration: {e}")
            
    def save_settings(self, settings=None):
        """Save settings to configuration file."""
        try:
            # If settings dict is provided, update the config object
            if settings:
                # Convert dictionary back to ConfigParser format
                for section_name, section_data in settings.items():
                    if not self.config.has_section(section_name):
                        self.config.add_section(section_name)
                    for key, value in section_data.items():
                        self.config.set(section_name, key, str(value))
            
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            self.logger.info("Settings saved to file")
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            raise
            
    def get_setting(self, section: str, key: str, default=None):
        """Get a specific setting value with type conversion."""
        try:
            value = self.config.get(section, key)
            
            # Handle boolean values
            if value.lower() in ('true', 'false'):
                return value.lower() == 'true'
            
            # Try to convert to number if possible
            try:
                if '.' in value:
                    return float(value)
                else:
                    return int(value)
            except ValueError:
                return value
                
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
        
    def set_setting(self, section: str, key: str, value):
        """Set a specific setting value."""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        
    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Get all settings as a dictionary."""
        settings = {}
        for section_name in self.config.sections():
            settings[section_name] = {}
            for key, value in self.config.items(section_name):
                # Convert values to appropriate types
                if value.lower() in ('true', 'false'):
                    settings[section_name][key] = value.lower() == 'true'
                else:
                    try:
                        if '.' in value:
                            settings[section_name][key] = float(value)
                        else:
                            settings[section_name][key] = int(value)
                    except ValueError:
                        settings[section_name][key] = value
        return settings
        
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.config = self.get_default_settings()
        self.save_settings()
        self.logger.info("Settings reset to defaults")
        
    def get_telescope_settings(self) -> Dict[str, Any]:
        """Get telescope-specific settings."""
        return {
            'ip': self.get_setting('CONFIG', 'telescope_ip', '192.168.4.1'),
            'port': self.get_setting('CONFIG', 'telescope_port', 9900),
            'timeout': self.get_setting('CONFIG', 'telescope_timeout', 10),
            'auto_connect': self.get_setting('CONFIG', 'auto_connect', False),
            'camera_model': self.get_setting('CONFIG', 'camera_model', 'Dwarf3'),
            'mount_type': self.get_setting('CONFIG', 'mount_type', 'Equatorial'),
            'device_type': self.get_setting('CONFIG', 'device_type', 'Dwarf 3 Tele Lens')
        }
        
    def get_location_settings(self) -> Dict[str, Any]:
        """Get location-specific settings."""
        return {
            'name': self.get_setting('CONFIG', 'address', 'New York, NY'),
            'latitude': self.get_setting('CONFIG', 'latitude', 40.7128),
            'longitude': self.get_setting('CONFIG', 'longitude', -74.006),
            'timezone': self.get_setting('CONFIG', 'timezone', 'America/New_York'),
            'utc_offset': self.get_setting('CONFIG', 'utc_offset', -5)
        }
        
    def get_default_capture_settings(self) -> Dict[str, Any]:
        """Get default capture settings."""
        return {
            'frame_count': self.get_setting('CONFIG', 'count', 50),
            'exposure_time': self.get_setting('CONFIG', 'exposure', 30.0),
            'gain': self.get_setting('CONFIG', 'gain', 100),
            'binning': '1x1' if self.get_setting('CONFIG', 'binning', 0) == 0 else f"{self.get_setting('CONFIG', 'binning', 1)}x{self.get_setting('CONFIG', 'binning', 1)}",
            'session_wait': self.get_setting('CONFIG', 'session_wait', 60),
            'settling_time': self.get_setting('CONFIG', 'settling_time', 10),
            'focus_timeout': self.get_setting('CONFIG', 'focus_timeout', 300)
        }

    def get_stellarium_settings(self) -> Dict[str, Any]:
        """Get Stellarium connection settings."""
        return {
            'ip': self.get_setting('CONFIG', 'stellarium_ip', '192.168.1.20'),
            'port': self.get_setting('CONFIG', 'stellarium_port', 8090)
        }
    
    def get_advanced_settings(self) -> Dict[str, Any]:
        """Get advanced settings."""
        return {
            'log_level': self.get_setting('CONFIG', 'log_level', 'INFO'),
            'log_to_file': self.get_setting('CONFIG', 'log_to_file', True),
            'auto_archive': self.get_setting('CONFIG', 'auto_archive', True),
            'archive_days': self.get_setting('CONFIG', 'archive_days', 30),
            'day_change_hour': self.get_setting('CONFIG', 'day_change_hour', 18)
        }
