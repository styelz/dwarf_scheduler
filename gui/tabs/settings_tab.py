"""
Settings tab for configuring application preferences and telescope settings.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging

class SettingsTab:
    """Tab for application and telescope settings."""
    
    def __init__(self, parent, config_manager):
        self.parent = parent
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        self.create_widgets()
        self.load_settings()
        
    def create_widgets(self):
        """Create and layout widgets for the settings tab."""
        self.frame = ttk.Frame(self.parent)
        
        # Create notebook for different setting categories
        settings_notebook = ttk.Notebook(self.frame)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Telescope Connection tab
        telescope_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(telescope_frame, text="Telescope")
        self.create_telescope_settings(telescope_frame)
        
        # Location tab
        location_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(location_frame, text="Location")
        self.create_location_settings(location_frame)
        
        # Defaults tab
        defaults_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(defaults_frame, text="Defaults")
        self.create_default_settings(defaults_frame)
        
        # Advanced tab
        advanced_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(advanced_frame, text="Advanced")
        self.create_advanced_settings(advanced_frame)
        
        # Save/Reset buttons
        button_frame = ttk.Frame(self.frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            button_frame, 
            text="Save Settings", 
            command=self.save_settings
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Reset to Defaults", 
            command=self.reset_defaults
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Test Connection", 
            command=self.test_connection
        ).pack(side=tk.RIGHT)
        
    def create_telescope_settings(self, parent):
        """Create telescope connection settings."""
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Connection settings
        conn_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding=10)
        conn_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Dwarf IP Address
        ttk.Label(conn_frame, text="Dwarf IP Address:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.dwarf_ip_var = tk.StringVar(value="192.168.4.1")
        ttk.Entry(conn_frame, textvariable=self.dwarf_ip_var, width=20).grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # Port
        ttk.Label(conn_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.port_var = tk.StringVar(value="80")
        ttk.Entry(conn_frame, textvariable=self.port_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        
        # Timeout
        ttk.Label(conn_frame, text="Connection Timeout:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.timeout_var = tk.StringVar(value="10")
        ttk.Entry(conn_frame, textvariable=self.timeout_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=2)
        ttk.Label(conn_frame, text="seconds").grid(row=2, column=2, sticky=tk.W, pady=2)
        
        # Auto-connect
        self.auto_connect_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            conn_frame, 
            text="Auto-connect on startup", 
            variable=self.auto_connect_var
        ).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Device settings
        device_frame = ttk.LabelFrame(main_frame, text="Device Settings", padding=10)
        device_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Camera settings
        ttk.Label(device_frame, text="Camera Model:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.camera_model_var = tk.StringVar(value="Dwarf3")
        camera_combo = ttk.Combobox(device_frame, textvariable=self.camera_model_var,
                                  values=["Dwarf3", "Dwarf2"], width=15)
        camera_combo.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # Mount type
        ttk.Label(device_frame, text="Mount Type:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.mount_type_var = tk.StringVar(value="Alt-Az")
        mount_combo = ttk.Combobox(device_frame, textvariable=self.mount_type_var,
                                 values=["Alt-Az", "Equatorial"], width=15)
        mount_combo.grid(row=1, column=1, sticky=tk.W, pady=2)
        
    def create_location_settings(self, parent):
        """Create location and time settings."""
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Geographic location
        location_frame = ttk.LabelFrame(main_frame, text="Geographic Location", padding=10)
        location_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Latitude
        ttk.Label(location_frame, text="Latitude:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.latitude_var = tk.StringVar(value="40.7128")
        ttk.Entry(location_frame, textvariable=self.latitude_var, width=15).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(location_frame, text="degrees (positive = North)").grid(row=0, column=2, sticky=tk.W, pady=2)
        
        # Longitude
        ttk.Label(location_frame, text="Longitude:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.longitude_var = tk.StringVar(value="-74.0060")
        ttk.Entry(location_frame, textvariable=self.longitude_var, width=15).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(location_frame, text="degrees (positive = East)").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        # Elevation
        ttk.Label(location_frame, text="Elevation:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.elevation_var = tk.StringVar(value="10")
        ttk.Entry(location_frame, textvariable=self.elevation_var, width=15).grid(row=2, column=1, sticky=tk.W, pady=2)
        ttk.Label(location_frame, text="meters above sea level").grid(row=2, column=2, sticky=tk.W, pady=2)
        
        # City/Location name
        ttk.Label(location_frame, text="Location Name:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.location_name_var = tk.StringVar(value="New York, NY")
        ttk.Entry(location_frame, textvariable=self.location_name_var, width=30).grid(row=3, column=1, columnspan=2, sticky=tk.W, pady=2)
        
        # Time zone settings
        timezone_frame = ttk.LabelFrame(main_frame, text="Time Zone", padding=10)
        timezone_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Time zone
        ttk.Label(timezone_frame, text="Time Zone:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.timezone_var = tk.StringVar(value="America/New_York")
        timezone_combo = ttk.Combobox(timezone_frame, textvariable=self.timezone_var, width=25,
                                    values=["America/New_York", "America/Chicago", "America/Denver", 
                                           "America/Los_Angeles", "Europe/London", "Europe/Paris",
                                           "Asia/Tokyo", "Australia/Sydney"])
        timezone_combo.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # UTC offset
        ttk.Label(timezone_frame, text="UTC Offset:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.utc_offset_var = tk.StringVar(value="-5")
        ttk.Entry(timezone_frame, textvariable=self.utc_offset_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(timezone_frame, text="hours").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        # Auto-detect
        ttk.Button(
            timezone_frame, 
            text="Auto-detect Location", 
            command=self.auto_detect_location
        ).grid(row=2, column=0, columnspan=3, pady=10)
        
    def create_default_settings(self, parent):
        """Create default capture and session settings."""
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Default capture settings
        capture_frame = ttk.LabelFrame(main_frame, text="Default Capture Settings", padding=10)
        capture_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Frame count
        ttk.Label(capture_frame, text="Default Frame Count:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.default_frames_var = tk.StringVar(value="50")
        ttk.Entry(capture_frame, textvariable=self.default_frames_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # Exposure time
        ttk.Label(capture_frame, text="Default Exposure:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.default_exposure_var = tk.StringVar(value="30")
        ttk.Entry(capture_frame, textvariable=self.default_exposure_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(capture_frame, text="seconds").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        # Gain
        ttk.Label(capture_frame, text="Default Gain:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.default_gain_var = tk.StringVar(value="100")
        ttk.Entry(capture_frame, textvariable=self.default_gain_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=2)
        
        # Binning
        ttk.Label(capture_frame, text="Default Binning:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.default_binning_var = tk.StringVar(value="1x1")
        binning_combo = ttk.Combobox(capture_frame, textvariable=self.default_binning_var,
                                   values=["1x1", "2x2", "3x3", "4x4"], width=8)
        binning_combo.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # Timing settings
        timing_frame = ttk.LabelFrame(main_frame, text="Default Timing Settings", padding=10)
        timing_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Wait between sessions
        ttk.Label(timing_frame, text="Wait Between Sessions:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.session_wait_var = tk.StringVar(value="60")
        ttk.Entry(timing_frame, textvariable=self.session_wait_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(timing_frame, text="seconds").grid(row=0, column=2, sticky=tk.W, pady=2)
        
        # Settling time
        ttk.Label(timing_frame, text="Default Settling Time:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.default_settling_var = tk.StringVar(value="10")
        ttk.Entry(timing_frame, textvariable=self.default_settling_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(timing_frame, text="seconds").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        # Focus timeout
        ttk.Label(timing_frame, text="Default Focus Timeout:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.default_focus_timeout_var = tk.StringVar(value="300")
        ttk.Entry(timing_frame, textvariable=self.default_focus_timeout_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=2)
        ttk.Label(timing_frame, text="seconds").grid(row=2, column=2, sticky=tk.W, pady=2)
        
    def create_advanced_settings(self, parent):
        """Create advanced application settings."""
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Logging settings
        logging_frame = ttk.LabelFrame(main_frame, text="Logging", padding=10)
        logging_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Log level
        ttk.Label(logging_frame, text="Log Level:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.log_level_var = tk.StringVar(value="INFO")
        log_combo = ttk.Combobox(logging_frame, textvariable=self.log_level_var,
                               values=["DEBUG", "INFO", "WARNING", "ERROR"], width=10)
        log_combo.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # Log to file
        self.log_to_file_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            logging_frame, 
            text="Log to file", 
            variable=self.log_to_file_var
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # File management
        file_frame = ttk.LabelFrame(main_frame, text="File Management", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Auto-archive
        self.auto_archive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            file_frame, 
            text="Auto-archive completed sessions", 
            variable=self.auto_archive_var
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=2)
        
        # Archive after days
        ttk.Label(file_frame, text="Archive after:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.archive_days_var = tk.StringVar(value="30")
        ttk.Entry(file_frame, textvariable=self.archive_days_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(file_frame, text="days").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        # Backup settings
        backup_frame = ttk.LabelFrame(main_frame, text="Backup", padding=10)
        backup_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Auto-backup
        self.auto_backup_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            backup_frame, 
            text="Auto-backup sessions", 
            variable=self.auto_backup_var
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=2)
        
        # Backup location
        ttk.Label(backup_frame, text="Backup Location:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.backup_location_var = tk.StringVar()
        ttk.Entry(backup_frame, textvariable=self.backup_location_var, width=40).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Button(
            backup_frame, 
            text="Browse", 
            command=self.browse_backup_location
        ).grid(row=1, column=2, padx=(5, 0), pady=2)
        
    def load_settings(self):
        """Load settings from configuration."""
        config = self.config_manager.get_all_settings()
        
        # Telescope settings
        telescope = config.get("telescope", {})
        self.dwarf_ip_var.set(telescope.get("ip", "192.168.4.1"))
        self.port_var.set(str(telescope.get("port", 80)))
        self.timeout_var.set(str(telescope.get("timeout", 10)))
        self.auto_connect_var.set(telescope.get("auto_connect", True))
        self.camera_model_var.set(telescope.get("camera_model", "Dwarf3"))
        self.mount_type_var.set(telescope.get("mount_type", "Alt-Az"))
        
        # Location settings
        location = config.get("location", {})
        self.latitude_var.set(str(location.get("latitude", 40.7128)))
        self.longitude_var.set(str(location.get("longitude", -74.0060)))
        self.elevation_var.set(str(location.get("elevation", 10)))
        self.location_name_var.set(location.get("name", "New York, NY"))
        self.timezone_var.set(location.get("timezone", "America/New_York"))
        self.utc_offset_var.set(str(location.get("utc_offset", -5)))
        
        # Default settings
        defaults = config.get("defaults", {})
        self.default_frames_var.set(str(defaults.get("frame_count", 50)))
        self.default_exposure_var.set(str(defaults.get("exposure_time", 30)))
        self.default_gain_var.set(str(defaults.get("gain", 100)))
        self.default_binning_var.set(defaults.get("binning", "1x1"))
        self.session_wait_var.set(str(defaults.get("session_wait", 60)))
        self.default_settling_var.set(str(defaults.get("settling_time", 10)))
        self.default_focus_timeout_var.set(str(defaults.get("focus_timeout", 300)))
        
        # Advanced settings
        advanced = config.get("advanced", {})
        self.log_level_var.set(advanced.get("log_level", "INFO"))
        self.log_to_file_var.set(advanced.get("log_to_file", True))
        self.auto_archive_var.set(advanced.get("auto_archive", True))
        self.archive_days_var.set(str(advanced.get("archive_days", 30)))
        self.auto_backup_var.set(advanced.get("auto_backup", False))
        self.backup_location_var.set(advanced.get("backup_location", ""))
        
    def save_settings(self):
        """Save current settings to configuration."""
        try:
            config = {
                "telescope": {
                    "ip": self.dwarf_ip_var.get(),
                    "port": int(self.port_var.get()),
                    "timeout": int(self.timeout_var.get()),
                    "auto_connect": self.auto_connect_var.get(),
                    "camera_model": self.camera_model_var.get(),
                    "mount_type": self.mount_type_var.get()
                },
                "location": {
                    "latitude": float(self.latitude_var.get()),
                    "longitude": float(self.longitude_var.get()),
                    "elevation": float(self.elevation_var.get()),
                    "name": self.location_name_var.get(),
                    "timezone": self.timezone_var.get(),
                    "utc_offset": float(self.utc_offset_var.get())
                },
                "defaults": {
                    "frame_count": int(self.default_frames_var.get()),
                    "exposure_time": float(self.default_exposure_var.get()),
                    "gain": int(self.default_gain_var.get()),
                    "binning": self.default_binning_var.get(),
                    "session_wait": int(self.session_wait_var.get()),
                    "settling_time": int(self.default_settling_var.get()),
                    "focus_timeout": int(self.default_focus_timeout_var.get())
                },
                "advanced": {
                    "log_level": self.log_level_var.get(),
                    "log_to_file": self.log_to_file_var.get(),
                    "auto_archive": self.auto_archive_var.get(),
                    "archive_days": int(self.archive_days_var.get()),
                    "auto_backup": self.auto_backup_var.get(),
                    "backup_location": self.backup_location_var.get()
                }
            }
            
            self.config_manager.save_settings(config)
            messagebox.showinfo("Success", "Settings saved successfully!")
            self.logger.info("Settings saved")
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input value: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
            self.logger.error(f"Failed to save settings: {e}")
            
    def reset_defaults(self):
        """Reset all settings to defaults."""
        if messagebox.askyesno("Confirm Reset", "Reset all settings to defaults?"):
            self.config_manager.reset_to_defaults()
            self.load_settings()
            messagebox.showinfo("Reset", "Settings reset to defaults!")
            
    def test_connection(self):
        """Test connection to telescope."""
        try:
            # This would test the actual connection to the Dwarf telescope
            ip = self.dwarf_ip_var.get()
            port = int(self.port_var.get())
            timeout = int(self.timeout_var.get())
            
            # Placeholder for actual connection test
            messagebox.showinfo("Connection Test", 
                              f"Testing connection to {ip}:{port}...\n"
                              f"(Connection test not implemented yet)")
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Connection test failed: {e}")
            
    def auto_detect_location(self):
        """Auto-detect geographic location."""
        # This would use a geolocation service
        messagebox.showinfo("Auto-detect", 
                          "Auto-detection not implemented yet.\n"
                          "Please enter coordinates manually.")
        
    def browse_backup_location(self):
        """Browse for backup location."""
        folder = filedialog.askdirectory(title="Select Backup Location")
        if folder:
            self.backup_location_var.set(folder)
