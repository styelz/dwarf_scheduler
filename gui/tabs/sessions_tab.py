"""
Sessions tab for creating and managing telescope sessions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import json
import datetime
import os
import re
import requests
import threading
from core.session_manager import SessionManager

def parse_coordinate_input(coordinate_str: str, coord_type: str = "ra") -> float:
    """
    Parse various coordinate formats and convert to decimal degrees.
    
    Supported formats:
    - Decimal degrees: 123.456 or 123.456°
    - Hours/Degrees, minutes, seconds: 12:34:56, 12h34m56s, 12°34'56", 01hr 19' 47"
    - Space-separated: "01 19 47", "-29 36 15"  
    - Degrees and decimal minutes: 12°34.56' or 12:34.56
    - Decimal with units: 123.456h, 1.3297hr (for RA), 123.456d or 123.456° (for DEC)
    
    Args:
        coordinate_str: Input coordinate string
        coord_type: "ra" for right ascension, "dec" for declination
        
    Returns:
        Decimal degrees as float
    """
    if not coordinate_str or not coordinate_str.strip():
        return 0.0
        
    # Clean the input - preserve spaces initially for space-separated format detection
    coord = coordinate_str.strip()
    
    try:
        # Case 1: Decimal with "hr" suffix (Stellarium format like "1.3297hr")
        if coord.endswith('hr'):
            value = float(coord[:-2])
            return value  # Already in hours for RA
            
        # Case 2: Decimal with 'd' suffix (degrees)
        if coord.endswith('d'):
            value = float(coord[:-1])
            # Convert RA degrees to hours
            if coord_type == "ra":
                value = value / 15.0
            return value
            
        # Case 3: Simple decimal number with ° symbol
        if coord.endswith('°'):
            value = float(coord[:-1])
            # Convert RA degrees to hours
            if coord_type == "ra":
                value = value / 15.0
            return value
            
        # Case 4: Space-separated format like "01 19 47" or "-29 36 15"
        # First, clean any quotes and extra symbols for space-separated detection
        coord_for_space_check = coord.replace('"', '').replace("'", '').replace('°', '')
        space_parts = coord_for_space_check.split()
        if len(space_parts) >= 2 and all(part.replace('-', '').replace('.', '').isdigit() for part in space_parts):
            # Handle negative values
            sign = 1
            first_part = space_parts[0]
            if first_part.startswith('-'):
                sign = -1
                first_part = first_part[1:]
                
            hours_or_degrees = float(first_part)
            minutes = float(space_parts[1]) if len(space_parts) > 1 else 0
            seconds = float(space_parts[2]) if len(space_parts) > 2 else 0
            
            # Convert to decimal
            decimal_value = hours_or_degrees + minutes/60.0 + seconds/3600.0
            return sign * decimal_value
        
        # Case 5: Simple decimal number (assume degrees, convert RA to hours if needed)
        if re.match(r'^-?\d+\.?\d*$', coord):
            value = float(coord)
            # For RA, if value > 24, assume it's degrees and convert to hours
            if coord_type == "ra" and value > 24:
                value = value / 15.0
            return value
        
        # Now clean symbols for traditional parsing
        coord_clean = coord.replace(' ', '')
        
        # Handle formats with hr, ', " symbols (like "01hr 19' 47\"")
        coord_clean = coord_clean.replace('hr', ':').replace('°', ':').replace('h', ':').replace('m', ':')
        coord_clean = coord_clean.replace("'", ':').replace('"', '').replace('s', '')
            
        # Case 6: HH:MM:SS or DD:MM:SS format (traditional colon-separated)
        parts = coord_clean.split(':')
        if len(parts) >= 2:
            # Handle negative values
            sign = 1
            first_part = parts[0]
            if first_part.startswith('-'):
                sign = -1
                first_part = first_part[1:]
                
            hours_or_degrees = float(first_part)
            minutes = float(parts[1]) if len(parts) > 1 else 0
            seconds = float(parts[2]) if len(parts) > 2 else 0
            
            # Convert to decimal
            decimal_value = hours_or_degrees + minutes/60.0 + seconds/3600.0
            return sign * decimal_value
            
        # Case 7: Single value, try to parse as float
        return float(coord_clean)
        
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid coordinate format: '{coordinate_str}'. Use formats like 12:34:56, 01 19 47, 123.456, 1.3297hr, or 12h34m56s")

def format_coordinate_display(decimal_value: float, coord_type: str = "ra") -> str:
    """
    Format decimal coordinate back to HH:MM:SS or DD:MM:SS for display.
    
    Args:
        decimal_value: Decimal coordinate value
        coord_type: "ra" for right ascension, "dec" for declination
        
    Returns:
        Formatted coordinate string
    """
    if decimal_value is None:
        return ""
        
    # Handle negative values for declination
    sign = ""
    if decimal_value < 0:
        sign = "-"
        decimal_value = abs(decimal_value)
        
    # Split into components
    whole = int(decimal_value)
    fraction = decimal_value - whole
    
    minutes_decimal = fraction * 60
    minutes = int(minutes_decimal)
    seconds = (minutes_decimal - minutes) * 60
    
    # Format with appropriate precision
    return f"{sign}{whole:02d}:{minutes:02d}:{seconds:05.2f}"

class SessionsTab:
    """Tab for managing telescope sessions."""
    
    def __init__(self, parent, config_manager):
        self.parent = parent
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize session manager
        self.session_manager = SessionManager()
        
        self.create_widgets()
        self.refresh_sessions()
        
    def create_widgets(self):
        """Create and layout widgets for the sessions tab."""
        self.frame = ttk.Frame(self.parent)
        
        # Main container with paned window
        paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Session list
        left_frame = ttk.LabelFrame(paned, text="Sessions", padding=10)
        paned.add(left_frame, weight=1)
        
        self.create_session_list(left_frame)
        
        # Right panel - Session editor
        right_frame = ttk.LabelFrame(paned, text="Session Editor", padding=10)
        paned.add(right_frame, weight=2)
        
        self.create_session_editor(right_frame)
        
    def create_session_list(self, parent):
        """Create the session list with controls."""
        # Control buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(
            button_frame, 
            text="New Session", 
            command=self.new_session
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Delete", 
            command=self.delete_session
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Duplicate", 
            command=self.duplicate_session
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Refresh", 
            command=self.refresh_sessions
        ).pack(side=tk.LEFT)
        
        # Session list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Listbox with scrollbar
        self.session_listbox = tk.Listbox(list_frame, height=20)
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.session_listbox.yview)
        self.session_listbox.configure(yscrollcommand=list_scroll.set)
        
        self.session_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind events
        self.session_listbox.bind("<<ListboxSelect>>", self.on_session_select)
        
        # Context menu
        self.create_context_menu()
        
    def create_session_editor(self, parent):
        """Create the session editor form."""
        # Create notebook for different sections
        editor_notebook = ttk.Notebook(parent)
        editor_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Basic Info tab
        basic_frame = ttk.Frame(editor_notebook)
        editor_notebook.add(basic_frame, text="Basic Info")
        self.create_basic_info_form(basic_frame)
        
        # Target Coordinates tab
        coords_frame = ttk.Frame(editor_notebook)
        editor_notebook.add(coords_frame, text="Coordinates")
        self.create_coordinates_form(coords_frame)
        
        # Capture Settings tab
        capture_frame = ttk.Frame(editor_notebook)
        editor_notebook.add(capture_frame, text="Capture")
        self.create_capture_form(capture_frame)
        
        # Calibration tab
        calib_frame = ttk.Frame(editor_notebook)
        editor_notebook.add(calib_frame, text="Calibration")
        self.create_calibration_form(calib_frame)
        
        # Save/Load buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="Save Session", 
            command=self.save_session
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Load Session", 
            command=self.load_session
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Add to Schedule", 
            command=self.add_to_schedule
        ).pack(side=tk.RIGHT)
        
    def create_basic_info_form(self, parent):
        """Create basic session information form."""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Session name
        ttk.Label(form_frame, text="Session Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.session_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.session_name_var, width=40).grid(row=0, column=1, columnspan=2, sticky=tk.W+tk.E, pady=2)
        
        # Target name
        ttk.Label(form_frame, text="Target Name:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.target_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.target_name_var, width=40).grid(row=1, column=1, columnspan=2, sticky=tk.W+tk.E, pady=2)
        
        # Start time
        ttk.Label(form_frame, text="Start Time:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.start_time_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ttk.Entry(form_frame, textvariable=self.start_time_var, width=30).grid(row=2, column=1, sticky=tk.W, pady=2)
        
        # Description
        ttk.Label(form_frame, text="Description:").grid(row=3, column=0, sticky=tk.W+tk.N, pady=2)
        self.description_text = tk.Text(form_frame, height=6, width=40)
        self.description_text.grid(row=3, column=1, columnspan=2, sticky=tk.W+tk.E, pady=2)
        
        # Configure grid weights
        form_frame.columnconfigure(1, weight=1)
        
    def create_coordinates_form(self, parent):
        """Create target coordinates form."""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # RA coordinates
        ttk.Label(form_frame, text="Right Ascension (RA):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.ra_var = tk.StringVar()
        self.ra_entry = ttk.Entry(form_frame, textvariable=self.ra_var, width=20)
        self.ra_entry.grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(form_frame, text="(HH:MM:SS, 01 19 47, 1.3297hr, etc.)").grid(row=0, column=2, sticky=tk.W, pady=2)
        
        # Bind Enter key to RA conversion
        self.ra_entry.bind('<Return>', self.convert_ra_coordinate)
        self.ra_entry.bind('<FocusOut>', self.convert_ra_coordinate)
        
        # DEC coordinates
        ttk.Label(form_frame, text="Declination (DEC):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.dec_var = tk.StringVar()
        self.dec_entry = ttk.Entry(form_frame, textvariable=self.dec_var, width=20)
        self.dec_entry.grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(form_frame, text="(DD:MM:SS, -29 36 15, -29.6043°, etc.)").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        # Bind Enter key to DEC conversion
        self.dec_entry.bind('<Return>', self.convert_dec_coordinate)
        self.dec_entry.bind('<FocusOut>', self.convert_dec_coordinate)
        
        # Format examples
        examples_frame = ttk.LabelFrame(form_frame, text="Supported Formats", padding=5)
        examples_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        
        examples_text = tk.Text(examples_frame, height=5, width=60, wrap=tk.WORD)
        examples_text.pack(fill=tk.X)
        examples_text.insert(tk.END, 
            "RA Examples: 12:34:56, 01 19 47, 1h29m46s, 01hr 19' 47\", 1.3297hr, 185.75°\n"
            "DEC Examples: +45:30:15, -29 36 15, -23°15'30\", -29.6043°, 45.504167\n"
            "Formats: HH:MM:SS, space-separated, decimal degrees, Stellarium/Telescopius formats\n"
            "Press Enter or Tab to convert to standard format.\n"
            "RA: Hours (0-24), DEC: Degrees (-90 to +90)")
        examples_text.config(state=tk.DISABLED)
        
        # Altitude/Azimuth (optional)
        ttk.Label(form_frame, text="Altitude:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.alt_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.alt_var, width=20).grid(row=3, column=1, sticky=tk.W, pady=2)
        ttk.Label(form_frame, text="(degrees)").grid(row=3, column=2, sticky=tk.W, pady=2)
        
        ttk.Label(form_frame, text="Azimuth:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.az_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.az_var, width=20).grid(row=4, column=1, sticky=tk.W, pady=2)
        ttk.Label(form_frame, text="(degrees)").grid(row=4, column=2, sticky=tk.W, pady=2)
        
        # Coordinate lookup button
        ttk.Button(
            form_frame, 
            text="Lookup Coordinates", 
            command=self.lookup_coordinates
        ).grid(row=5, column=0, columnspan=3, pady=10)
        
        # Get from Stellarium button
        ttk.Button(
            form_frame, 
            text="Get from Stellarium", 
            command=self.get_from_stellarium
        ).grid(row=6, column=0, columnspan=3, pady=5)
        
        # Configure grid weights
        form_frame.columnconfigure(2, weight=1)
        
    def create_capture_form(self, parent):
        """Create capture settings form."""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Frame count
        ttk.Label(form_frame, text="Frame Count:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.frame_count_var = tk.StringVar(value="50")
        ttk.Entry(form_frame, textvariable=self.frame_count_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # Exposure time
        ttk.Label(form_frame, text="Exposure Time:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.exposure_var = tk.StringVar(value="30")
        ttk.Entry(form_frame, textvariable=self.exposure_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(form_frame, text="seconds").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        # Gain
        ttk.Label(form_frame, text="Gain:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.gain_var = tk.StringVar(value="100")
        ttk.Entry(form_frame, textvariable=self.gain_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=2)
        
        # Binning
        ttk.Label(form_frame, text="Binning:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.binning_var = tk.StringVar(value="1x1")
        binning_combo = ttk.Combobox(form_frame, textvariable=self.binning_var, 
                                   values=["1x1", "2x2", "3x3", "4x4"], width=8)
        binning_combo.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # Filter
        ttk.Label(form_frame, text="Filter:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.filter_var = tk.StringVar(value="None")
        filter_combo = ttk.Combobox(form_frame, textvariable=self.filter_var,
                                  values=["None", "R", "G", "B", "L", "Ha", "OIII", "SII"], width=10)
        filter_combo.grid(row=4, column=1, sticky=tk.W, pady=2)
        
    def create_calibration_form(self, parent):
        """Create calibration settings form."""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Calibration options
        self.auto_focus_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Auto Focus", variable=self.auto_focus_var).grid(row=0, column=0, sticky=tk.W, pady=2)
        
        self.plate_solve_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Plate Solving", variable=self.plate_solve_var).grid(row=1, column=0, sticky=tk.W, pady=2)
        
        self.auto_guide_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Auto Guiding", variable=self.auto_guide_var).grid(row=2, column=0, sticky=tk.W, pady=2)
        
        # Wait times
        ttk.Label(form_frame, text="Settling Time:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.settling_time_var = tk.StringVar(value="10")
        ttk.Entry(form_frame, textvariable=self.settling_time_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=2)
        ttk.Label(form_frame, text="seconds").grid(row=3, column=2, sticky=tk.W, pady=2)
        
        ttk.Label(form_frame, text="Focus Timeout:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.focus_timeout_var = tk.StringVar(value="300")
        ttk.Entry(form_frame, textvariable=self.focus_timeout_var, width=10).grid(row=4, column=1, sticky=tk.W, pady=2)
        ttk.Label(form_frame, text="seconds").grid(row=4, column=2, sticky=tk.W, pady=2)
        
    def create_context_menu(self):
        """Create context menu for session list."""
        self.context_menu = tk.Menu(self.session_listbox, tearoff=0)
        self.context_menu.add_command(label="Edit", command=self.edit_session)
        self.context_menu.add_command(label="Duplicate", command=self.duplicate_session)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete", command=self.delete_session)
        self.context_menu.add_command(label="Add to Schedule", command=self.add_to_schedule)
        
        self.session_listbox.bind("<Button-3>", self.show_context_menu)
        
    def show_context_menu(self, event):
        """Show context menu."""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
            
    def refresh_sessions(self):
        """Refresh the session list."""
        self.session_listbox.delete(0, tk.END)
        sessions = self.session_manager.get_available_sessions()
        for session in sessions:
            self.session_listbox.insert(tk.END, session)
            
    def on_session_select(self, event):
        """Handle session selection."""
        selection = self.session_listbox.curselection()
        if selection:
            session_name = self.session_listbox.get(selection[0])
            self.load_session_data(session_name)
            
    def new_session(self):
        """Create a new session."""
        self.clear_form()
        self.session_name_var.set(f"Session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        # Load default values from settings
        self.load_default_values()
        
    def load_default_values(self):
        """Load default values from settings configuration."""
        try:
            # Get default capture settings - use get_setting for the entire defaults section
            frame_count = self.config_manager.get_setting("defaults", "frame_count", 50)
            self.frame_count_var.set(str(frame_count))
            
            exposure_time = self.config_manager.get_setting("defaults", "exposure_time", 30)
            self.exposure_var.set(str(exposure_time))
            
            gain = self.config_manager.get_setting("defaults", "gain", 100)
            self.gain_var.set(str(gain))
            
            binning = self.config_manager.get_setting("defaults", "binning", "1x1")
            self.binning_var.set(binning)
            
            # Set calibration defaults
            settling_time = self.config_manager.get_setting("defaults", "settling_time", 10)
            self.settling_time_var.set(str(settling_time))
            
            focus_timeout = self.config_manager.get_setting("defaults", "focus_timeout", 300)
            self.focus_timeout_var.set(str(focus_timeout))
            
        except Exception as e:
            self.logger.warning(f"Failed to load default values: {e}")
            # If loading defaults fails, use hardcoded fallbacks
            self.frame_count_var.set("50")
            self.exposure_var.set("30")
            self.gain_var.set("100")
            self.binning_var.set("1x1")
            self.settling_time_var.set("10")
            self.focus_timeout_var.set("300")
        
    def clear_form(self):
        """Clear all form fields and set to default values."""
        # Clear basic info
        self.session_name_var.set("")
        self.target_name_var.set("")
        self.start_time_var.set(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.description_text.delete(1.0, tk.END)
        
        # Clear coordinates
        self.ra_var.set("")
        self.dec_var.set("")
        self.alt_var.set("")
        self.az_var.set("")
        
        # Set capture settings to defaults (will be overridden by load_default_values if called)
        self.frame_count_var.set("50")
        self.exposure_var.set("30")
        self.gain_var.set("100")
        self.binning_var.set("1x1")
        self.filter_var.set("None")
        
        # Set calibration settings to defaults (will be overridden by load_default_values if called)
        self.auto_focus_var.set(True)
        self.plate_solve_var.set(True)
        self.auto_guide_var.set(False)
        self.settling_time_var.set("10")
        self.focus_timeout_var.set("300")
        
    def save_session(self):
        """Save current session."""
        if not self.session_name_var.get():
            messagebox.showerror("Error", "Session name is required!")
            return
            
        session_data = self.get_session_data()
        try:
            self.session_manager.save_session(session_data)
            self.refresh_sessions()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save session: {e}")
            
    def get_session_data(self):
        """Get current form data as session dictionary."""
        return {
            "session_name": self.session_name_var.get(),
            "target_name": self.target_name_var.get(),
            "start_time": self.start_time_var.get(),
            "description": self.description_text.get(1.0, tk.END).strip(),
            "coordinates": {
                "ra": self.ra_var.get(),
                "dec": self.dec_var.get(),
                "ra_decimal": getattr(self, 'ra_decimal', 0.0),  # Store decimal hours for precision
                "dec_decimal": getattr(self, 'dec_decimal', 0.0),  # Store decimal degrees for precision
                "alt": self.alt_var.get(),
                "az": self.az_var.get()
            },
            "capture_settings": {
                "frame_count": int(self.frame_count_var.get() or 0),
                "exposure_time": float(self.exposure_var.get() or 0),
                "gain": int(self.gain_var.get() or 0),
                "binning": self.binning_var.get(),
                "filter": self.filter_var.get()
            },
            "calibration": {
                "auto_focus": self.auto_focus_var.get(),
                "plate_solve": self.plate_solve_var.get(),
                "auto_guide": self.auto_guide_var.get(),
                "settling_time": int(self.settling_time_var.get() or 0),
                "focus_timeout": int(self.focus_timeout_var.get() or 0)
            }
        }
        
    def load_session_data(self, session_name):
        """Load session data into form."""
        try:
            session_data = self.session_manager.load_session(session_name)
            if session_data:
                self.session_name_var.set(session_data.get("session_name", ""))
                self.target_name_var.set(session_data.get("target_name", ""))
                self.start_time_var.set(session_data.get("start_time", ""))
                self.description_text.delete(1.0, tk.END)
                self.description_text.insert(1.0, session_data.get("description", ""))
                
                coords = session_data.get("coordinates", {})
                
                # Load coordinates using raw string values, not converted
                # Store decimal values for calculations but display raw input
                if "ra_decimal" in coords and coords["ra_decimal"]:
                    self.ra_decimal = coords["ra_decimal"]
                else:
                    self.ra_decimal = None
                self.ra_var.set(coords.get("ra", ""))
                    
                if "dec_decimal" in coords and coords["dec_decimal"]:
                    self.dec_decimal = coords["dec_decimal"] 
                else:
                    self.dec_decimal = None
                self.dec_var.set(coords.get("dec", ""))
                    
                self.alt_var.set(coords.get("alt", ""))
                self.az_var.set(coords.get("az", ""))
                
                capture = session_data.get("capture_settings", {})
                self.frame_count_var.set(str(capture.get("frame_count", 50)))
                self.exposure_var.set(str(capture.get("exposure_time", 30)))
                self.gain_var.set(str(capture.get("gain", 100)))
                self.binning_var.set(capture.get("binning", "1x1"))
                self.filter_var.set(capture.get("filter", "None"))
                
                calib = session_data.get("calibration", {})
                self.auto_focus_var.set(calib.get("auto_focus", True))
                self.plate_solve_var.set(calib.get("plate_solve", True))
                self.auto_guide_var.set(calib.get("auto_guide", False))
                self.settling_time_var.set(str(calib.get("settling_time", 10)))
                self.focus_timeout_var.set(str(calib.get("focus_timeout", 300)))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load session: {e}")
            
    def load_session(self):
        """Load session from file dialog."""
        filename = filedialog.askopenfilename(
            title="Load Session",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir="Sessions/Available"
        )
        if filename:
            try:
                with open(filename, 'r') as f:
                    session_data = json.load(f)
                    # Load data into form (implementation similar to load_session_data)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load session file: {e}")
                
    def delete_session(self):
        """Delete selected session."""
        selection = self.session_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to delete.")
            return
            
        session_name = self.session_listbox.get(selection[0])
        if messagebox.askyesno("Confirm Delete", f"Delete session '{session_name}'?"):
            try:
                self.session_manager.delete_session(session_name)
                self.refresh_sessions()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete session: {e}")
                
    def duplicate_session(self):
        """Duplicate selected session."""
        selection = self.session_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to duplicate.")
            return
            
        session_name = self.session_listbox.get(selection[0])
        new_name = f"{session_name}_copy"
        
        try:
            self.session_manager.duplicate_session(session_name, new_name)
            self.refresh_sessions()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to duplicate session: {e}")
            
    def edit_session(self):
        """Edit selected session (same as selection)."""
        self.on_session_select(None)
        
    def add_to_schedule(self):
        """Add current session to schedule."""
        if not self.session_name_var.get():
            messagebox.showerror("Error", "Please create or select a session first!")
            return
            
        session_data = self.get_session_data()
        try:
            session_name = session_data.get('session_name', 'Unknown')
            target_name = session_data.get('target_name', 'Unknown')
            
            # First, check if a session with this name/target already exists in Available
            existing_file = None
            available_dir = "Sessions/Available"
            
            if os.path.exists(available_dir):
                for filename in os.listdir(available_dir):
                    if filename.endswith('.json'):
                        # Load the session to check if it matches
                        existing_session = self.session_manager.load_session(filename, available_dir)
                        if existing_session and (
                            existing_session.get('session_name') == session_name or
                            (existing_session.get('target_name') == target_name and 
                             existing_session.get('session_name') == session_name)
                        ):
                            existing_file = filename
                            break
            
            if existing_file:
                # Move the existing session from Available to ToDo
                success = self.session_manager.move_session(existing_file, "Available", "ToDo")
                action = "moved to"
            else:
                # No existing session found, save new one directly to ToDo
                saved_filepath = self.session_manager.save_session(session_data, "ToDo")
                success = True
                action = "added to"
            
            if success:
                # Refresh the sessions list to reflect the change
                self.refresh_sessions()
            else:
                messagebox.showerror("Error", "Failed to add session to schedule!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add to schedule: {e}")
            
    def convert_ra_coordinate(self, event=None):
        """Convert RA coordinate input to standard format."""
        try:
            input_value = self.ra_var.get().strip()
            if not input_value:
                return
                
            # Parse the input and convert to decimal hours
            decimal_hours = parse_coordinate_input(input_value, "ra")
            
            # Validate RA range (0-24 hours)
            if decimal_hours < 0 or decimal_hours >= 24:
                raise ValueError("RA must be between 0 and 24 hours")
                
            # Set as decimal value (J2000 format)
            self.ra_var.set(f"{decimal_hours:.6f}")
            
            # Store the decimal value for internal use
            self.ra_decimal = decimal_hours
            
        except ValueError as e:
            # Show error but don't clear the field so user can correct it
            messagebox.showerror("Invalid RA Format", str(e))
            self.ra_entry.focus()
            
    def convert_dec_coordinate(self, event=None):
        """Convert DEC coordinate input to standard format."""
        try:
            input_value = self.dec_var.get().strip()
            if not input_value:
                return
                
            # Parse the input and convert to decimal degrees
            decimal_degrees = parse_coordinate_input(input_value, "dec")
            
            # Validate DEC range (-90 to +90 degrees)
            if decimal_degrees < -90 or decimal_degrees > 90:
                raise ValueError("DEC must be between -90 and +90 degrees")
                
            # Set as decimal value (J2000 format)
            self.dec_var.set(f"{decimal_degrees:.6f}")
            
            # Store the decimal value for internal use
            self.dec_decimal = decimal_degrees
            
        except ValueError as e:
            # Show error but don't clear the field so user can correct it
            messagebox.showerror("Invalid DEC Format", str(e))
            self.dec_entry.focus()
            
    def get_ra_decimal(self):
        """Get RA in decimal hours."""
        return getattr(self, 'ra_decimal', 0.0)
        
    def get_dec_decimal(self):
        """Get DEC in decimal degrees."""
        return getattr(self, 'dec_decimal', 0.0)
        
    def lookup_coordinates(self):
        """Lookup coordinates for target (placeholder)."""
        target = self.target_name_var.get()
        if not target:
            messagebox.showwarning("No Target", "Please enter a target name first.")
            return
            
        # This would integrate with an astronomy database
        messagebox.showinfo("Lookup", f"Coordinate lookup for '{target}' not implemented yet.\nPlease enter coordinates manually.")
        
    def get_from_stellarium(self):
        """Get current target and coordinates from Stellarium."""
        def stellarium_worker():
            """Worker function to fetch data from Stellarium in background thread."""
            try:
                # Get Stellarium connection settings
                stellarium_ip = self.config_manager.get_setting("stellarium", "ip", "192.168.1.20")
                stellarium_port = self.config_manager.get_setting("stellarium", "port", 8090)
                
                # Build the API URL for getting object info
                base_url = f"http://{stellarium_ip}:{stellarium_port}/api"
                
                # Try different endpoints and formats
                endpoints_to_try = [
                    f"{base_url}/objects/info?format=json",  # Explicitly request JSON format
                    f"{base_url}/objects/info",               # Default endpoint
                    f"{base_url}/stelaction/do",              # Alternative action endpoint
                ]
                
                object_info = None
                successful_endpoint = None
                
                for endpoint in endpoints_to_try:
                    try:
                        if "stelaction" in endpoint:
                            # For action endpoint, use POST with action parameter
                            response = requests.post(endpoint, 
                                                   data={"id": "actionShow_Object_Info"},
                                                   timeout=5)
                        else:
                            response = requests.get(endpoint, timeout=5)
                        
                        response.raise_for_status()
                        
                        # Check if we got any content
                        if not response.text.strip():
                            continue
                        
                        # Check content type and try to parse accordingly
                        content_type = response.headers.get('Content-Type', '').lower()
                        
                        if 'json' in content_type or endpoint.endswith('format=json'):
                            # Try to parse as JSON
                            try:
                                object_info = response.json()
                                successful_endpoint = endpoint
                                break
                            except json.JSONDecodeError:
                                continue
                        else:
                            # Got HTML/text response - Stellarium might be returning HTML format
                            # Let's inform the user about the configuration issue
                            if len(response.text) > 100:  # We got a substantial response
                                self.parent.after(0, lambda: messagebox.showerror(
                                    "Configuration Issue", 
                                    f"Stellarium is returning HTML instead of JSON.\n\n"
                                    f"Please check Remote Control plugin settings:\n"
                                    f"• Enable 'Allow remote control'\n"
                                    f"• Set response format to JSON\n"
                                    f"• Restart Stellarium after changes\n\n"
                                    f"Response received: {response.text[:100]}..."
                                ))
                                return
                    
                    except requests.exceptions.RequestException:
                        # Try next endpoint
                        continue
                
                # If no endpoint worked, show connection error
                if object_info is None:
                    self.parent.after(0, lambda: messagebox.showerror(
                        "Connection Error",
                        f"Cannot get TARGET from Stellarium at {stellarium_ip}:{stellarium_port}\n\n"
                        f"Please ensure:\n"
                        f"• A target is selected in Stellarium"
                    ))
                    return
                    
                if not object_info or "name" not in object_info:
                    self.parent.after(0, lambda: messagebox.showwarning(
                        "No Selection", 
                        "No object is currently selected in Stellarium.\nPlease select an object first."
                    ))
                    return
                
                # Get target name - try different possible fields
                target_name = object_info.get("name", "Unknown")
                if target_name == "Unknown":
                    target_name = object_info.get("localized-name", "Unknown")
                if target_name == "Unknown":
                    target_name = object_info.get("designation", "Unknown")
                
                # Get coordinates - Stellarium returns RA in hours and DEC in degrees for J2000
                ra_decimal = object_info.get("raJ2000", 0)  # RA in hours from raJ2000
                dec_decimal = object_info.get("decJ2000", 0)  # DEC in degrees from decJ2000
                
                # Validate coordinates
                if ra_decimal == 0 and dec_decimal == 0:
                    # Try current epoch coordinates if J2000 not available
                    ra_decimal = object_info.get("ra", 0)
                    dec_decimal = object_info.get("dec", 0)
                
                # Update the GUI in the main thread
                def update_gui():
                    self.target_name_var.set(target_name)
                    # Set coordinates directly as they come from Stellarium
                    self.ra_var.set(f"{ra_decimal:.6f}")
                    self.dec_var.set(f"{dec_decimal:.6f}")
                    # Store the values for internal use
                    self.ra_decimal = ra_decimal  # RA in hours from Stellarium
                    self.dec_decimal = dec_decimal  # DEC in degrees from Stellarium
                    
                    messagebox.showinfo(
                        "Success", 
                        f"Retrieved target from Stellarium:\n"
                        f"Target: {target_name}\n"
                        f"RA: {ra_decimal:.6f}h\n"
                        f"DEC: {dec_decimal:.6f}°"
                    )
                
                self.parent.after(0, update_gui)
                    
            except requests.exceptions.ConnectionError:
                error_msg = (f"Cannot connect to Stellarium at {stellarium_ip}:{stellarium_port}\n\n"
                           f"Please ensure:\n"
                           f"• Stellarium is running\n"
                           f"• Remote Control plugin is enabled\n"
                           f"• Server settings match: {stellarium_ip}:{stellarium_port}\n"
                           f"• Check Settings tab for correct IP address")
                self.parent.after(0, lambda: messagebox.showerror("Connection Error", error_msg))
            except requests.exceptions.Timeout:
                self.parent.after(0, lambda: messagebox.showerror(
                    "Timeout Error", 
                    "Connection to Stellarium timed out.\nPlease check if Stellarium is responding."
                ))
            except Exception as e:
                error_msg = f"Failed to get data from Stellarium: {str(e)}"
                self.parent.after(0, lambda: messagebox.showerror(
                    "Error", 
                    error_msg
                ))
                    
            except Exception as e:
                self.logger.error(f"Stellarium connection error: {e}")
                error_msg = f"An unexpected error occurred: {str(e)}"
                self.parent.after(0, lambda: messagebox.showerror(
                    "Error", 
                    error_msg
                ))
        
        # Run in background thread to avoid blocking the GUI
        thread = threading.Thread(target=stellarium_worker, daemon=True)
        thread.start()
