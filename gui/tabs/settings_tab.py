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
        
        # Reference to scheduler will be set by main window
        self.scheduler = None
        
        # Auto-save debounce timer
        self.auto_save_timer = None
        self.auto_save_delay = 1000  # 1 second delay in milliseconds
        
        self.create_widgets()
        self.load_settings()
        self.setup_auto_save_callbacks()
        
    def set_scheduler_reference(self, scheduler):
        """Set reference to scheduler for settings updates."""
        self.scheduler = scheduler
    
    def setup_auto_save_callbacks(self):
        """Setup auto-save callbacks for all settings widgets."""
        # Get all StringVar, IntVar, BooleanVar, DoubleVar instances
        vars_to_watch = []
        
        # Telescope settings
        vars_to_watch.extend([
            self.dwarf_ip_var, self.port_var, self.timeout_var,
            self.auto_connect_var, self.camera_model_var, self.mount_type_var,
            self.stellarium_ip_var, self.stellarium_port_var
        ])
        
        # Location settings
        vars_to_watch.extend([
            self.latitude_var, self.longitude_var,
            self.location_name_var, self.timezone_var, self.utc_offset_var
        ])
        
        # Default settings
        vars_to_watch.extend([
            self.default_frames_var, self.default_exposure_var, self.default_gain_var,
            self.default_binning_var, self.session_wait_var, self.default_settling_var,
            self.default_focus_timeout_var
        ])
        
        # History settings
        vars_to_watch.append(self.day_change_hour_var)
        
        # Add trace callbacks to all variables
        for var in vars_to_watch:
            if hasattr(var, 'trace_add'):  # Modern tkinter
                var.trace_add('write', self.on_setting_changed)
            else:  # Older tkinter
                var.trace('w', self.on_setting_changed)
    
    def on_setting_changed(self, *args):
        """Called when any setting changes - triggers debounced auto-save."""
        # Cancel existing timer if it exists
        if self.auto_save_timer:
            self.parent.after_cancel(self.auto_save_timer)
        
        # Schedule new auto-save
        self.auto_save_timer = self.parent.after(self.auto_save_delay, self.auto_save_settings)
    
    def auto_save_settings(self):
        """Automatically save settings (debounced version)."""
        try:
            self.save_settings_internal()
            self.logger.debug("Settings auto-saved")
        except Exception as e:
            self.logger.error(f"Auto-save failed: {e}")
        finally:
            self.auto_save_timer = None
        
    def create_widgets(self):
        """Create and layout widgets for the settings tab."""
        self.frame = ttk.Frame(self.parent)
        
        # Create a canvas and scrollbar for scrollable content
        canvas = tk.Canvas(self.frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        # Configure scrollable frame
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        scrollbar.pack(side="right", fill="y", pady=5)
        
        # Bind mousewheel to canvas
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Create main container with two columns
        main_container = ttk.Frame(scrollable_frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left column
        left_column = ttk.Frame(main_container)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Right column
        right_column = ttk.Frame(main_container)
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Distribute settings across two columns
        self.create_telescope_settings(left_column)
        self.create_location_settings(left_column)
        self.create_default_settings(right_column)
        self.create_advanced_settings(right_column)
        
        right_column.pack(fill=tk.X, padx=5, pady=5)        
        ttk.Button(
            right_column, 
            text="Reset to Defaults", 
            command=self.reset_defaults
        ).pack(side=tk.LEFT)
        
    def create_telescope_settings(self, parent):
        """Create telescope connection settings."""
        # Telescope section header
        main_frame = ttk.LabelFrame(parent, text="Telescope Settings", padding=10)
        main_frame.pack(fill=tk.X, pady=(0, 10))
        
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
        
        # Stellarium settings
        stellarium_frame = ttk.LabelFrame(main_frame, text="Stellarium Remote", padding=10)
        stellarium_frame.pack(fill=tk.X, pady=(0, 0))
        
        # Stellarium IP Address
        ttk.Label(stellarium_frame, text="Stellarium IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.stellarium_ip_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(stellarium_frame, textvariable=self.stellarium_ip_var, width=20).grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # Stellarium Port
        ttk.Label(stellarium_frame, text="Stellarium Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.stellarium_port_var = tk.StringVar(value="8090")
        ttk.Entry(stellarium_frame, textvariable=self.stellarium_port_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        
        # Device settings
        device_frame = ttk.LabelFrame(main_frame, text="Device Settings", padding=10)
        device_frame.pack(fill=tk.X)
        
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
        # Location section header
        main_frame = ttk.LabelFrame(parent, text="Location & Time Settings", padding=10)
        main_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Geographic location
        location_frame = ttk.LabelFrame(main_frame, text="Geographic Location", padding=10)
        location_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Latitude
        ttk.Label(location_frame, text="Latitude:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.latitude_var = tk.StringVar(value="40.7128")
        ttk.Entry(location_frame, textvariable=self.latitude_var, width=15).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(location_frame, text="degrees (+ = North)").grid(row=0, column=2, sticky=tk.W, pady=2)
        
        # Longitude
        ttk.Label(location_frame, text="Longitude:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.longitude_var = tk.StringVar(value="-74.0060")
        ttk.Entry(location_frame, textvariable=self.longitude_var, width=15).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(location_frame, text="degrees (+ = East)").grid(row=1, column=2, sticky=tk.W, pady=2)
                
        # City/Location name
        ttk.Label(location_frame, text="Location Name:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.location_name_var = tk.StringVar(value="New York, NY")
        ttk.Entry(location_frame, textvariable=self.location_name_var, width=25).grid(row=3, column=1, columnspan=2, sticky=tk.W, pady=2)
        
        # Time zone settings
        timezone_frame = ttk.LabelFrame(main_frame, text="Time Zone", padding=10)
        timezone_frame.pack(fill=tk.X)
        
        # Time zone
        ttk.Label(timezone_frame, text="Time Zone:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.timezone_var = tk.StringVar(value="America/New_York")
        timezone_combo = ttk.Combobox(timezone_frame, textvariable=self.timezone_var, width=20,
                                    values=["America/New_York", "America/Chicago", "America/Denver", 
                                           "America/Los_Angeles", "Europe/London", "Europe/Paris",
                                           "Asia/Tokyo", "Australia/Sydney"])
        timezone_combo.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # UTC offset
        ttk.Label(timezone_frame, text="UTC Offset:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.utc_offset_var = tk.StringVar(value="-5")
        ttk.Entry(timezone_frame, textvariable=self.utc_offset_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(timezone_frame, text="hours").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        # Auto-detect button (smaller)
        ttk.Button(
            timezone_frame, 
            text="Auto-detect", 
            command=self.auto_detect_location
        ).grid(row=2, column=0, columnspan=2, pady=8, sticky=tk.W)
        
    def create_default_settings(self, parent):
        """Create default capture and session settings."""
        # Defaults section header
        main_frame = ttk.LabelFrame(parent, text="Default Settings", padding=10)
        main_frame.pack(fill=tk.X, pady=(0, 10))
        
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
        timing_frame.pack(fill=tk.X)
        
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
        # Advanced section header
        main_frame = ttk.LabelFrame(parent, text="Advanced Settings", padding=10)
        main_frame.pack(fill=tk.X, pady=(0, 10))
        
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
        
        # History settings
        history_frame = ttk.LabelFrame(main_frame, text="History Settings", padding=10)
        history_frame.pack(fill=tk.X, pady=(0, 0))
        
        # Day change hour
        ttk.Label(history_frame, text="Day change hour:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.day_change_hour_var = tk.StringVar(value="18")
        day_change_spinbox = tk.Spinbox(history_frame, textvariable=self.day_change_hour_var, 
                                       from_=0, to=23, width=5, format="%02.0f")
        day_change_spinbox.grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(history_frame, text="(24-hour format)").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(5, 0))
        
        # Explanation (smaller font)
        ttk.Label(history_frame, 
                 text="Sessions before this hour go to previous day's history",
                 font=("Arial", 8)).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        
        # Backup settings
        backup_frame = ttk.LabelFrame(main_frame, text="Backup", padding=10)
        backup_frame.pack(fill=tk.X)
                
    def load_settings(self):
        """Load settings from configuration."""
        config = self.config_manager.get_all_settings()
        
        # All settings from CONFIG section
        config_section = config.get("CONFIG", {})
        self.dwarf_ip_var.set(config_section.get("telescope_ip", "192.168.4.1"))
        self.port_var.set(str(config_section.get("telescope_port", 80)))
        self.timeout_var.set(str(config_section.get("telescope_timeout", 10)))
        self.auto_connect_var.set(config_section.get("auto_connect", True))
        self.stellarium_ip_var.set(config_section.get("stellarium_ip", "192.168.1.20"))
        self.stellarium_port_var.set(str(config_section.get("stellarium_port", 8090)))
        
        # Device settings from CONFIG section
        self.camera_model_var.set(config_section.get("camera_model", "Dwarf3"))
        self.mount_type_var.set(config_section.get("mount_type", "Equatorial"))
        
        # Location settings from CONFIG section
        self.latitude_var.set(str(config_section.get("latitude", 40.7128)))
        self.longitude_var.set(str(config_section.get("longitude", -74.0060)))
        self.location_name_var.set(config_section.get("address", "New York, NY"))
        self.timezone_var.set(config_section.get("timezone", "America/New_York"))
        self.utc_offset_var.set(str(config_section.get("utc_offset", -5)))
        
        # Default settings from CONFIG section
        self.default_frames_var.set(str(config_section.get("count", 50)))
        self.default_exposure_var.set(str(config_section.get("exposure", 30)))
        self.default_gain_var.set(str(config_section.get("gain", 100)))
        
        # Convert binning value
        binning_val = config_section.get("binning", 0)
        if binning_val == 0:
            self.default_binning_var.set("1x1")
        else:
            self.default_binning_var.set(f"{binning_val}x{binning_val}")
        
        self.session_wait_var.set(str(config_section.get("session_wait", 60)))
        self.default_settling_var.set(str(config_section.get("settling_time", 10)))
        self.default_focus_timeout_var.set(str(config_section.get("focus_timeout", 300)))
        
        # Advanced settings from CONFIG section
        self.log_level_var.set(config_section.get("log_level", "INFO"))
        self.log_to_file_var.set(config_section.get("log_to_file", True))
        self.auto_archive_var.set(config_section.get("auto_archive", True))
        self.archive_days_var.set(str(config_section.get("archive_days", 30)))
        
        # History settings from CONFIG section
        self.day_change_hour_var.set(str(config_section.get("day_change_hour", 18)))
        
    def save_settings_internal(self):
        """Internal method to save settings without user dialogs."""
        try:
            # All settings go to CONFIG section
            config_settings = {
                # Telescope settings
                "telescope_ip": self.dwarf_ip_var.get(),
                "telescope_port": int(self.port_var.get()),
                "telescope_timeout": int(self.timeout_var.get()),
                "auto_connect": self.auto_connect_var.get(),
                "stellarium_ip": self.stellarium_ip_var.get(),
                "stellarium_port": int(self.stellarium_port_var.get()),
                
                # Device settings
                "camera_model": self.camera_model_var.get(),
                "mount_type": self.mount_type_var.get(),
                "device_type": "Dwarf 3 Tele Lens",
                
                # Location settings
                "latitude": float(self.latitude_var.get()),
                "longitude": float(self.longitude_var.get()),
                "address": self.location_name_var.get(),
                "timezone": self.timezone_var.get(),
                "utc_offset": int(self.utc_offset_var.get()),
                
                # Default capture settings
                "count": int(self.default_frames_var.get()),
                "exposure": int(self.default_exposure_var.get()),
                "gain": int(self.default_gain_var.get()),
                "session_wait": int(self.session_wait_var.get()),
                "settling_time": int(self.default_settling_var.get()),
                "focus_timeout": int(self.default_focus_timeout_var.get()),
                
                # Advanced settings
                "log_level": self.log_level_var.get(),
                "log_to_file": self.log_to_file_var.get(),
                "auto_archive": self.auto_archive_var.get(),
                "archive_days": int(self.archive_days_var.get()),
                "day_change_hour": int(self.day_change_hour_var.get())
            }
            
            # Convert binning setting
            binning_str = self.default_binning_var.get()
            if binning_str == "1x1":
                config_settings["binning"] = 0
            else:
                # Extract number from format like "2x2"
                binning_num = int(binning_str.split('x')[0])
                config_settings["binning"] = binning_num
            
            # Save to config manager
            settings_dict = {
                "CONFIG": config_settings
            }
            
            self.config_manager.save_settings(settings_dict)
            
            # Refresh scheduler settings if available
            if self.scheduler and hasattr(self.scheduler, 'dwarf_controller'):
                try:
                    self.scheduler.dwarf_controller.refresh_settings()
                    self.logger.debug("Scheduler settings refreshed")
                except Exception as e:
                    self.logger.error(f"Failed to refresh scheduler settings: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            return False
            
    def reset_defaults(self):
        """Reset all settings to defaults."""
        if messagebox.askyesno("Confirm Reset", "Reset all settings to defaults?"):
            self.config_manager.reset_to_defaults()
            self.load_settings()
            # Auto-save the reset values
            self.auto_save_settings()
                        
    def auto_detect_location(self):
        """Auto-detect geographic location."""
        # This would use a geolocation service
        messagebox.showinfo("Auto-detect", 
                          "Auto-detection not implemented yet.\n"
                          "Please enter coordinates manually.")
        
