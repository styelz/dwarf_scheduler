"""
Sessions tab for creating and managing telescope sessions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import json
import os
import threading
import requests
import re
import logging
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

        # --- Add this mapping for filter display names <-> values ---
        self.filter_options = {
            "Vis": 0,
            "Astro": 1,
            "Dual Band": 2
        }
        # ------------------------------------------------------------

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
        # Create main container with scrollbar
        main_container = ttk.Frame(parent)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(main_container)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Basic Info section
        basic_frame = ttk.LabelFrame(scrollable_frame, text="Basic Information", padding=10)
        basic_frame.pack(fill=tk.X, padx=5, pady=(5, 10))
        self.create_basic_info_form(basic_frame)
        
        # Target Coordinates section
        coords_frame = ttk.LabelFrame(scrollable_frame, text="Target Coordinates", padding=10)
        coords_frame.pack(fill=tk.X, padx=5, pady=(0, 10))
        self.create_coordinates_form(coords_frame)
        
        # Capture Settings section
        capture_frame = ttk.LabelFrame(scrollable_frame, text="Capture Settings", padding=10)
        capture_frame.pack(fill=tk.X, padx=5, pady=(0, 10))
        self.create_capture_form(capture_frame)
        
        # Calibration section
        calib_frame = ttk.LabelFrame(scrollable_frame, text="Calibration Settings", padding=10)
        calib_frame.pack(fill=tk.X, padx=5, pady=(0, 10))
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
        
        # Bind mousewheel to canvas for scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
    def create_basic_info_form(self, parent):
        """Create basic session information form."""
        # Session name
        row = 0
        ttk.Label(parent, text="Session Name:").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.session_name_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.session_name_var, width=30).grid(row=row, column=1, sticky=tk.W+tk.E, pady=2)
        
        # Target name
        row += 1
        ttk.Label(parent, text="Target Name:").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.target_name_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.target_name_var, width=30).grid(row=row, column=1, sticky=tk.W+tk.E, pady=2)
        
        # Start time
        row += 1
        ttk.Label(parent, text="Start Time:").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.start_time_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ttk.Entry(parent, textvariable=self.start_time_var, width=30).grid(row=row, column=1, sticky=tk.W, pady=2)
        
        # Description
        row += 1
        ttk.Label(parent, text="Description:").grid(row=row, column=0, sticky=tk.W+tk.N, pady=2, padx=(0, 10))
        self.description_text = tk.Text(parent, height=3, width=30)
        self.description_text.grid(row=row, column=1, sticky=tk.W+tk.E, pady=2)
        
        # Configure grid weights
        parent.columnconfigure(1, weight=1)
        
    def create_coordinates_form(self, parent):
        """Create target coordinates form."""
        # RA coordinates
        row = 0
        ttk.Label(parent, text="Right Ascension (RA):").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.ra_var = tk.StringVar()
        self.ra_entry = ttk.Entry(parent, textvariable=self.ra_var, width=20)
        self.ra_entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Label(parent, text="(hours").grid(row=row, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Bind Enter key to RA conversion
        self.ra_entry.bind('<Return>', self.convert_ra_coordinate)
        self.ra_entry.bind('<FocusOut>', self.convert_ra_coordinate)
        
        # DEC coordinates
        row += 1
        ttk.Label(parent, text="Declination (DEC):").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.dec_var = tk.StringVar()
        self.dec_entry = ttk.Entry(parent, textvariable=self.dec_var, width=20)
        self.dec_entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Label(parent, text="(hours)").grid(row=row, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        
        # Bind Enter key to DEC conversion
        self.dec_entry.bind('<Return>', self.convert_dec_coordinate)
        self.dec_entry.bind('<FocusOut>', self.convert_dec_coordinate)
        
        # Buttons
        row += 1
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=0, columnspan=3, pady=10, sticky=tk.W)
                
        ttk.Button(
            button_frame, 
            text="Get from Stellarium", 
            command=self.get_from_stellarium
        ).pack(side=tk.LEFT)
                
        # Configure grid weights
        parent.columnconfigure(2, weight=1)
        
    def create_capture_form(self, parent):
        """Create capture settings form."""
        # First row: Frame count and Exposure time
        row = 0
        ttk.Label(parent, text="Frame Count:").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.frame_count_var = tk.StringVar(value="50")
        ttk.Entry(parent, textvariable=self.frame_count_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(parent, text="Exposure Time:").grid(row=row, column=2, sticky=tk.W, pady=2, padx=(20, 10))
        self.exposure_var = tk.StringVar(value="30")
        ttk.Entry(parent, textvariable=self.exposure_var, width=10).grid(row=row, column=3, sticky=tk.W, pady=2)
        ttk.Label(parent, text="seconds").grid(row=row, column=4, sticky=tk.W, pady=2, padx=(5, 0))
        
        # Second row: Gain and Binning
        row += 1
        ttk.Label(parent, text="Gain:").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.gain_var = tk.StringVar(value="100")
        ttk.Entry(parent, textvariable=self.gain_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(parent, text="Binning:").grid(row=row, column=2, sticky=tk.W, pady=2, padx=(20, 10))
        self.binning_var = tk.StringVar(value="1x1")
        binning_combo = ttk.Combobox(parent, textvariable=self.binning_var, 
                                   values=["1x1", "2x2", "3x3", "4x4"], width=8)
        binning_combo.grid(row=row, column=3, sticky=tk.W, pady=2)
        
        # Third row: Filter
        row += 1
        ttk.Label(parent, text="Filter:").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.filter_var = tk.StringVar(value="Astro")
        filter_combo = ttk.Combobox(parent, textvariable=self.filter_var,
                                  values=["Vis", "Astro", "Dual Band"], width=10)
        filter_combo.grid(row=row, column=1, sticky=tk.W, pady=2)
        
    def create_calibration_form(self, parent):
        """Create calibration settings form."""
        # First row: Checkboxes
        row = 0
        self.auto_focus_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="Auto Focus", variable=self.auto_focus_var).grid(row=row, column=0, sticky=tk.W, pady=2)
        
        self.plate_solve_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="Plate Solving", variable=self.plate_solve_var).grid(row=row, column=1, sticky=tk.W, pady=2, padx=(20, 0))
        
        self.auto_guide_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, text="Auto Guiding", variable=self.auto_guide_var).grid(row=row, column=2, sticky=tk.W, pady=2, padx=(20, 0))
        
        # Second row: Wait times
        row += 1
        ttk.Label(parent, text="Settling Time:").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.settling_time_var = tk.StringVar(value="10")
        ttk.Entry(parent, textvariable=self.settling_time_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Label(parent, text="seconds").grid(row=row, column=2, sticky=tk.W, pady=2, padx=(5, 0))
        
        # Third row: Focus timeout
        row += 1
        ttk.Label(parent, text="Focus Timeout:").grid(row=row, column=0, sticky=tk.W, pady=2, padx=(0, 10))
        self.focus_timeout_var = tk.StringVar(value="300")
        ttk.Entry(parent, textvariable=self.focus_timeout_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Label(parent, text="seconds").grid(row=row, column=2, sticky=tk.W, pady=2, padx=(5, 0))
        
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
        """
        Refresh the session list.
        Show session names in the listbox, but keep a mapping to filenames for selection.
        """
        self.session_listbox.delete(0, tk.END)
        self.session_display_map = {}  # Maps listbox index to filename

        directory = "Sessions/Available"
        if not os.path.exists(directory):
            return

        try:
            files = [f for f in os.listdir(directory) if f.endswith('.json')]
            files.sort()
            for idx, filename in enumerate(files):
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    session_name = data.get("session_name", filename[:-5])
                except Exception as e:
                    self.logger.error(f"Failed to load session '{filename}': {e}")
                    session_name = filename[:-5]
                self.session_listbox.insert(tk.END, session_name)
                self.session_display_map[idx] = filename
        except Exception as e:
            self.logger.error(f"Failed to refresh sessions: {e}")

    def on_session_select(self, event):
        """
        Handle session selection.
        Use the filename mapped from the selected index.
        """
        selection = self.session_listbox.curselection()
        if selection:
            idx = selection[0]
            filename = self.session_display_map.get(idx)
            if filename:
                self.load_session_data(filename)
            
    def new_session(self):
        """Create a new session."""
        self.clear_form()
        self.session_name_var.set(f"Session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        # Load default values from settings
        self.load_default_values()
        
    def load_default_values(self):
        """Load default values from settings configuration."""
        try:
            # Get default capture settings from CONFIG section
            frame_count = self.config_manager.get_setting("CONFIG", "count", 50)
            self.frame_count_var.set(str(frame_count))
            
            exposure_time = self.config_manager.get_setting("CONFIG", "exposure", 30)
            self.exposure_var.set(str(exposure_time))
            
            gain = self.config_manager.get_setting("CONFIG", "gain", 100)
            self.gain_var.set(str(gain))
            
            # Convert binning value
            binning_val = self.config_manager.get_setting("CONFIG", "binning", 0)
            if binning_val == 0:
                binning_str = "1x1"
            else:
                binning_str = f"{binning_val}x{binning_val}"
            self.binning_var.set(binning_str)
            
            # Set calibration defaults
            settling_time = self.config_manager.get_setting("CONFIG", "settling_time", 10)
            self.settling_time_var.set(str(settling_time))
            
            focus_timeout = self.config_manager.get_setting("CONFIG", "focus_timeout", 300)
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
        
        # Set capture settings to defaults (will be overridden by load_default_values if called)
        self.frame_count_var.set("50")
        self.exposure_var.set("30")
        self.gain_var.set("60")
        self.binning_var.set("1x1")
        self.filter_var.set("Astro")
        
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
            
    def get_session_data(self) -> dict:
        """Get current form data as session dictionary."""
        return {
            "session_name": self.session_name_var.get(),
            "target_name": self.target_name_var.get(),
            "start_time": self.start_time_var.get(),
            "description": self.description_text.get(1.0, tk.END).strip(),
            "coordinates": {
                "ra": self.ra_var.get(),
                "dec": self.dec_var.get(),
                "ra_decimal": getattr(self, 'ra_decimal', 0.0),
                "dec_decimal": getattr(self, 'dec_decimal', 0.0)
            },
            "capture_settings": {
                "frame_count": int(float(self.frame_count_var.get() or 0)),
                "exposure_time": int(float(self.exposure_var.get() or 0)),
                "gain": int(float(self.gain_var.get() or 0)),
                "binning": self.binning_var.get(),
                "filter": self.filter_options.get(self.filter_var.get(), 0)  # Store as int
            },
            "calibration": {
                "auto_focus": self.auto_focus_var.get(),
                "plate_solve": self.plate_solve_var.get(),
                "auto_guide": self.auto_guide_var.get(),
                "settling_time": int(float(self.settling_time_var.get() or 0)),
                "focus_timeout": int(float(self.focus_timeout_var.get() or 0))
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
                
                capture = session_data.get("capture_settings", {})
                self.frame_count_var.set(str(capture.get("frame_count", 50)))
                self.exposure_var.set(str(capture.get("exposure_time", 30)))
                self.gain_var.set(str(capture.get("gain", 100)))
                self.binning_var.set(capture.get("binning", "1x1"))
                
                # Set filter by value
                value_to_name = {v: k for k, v in self.filter_options.items()}
                self.filter_var.set(value_to_name.get(capture.get("filter", 0), "Vis"))
                
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
                
    def get_from_stellarium(self):
        """Get current target and coordinates from Stellarium."""
        def stellarium_worker():
            """Worker function to fetch data from Stellarium in background thread."""
            try:
                # Get Stellarium connection settings from CONFIG section
                stellarium_ip = self.config_manager.get_setting("CONFIG", "stellarium_ip", "192.168.1.20")
                stellarium_port = self.config_manager.get_setting("CONFIG", "stellarium_port", 8090)
                
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
                        response = requests.get(endpoint, timeout=10)
                        if response.status_code == 200:
                            object_info = response.json()
                            successful_endpoint = endpoint
                            break
                    except requests.exceptions.RequestException:
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
                if target_name == "Unknown" or not target_name:
                    target_name = object_info.get("localized-name", "Unknown")
                if target_name == "Unknown" or not target_name:
                    target_name = object_info.get("designations", "Unknown")

                target_desc = object_info.get("object-type", "") + "\n"
                target_desc += object_info.get("type", "")

                target_name = target_name.strip()
                target_desc = target_desc.strip()

                # Get coordinates - Stellarium returns RA in degrees, need to convert to hours
                ra_degrees = object_info.get("raJ2000", 0)  # RA in degrees from raJ2000
                dec_decimal = object_info.get("decJ2000", 0)  # DEC in degrees from decJ2000
                
                # Validate coordinates
                if ra_degrees == 0 and dec_decimal == 0:
                    self.parent.after(0, lambda: messagebox.showwarning(
                        "Invalid Coordinates", 
                        "Stellarium returned invalid coordinates (0,0).\nPlease ensure a valid astronomical object is selected."
                    ))
                    return
                
                # Convert RA from degrees to hours (divide by 15)
                # Also normalize to 0-24 hours range
                ra_decimal = ra_degrees / 15.0
                
                # Normalize RA to 0-24 hours range
                while ra_decimal < 0:
                    ra_decimal += 24
                while ra_decimal >= 24:
                    ra_decimal -= 24
                
                # Update the GUI in the main thread
                def update_gui():
                    self.target_name_var.set(target_name)
                    self.ra_var.set(f"{ra_decimal:.6f}")
                    self.dec_var.set(f"{dec_decimal:.6f}")
                    self.ra_decimal = ra_decimal
                    self.dec_decimal = dec_decimal
                    # Set the description field with target_desc from Stellarium
                    self.description_text.delete(1.0, tk.END)
                    self.description_text.insert(1.0, target_desc)
                    # Use logger instead of add_log_message (which does not exist)
                    self.logger.info(f"Loaded from Stellarium: {target_name} at RA={ra_decimal:.6f}h, DEC={dec_decimal:.6f}°")

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
        
        # Run in background thread to avoid blocking the GUI
        thread = threading.Thread(target=stellarium_worker, daemon=True)
        thread.start()
