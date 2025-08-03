"""
Main window for the Dwarf3 Telescope Scheduler application.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from .tabs.schedule_tab import ScheduleTab
from .tabs.sessions_tab import SessionsTab
from .tabs.settings_tab import SettingsTab
from .tabs.history_tab import HistoryTab

class MainWindow:
    """Main application window with tabbed interface."""
    
    def __init__(self, root, config_manager):
        self.root = root
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        self.setup_window()
        self.create_widgets()
        
    def setup_window(self):
        """Configure the main window properties."""
        self.root.title("Dwarf3 Telescope Scheduler")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # Set window icon (if available)
        try:
            # You can add an icon file later
            # self.root.iconbitmap("assets/telescope.ico")
            pass
        except Exception:
            pass
            
        # Configure window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def create_widgets(self):
        """Create and layout the main widgets."""
        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.create_tabs()
        
        # Create status bar
        self.create_status_bar()
        
    def create_tabs(self):
        """Create all application tabs."""
        # Schedule tab
        self.schedule_tab = ScheduleTab(self.notebook, self.config_manager)
        self.notebook.add(self.schedule_tab.frame, text="Schedule")
        
        # Sessions tab
        self.sessions_tab = SessionsTab(self.notebook, self.config_manager)
        self.notebook.add(self.sessions_tab.frame, text="Sessions")
        
        # Settings tab
        self.settings_tab = SettingsTab(self.notebook, self.config_manager)
        self.notebook.add(self.settings_tab.frame, text="Settings")
        
        # History tab
        self.history_tab = HistoryTab(self.notebook, self.config_manager)
        self.notebook.add(self.history_tab.frame, text="History")
        
        # Bind tab change event to refresh data
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
    def on_tab_changed(self, event):
        """Handle tab change events to refresh data."""
        try:
            # Get the currently selected tab
            selected_tab = self.notebook.select()
            tab_text = self.notebook.tab(selected_tab, "text")
            
            # Refresh data based on which tab is selected
            if tab_text == "Schedule":
                self.schedule_tab.refresh_schedule()
                self.update_status("Schedule refreshed")
            elif tab_text == "Sessions":
                self.sessions_tab.refresh_sessions()
                self.update_status("Sessions refreshed")
            elif tab_text == "History":
                self.history_tab.refresh_history()
                self.update_status("History refreshed")
                
        except Exception as e:
            self.logger.error(f"Error refreshing tab data: {e}")
            
    def create_status_bar(self):
        """Create the status bar at the bottom of the window."""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Status label
        self.status_label = ttk.Label(
            self.status_frame, 
            text="Ready", 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Connection status
        self.connection_label = ttk.Label(
            self.status_frame, 
            text="Disconnected", 
            relief=tk.SUNKEN,
            foreground="red"
        )
        self.connection_label.pack(side=tk.RIGHT, padx=(5, 0))
        
    def update_status(self, message):
        """Update the status bar message."""
        self.status_label.config(text=message)
        self.logger.info(f"Status: {message}")
        
    def update_connection_status(self, connected):
        """Update the connection status indicator."""
        if connected:
            self.connection_label.config(text="Connected", foreground="green")
        else:
            self.connection_label.config(text="Disconnected", foreground="red")
            
    def on_closing(self):
        """Handle window closing event."""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.logger.info("Application closing")
            self.root.destroy()
