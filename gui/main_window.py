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
        # Create status bar first (at bottom)
        self.create_status_bar()
        
        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.create_tabs()
        
        # Start monitoring scheduler status after tabs are created
        self.monitor_scheduler_status()
        
        # Check for orphaned sessions and show recovery dialog if needed
        self.check_orphaned_sessions_on_startup()
        
        # Handle auto-connect if enabled
        self.handle_auto_connect_on_startup()
        
    def monitor_scheduler_status(self):
        """Monitor and update scheduler status in the status bar."""
        try:
            # Get scheduler from schedule tab
            if hasattr(self, 'schedule_tab') and hasattr(self.schedule_tab, 'scheduler'):
                scheduler = self.schedule_tab.scheduler
                
                # Update scheduler status
                if hasattr(scheduler, 'is_running') and scheduler.is_running:
                    self.update_scheduler_status("Running", "green")
                else:
                    self.update_scheduler_status("Stopped", "red")
                
                # Update connection status using non-blocking call
                def handle_telescope_status(result):
                    """Handle telescope status result from threaded call."""
                    try:
                        if result:
                            connected = result.get('connected', False)
                            self.root.after(0, lambda: self.update_connection_status(connected, result if connected else None))
                        else:
                            self.root.after(0, lambda: self.update_connection_status(False))
                    except Exception as e:
                        self.logger.debug(f"Error handling telescope status: {e}")
                        self.root.after(0, lambda: self.update_connection_status(False))
                
                try:
                    # Use non-blocking telescope status check
                    if hasattr(scheduler, 'telescope_controller'):
                        scheduler.telescope_controller.get_telescope_status(timeout=5, callback=handle_telescope_status)
                    else:
                        # Fallback to synchronous method with shorter timeout
                        telescope_status = scheduler.get_telescope_status(timeout=2)
                        connected = telescope_status.get('connected', False) if telescope_status else False
                        self.update_connection_status(connected, telescope_status if connected else None)
                except Exception as e:
                    self.logger.debug(f"Error checking telescope connection: {e}")
                    self.update_connection_status(False)
                    
            else:
                self.update_scheduler_status("Unknown", "gray")
                self.update_connection_status(False, None)
                
        except Exception as e:
            self.logger.error(f"Error monitoring scheduler status: {e}")
            self.update_scheduler_status("Error", "gray")
            self.update_connection_status(False, None)
        
        # Schedule next update
        self.root.after(5000, self.monitor_scheduler_status)  # Update every 5 seconds
        
    def create_tabs(self):
        """Create all application tabs."""
        # Schedule tab
        self.schedule_tab = ScheduleTab(self.notebook, self.config_manager)
        self.notebook.add(self.schedule_tab.frame, text="Schedule")
        
        # Sessions tab
        self.sessions_tab = SessionsTab(self.notebook, self.config_manager)
        self.notebook.add(self.sessions_tab.frame, text="Sessions")

        # History tab
        self.history_tab = HistoryTab(self.notebook, self.config_manager)
        self.notebook.add(self.history_tab.frame, text="History")

        # Settings tab
        self.settings_tab = SettingsTab(self.notebook, self.config_manager)
        self.notebook.add(self.settings_tab.frame, text="Settings")
        
        # Set scheduler reference in settings tab for settings refresh
        self.settings_tab.set_scheduler_reference(self.schedule_tab.scheduler)
                
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
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0, 5))
        
        # Status label
        self.status_label = ttk.Label(
            self.status_frame, 
            text="Ready", 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Scheduler status
        self.scheduler_status_label = ttk.Label(
            self.status_frame, 
            text="Scheduler: Stopped", 
            relief=tk.SUNKEN,
            foreground="red"
        )
        self.scheduler_status_label.pack(side=tk.RIGHT, padx=(5, 5))
        
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
        
    def update_connection_status(self, connected, telescope_info=None):
        """Update the connection status indicator."""
        if connected:
            self.connection_label.config(text="✓ Connected", foreground="green")
        else:
            self.connection_label.config(text="✗ Disconnected", foreground="red")
    
    def update_scheduler_status(self, status, color):
        """Update the scheduler status indicator."""
        if hasattr(self, 'scheduler_status_label'):
            self.scheduler_status_label.config(text=f"Scheduler: {status}", foreground=color)
            
    def on_closing(self):
        """Handle window closing event."""
        # if messagebox.askokcancel("Quit", "Do you want to quit?"):
        self.logger.info("Application closing")
        
        # Clean up scheduler and telescope controller
        try:
            if hasattr(self, 'schedule_tab') and hasattr(self.schedule_tab, 'scheduler'):
                scheduler = self.schedule_tab.scheduler
                if hasattr(scheduler, 'dwarf_controller'):
                    self.logger.info("Cleaning up telescope controller...")
                    scheduler.dwarf_controller.cleanup()
                if hasattr(scheduler, 'stop'):
                    scheduler.stop()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
        
        self.root.destroy()
            
    def check_orphaned_sessions_on_startup(self):
        """Check for orphaned running sessions and show recovery dialog."""
        try:
            # Get scheduler from schedule tab
            if hasattr(self, 'schedule_tab') and hasattr(self.schedule_tab, 'scheduler'):
                scheduler = self.schedule_tab.scheduler
                session_manager = scheduler.session_manager
                
                # Check if there are running sessions
                running_count = session_manager.get_running_sessions_count()
                
                if running_count > 0:
                    # Show recovery dialog
                    self.show_orphaned_sessions_dialog(running_count, scheduler)
                    
        except Exception as e:
            self.logger.error(f"Error checking orphaned sessions: {e}")
            
    def show_orphaned_sessions_dialog(self, count: int, scheduler):
        """Show dialog for recovering orphaned sessions."""
        message = (
            f"Found {count} session(s) that were running when the application was last closed.\n\n"
            "These sessions are stuck in 'Running' status and prevent normal operation.\n\n"
            "How would you like to handle them?"
        )
        
        # Create custom dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Orphaned Sessions Detected")
        dialog.geometry("500x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        # Message label
        message_label = ttk.Label(dialog, text=message, wraplength=450, justify=tk.LEFT)
        message_label.pack(pady=20, padx=20)
        
        # Button frame
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def mark_as_failed():
            """Mark orphaned sessions as failed."""
            try:
                recovered = scheduler.recover_running_sessions("fail")
                self.update_status(f"Marked {len(recovered)} sessions as failed")
                dialog.destroy()
                # Refresh tabs
                if hasattr(self, 'schedule_tab'):
                    self.schedule_tab.refresh_schedule()
                if hasattr(self, 'sessions_tab'):
                    self.sessions_tab.refresh_sessions()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to recover sessions: {e}")
        
        def move_to_queue():
            """Move orphaned sessions back to queue."""
            try:
                recovered = scheduler.recover_running_sessions("todo")
                self.update_status(f"Moved {len(recovered)} sessions back to queue")
                dialog.destroy()
                # Refresh tabs
                if hasattr(self, 'schedule_tab'):
                    self.schedule_tab.refresh_schedule()
                if hasattr(self, 'sessions_tab'):
                    self.sessions_tab.refresh_sessions()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to recover sessions: {e}")
        
        def move_to_available():
            """Move orphaned sessions to available for editing."""
            try:
                recovered = scheduler.recover_running_sessions("available")
                self.update_status(f"Moved {len(recovered)} sessions to available")
                dialog.destroy()
                # Refresh tabs
                if hasattr(self, 'schedule_tab'):
                    self.schedule_tab.refresh_schedule()
                if hasattr(self, 'sessions_tab'):
                    self.sessions_tab.refresh_sessions()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to recover sessions: {e}")
        
        # Buttons
        ttk.Button(button_frame, text="Mark as Failed", command=mark_as_failed).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Return to Queue", command=move_to_queue).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Make Available", command=move_to_available).pack(side=tk.LEFT, padx=5)
        
        # Info label
        info_label = ttk.Label(
            dialog, 
            text="• Mark as Failed: Sessions are recorded as failed in history\n"
                 "• Return to Queue: Sessions will be scheduled again\n"
                 "• Make Available: Sessions can be edited and rescheduled",
            font=("TkDefaultFont", 8),
            foreground="gray"
        )
        info_label.pack(pady=(0, 10), padx=20)
        
    def handle_auto_connect_on_startup(self):
        """Handle auto-connect functionality on startup."""
        try:
            # Check if auto-connect is enabled in settings
            telescope_settings = self.config_manager.get_telescope_settings()
            auto_connect = telescope_settings.get("auto_connect", False)
            
            if auto_connect:
                self.logger.info("Auto-connect enabled, attempting to connect to telescope...")
                self.update_status("Auto-connecting to telescope...")
                
                # Get the telescope controller and attempt connection
                if hasattr(self, 'schedule_tab') and hasattr(self.schedule_tab, 'scheduler'):
                    scheduler = self.schedule_tab.scheduler
                    self.logger.info("Successfully connected to Dwarf3")
                    def auto_connect_callback(success, message):
                        """Callback for auto-connect attempt."""
                        if success:
                            self.root.after(0, lambda: self.update_status("Auto-connect successful"))
                            self.logger.info(f"Auto-connect successful: {message}")
                        else:
                            self.root.after(0, lambda: self.update_status("Auto-connect failed"))
                            self.logger.warning(f"Auto-connect failed: {message}")
                    
                    # Use threaded connection to avoid blocking startup
                    scheduler.telescope_controller.connect(timeout=10, callback=auto_connect_callback)
                    
            else:
                self.logger.info("Auto-connect disabled in settings")
                
        except Exception as e:
            self.logger.error(f"Error during auto-connect: {e}")
            self.update_status("Auto-connect error")
