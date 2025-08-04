"""
Schedule tab for managing telescope session scheduling.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import os
import datetime
from core.scheduler import Scheduler
from core.session_manager import SessionManager

class ScheduleTab:
    """Tab for scheduling telescope sessions."""
    
    def __init__(self, parent, config_manager):
        self.parent = parent
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize managers
        self.session_manager = SessionManager()
        self.scheduler = Scheduler(self.session_manager, config_manager)
        
        # Control flag for periodic updates
        self.periodic_updates_active = True
        
        # Set up scheduler callbacks for real-time log updates
        self.scheduler.set_status_callback(self.on_scheduler_status_update)
        self.scheduler.set_session_callback(self.on_scheduler_session_update)
        
        self.create_widgets()
        self.refresh_schedule()
        
        # Initialize scheduler status
        self.update_scheduler_status()
        self.update_button_states()  # Update button states on startup
        
        # Start periodic telescope status updates
        self.start_periodic_telescope_status_update()
        
    def create_widgets(self):
        """Create and layout widgets for the schedule tab."""
        self.frame = ttk.Frame(self.parent)
        
        # Configure custom button styles
        style = ttk.Style()
        style.configure("Connected.TButton", foreground="green")
        style.configure("Disconnected.TButton", foreground="red")
        
        # Main vertical paned window - split between top content and log
        main_paned = ttk.PanedWindow(self.frame, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Top section - horizontal paned window for schedule and details
        top_frame = ttk.Frame(main_paned)
        main_paned.add(top_frame, weight=3)  # 60% of total height
        
        # Horizontal paned window for schedule queue and session details
        paned = ttk.PanedWindow(top_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Schedule queue
        left_frame = ttk.LabelFrame(paned, text="Schedule Queue", padding=10)
        paned.add(left_frame, weight=2)  # Give more space to schedule queue
        
        # Schedule controls
        controls_frame = ttk.LabelFrame(left_frame, text="Controls", padding=5)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create button grid for better organization
        button_grid = ttk.Frame(controls_frame)
        button_grid.pack(fill=tk.X)
        
        # Configure columns for even distribution
        button_grid.grid_columnconfigure(0, weight=1)
        button_grid.grid_columnconfigure(1, weight=1)
        button_grid.grid_columnconfigure(2, weight=1)
        button_grid.grid_columnconfigure(3, weight=1)
        
        # Main control buttons - Row 1
        self.start_button = ttk.Button(
            button_grid, 
            text="Start", 
            command=self.start_scheduler,
            width=10
        )
        self.start_button.grid(row=0, column=0, padx=2, pady=2, sticky=tk.EW)
        
        self.stop_button = ttk.Button(
            button_grid, 
            text="Stop", 
            command=self.stop_scheduler,
            width=10
        )
        self.stop_button.grid(row=0, column=1, padx=2, pady=2, sticky=tk.EW)
        
        ttk.Button(
            button_grid, 
            text="Refresh", 
            command=self.refresh_schedule,
            width=10
        ).grid(row=0, column=2, padx=2, pady=2, sticky=tk.EW)
        
        # Connection control button
        self.connection_button = ttk.Button(
            button_grid, 
            text="Connect", 
            command=self.toggle_telescope_connection,
            width=10
        )
        self.connection_button.grid(row=0, column=3, padx=2, pady=2, sticky=tk.EW)
        
        # Test connection button - Row 2
        ttk.Button(
            button_grid, 
            text="Test Connection", 
            command=self.test_telescope_connection,
            width=15
        ).grid(row=1, column=0, columnspan=4, padx=2, pady=2, sticky=tk.EW)
        
        # Telescope status display
        status_frame = ttk.LabelFrame(controls_frame, text="Telescope Status", padding=5)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.telescope_status_text = tk.Text(
            status_frame,
            height=4,
            font=('Segoe UI', 8),
            bg='#f8f8f8',
            fg='#333333',
            relief=tk.SUNKEN,
            bd=1,
            state=tk.DISABLED
        )
        self.telescope_status_text.pack(fill=tk.X, padx=5, pady=5)
        
        # Schedule tree
        self.create_schedule_tree(left_frame)
        
        # Right panel - Session details
        right_frame = ttk.LabelFrame(paned, text="Session Details", padding=10)
        paned.add(right_frame, weight=3)  # Give more space to session details
        
        self.create_session_details(right_frame)
        
        # Bottom section - Session log output (40% of total height)
        log_frame = ttk.LabelFrame(main_paned, text="Session Log Output", padding=10)
        main_paned.add(log_frame, weight=2)  # 40% of total height
        
        self.create_log_output(log_frame)
        
    def create_schedule_tree(self, parent):
        """Create the schedule queue tree view."""
        # Container for tree and scrollbars
        tree_container = ttk.Frame(parent)
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        # Tree view for scheduled sessions
        columns = ("time", "target", "status", "frames", "exposure")
        self.schedule_tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=12)
        
        # Configure columns with better proportions
        self.schedule_tree.heading("time", text="Start Time")
        self.schedule_tree.heading("target", text="Target")
        self.schedule_tree.heading("status", text="Status")
        self.schedule_tree.heading("frames", text="Frames")
        self.schedule_tree.heading("exposure", text="Exposure")
        
        self.schedule_tree.column("time", width=140, minwidth=120)
        self.schedule_tree.column("target", width=100, minwidth=80)
        self.schedule_tree.column("status", width=80, minwidth=60)
        self.schedule_tree.column("frames", width=60, minwidth=50)
        self.schedule_tree.column("exposure", width=70, minwidth=60)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.schedule_tree.yview)
        tree_scroll_x = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.schedule_tree.xview)
        self.schedule_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        # Grid layout for better control
        self.schedule_tree.grid(row=0, column=0, sticky=tk.N+tk.S+tk.E+tk.W)
        tree_scroll_y.grid(row=0, column=1, sticky=tk.N+tk.S)
        tree_scroll_x.grid(row=1, column=0, sticky=tk.E+tk.W)
        
        # Configure grid weights
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.schedule_tree.bind("<<TreeviewSelect>>", self.on_schedule_select)
        
    def create_session_details(self, parent):
        """Create session details panel."""
        # Main details container
        details_container = ttk.Frame(parent)
        details_container.pack(fill=tk.BOTH, expand=True)
        
        # Session control buttons - arranged in a grid for better visibility
        button_frame = ttk.LabelFrame(details_container, text="Session Actions", padding=10)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create button grid
        button_grid = ttk.Frame(button_frame)
        button_grid.pack(fill=tk.X)
        
        ttk.Button(
            button_grid, 
            text="Remove from Queue", 
            command=self.remove_from_queue,
            width=18
        ).grid(row=0, column=0, padx=(0, 5), pady=(0, 5), sticky=tk.W+tk.E)
        
        ttk.Button(
            button_grid, 
            text="Reset to Available", 
            command=self.reset_to_available,
            width=15
        ).grid(row=0, column=1, padx=(5, 5), pady=(0, 5), sticky=tk.W+tk.E)
        
        ttk.Button(
            button_grid, 
            text="Delete Session", 
            command=self.delete_session_from_schedule,
            width=15
        ).grid(row=0, column=2, padx=(5, 0), pady=(0, 5), sticky=tk.W+tk.E)
        
        # Configure column weights for better distribution
        button_grid.columnconfigure(0, weight=2)
        button_grid.columnconfigure(1, weight=1)
        button_grid.columnconfigure(2, weight=1)
        
        # Details text widget with better sizing
        text_frame = ttk.Frame(details_container)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.details_text = tk.Text(
            text_frame, 
            height=15, 
            width=50, 
            wrap=tk.WORD,
            font=('Segoe UI', 9),
            bg='#ffffff',
            fg='#000000',
            relief=tk.SUNKEN,
            bd=1
        )
        details_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scroll.set)
        
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
    def create_log_output(self, parent):
        """Create session log output window."""
        # Log controls frame
        log_controls = ttk.Frame(parent)
        log_controls.pack(fill=tk.X, pady=(0, 10))
        
        # Auto-scroll checkbox
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            log_controls,
            text="Auto-scroll",
            variable=self.auto_scroll_var
        ).pack(side=tk.LEFT)
        
        # Log level filter
        ttk.Label(log_controls, text="Level:").pack(side=tk.LEFT, padx=(20, 5))
        self.log_level_var = tk.StringVar(value="INFO")
        log_level_combo = ttk.Combobox(
            log_controls,
            textvariable=self.log_level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            width=10,
            state="readonly"
        )
        log_level_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # Log action buttons
        ttk.Button(
            log_controls,
            text="Clear Log",
            command=self.clear_log
        ).pack(side=tk.RIGHT, padx=(0, 5))
        
        ttk.Button(
            log_controls,
            text="Save Log",
            command=self.save_log
        ).pack(side=tk.RIGHT)
        
        # Log text widget with scrollbar
        log_text_frame = ttk.Frame(parent)
        log_text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(
            log_text_frame, 
            height=12, 
            wrap=tk.WORD,
            font=('DejaVu Sans Mono', 10),
            bg='#ffffff',
            fg='#000000',
            insertbackground='black'
        )
        
        log_scroll_y = ttk.Scrollbar(log_text_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll_x = ttk.Scrollbar(log_text_frame, orient=tk.HORIZONTAL, command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=log_scroll_y.set, xscrollcommand=log_scroll_x.set)
        
        # Pack scrollbars first, then text widget - this ensures proper layout
        log_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        log_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure text tags for different log levels
        self.log_text.tag_config("DEBUG", foreground="#666666")
        self.log_text.tag_config("INFO", foreground="#000000")
        self.log_text.tag_config("WARNING", foreground="#cc6600")
        self.log_text.tag_config("ERROR", foreground="#cc0000")
        self.log_text.tag_config("SUCCESS", foreground="#006600")
        
        # Configure text tags for indicator types
        self.log_text.tag_config("START_TAG", foreground="#008844")
        self.log_text.tag_config("STOP_TAG", foreground="#cc3333")
        self.log_text.tag_config("SESSION_TAG", foreground="#0066cc")
        self.log_text.tag_config("COMPLETE_TAG", foreground="#006600")
        self.log_text.tag_config("ERROR_TAG", foreground="#cc0000")
        self.log_text.tag_config("WARNING_TAG", foreground="#cc6600")
        self.log_text.tag_config("INFO_TAG", foreground="#0088cc")
        
        # Add initial welcome message
        self.add_log_message("INFO", "Session log initialized - Ready for scheduling operations")
        
    def clear_log(self):
        """Clear the log output."""
        if hasattr(self, 'log_text'):
            self.log_text.delete(1.0, tk.END)
            self.add_log_message("INFO", "Log cleared")
        
    def refresh_schedule(self):
        """Refresh the schedule display."""
        # Clear current items
        for item in self.schedule_tree.get_children():
            self.schedule_tree.delete(item)
            
        # Get sessions from all status directories
        all_sessions = []
        
        # Define the order and display mapping for statuses
        status_order = ["ToDo", "Running", "Done", "Failed"]
        status_display = {
            "ToDo": "Queued",
            "Running": "Running", 
            "Done": "Completed",
            "Failed": "Failed"
        }
        
        # Collect sessions from each status directory
        for status in status_order:
            sessions = self.session_manager.get_session_by_status(status)
            for session in sessions:
                # Add status information to session data
                session["current_status"] = status
                session["display_status"] = status_display[status]
                all_sessions.append(session)
        
        # Log the refresh activity
        if hasattr(self, 'add_log_message'):
            total_count = len(all_sessions)
            todo_count = len([s for s in all_sessions if s["current_status"] == "ToDo"])
            self.add_log_message("DEBUG", f"Schedule refreshed - {total_count} total sessions ({todo_count} queued, {total_count - todo_count} archived)")
        
        # Sort all sessions by start time
        all_sessions.sort(key=lambda x: x.get("start_time", ""))
        
        # Add sessions to tree with appropriate formatting
        for session in all_sessions:
            status = session["current_status"]
            display_status = session["display_status"]
            
            # Create display values
            start_time = session.get("start_time", "")
            target_name = session.get("target_name", "")
            frame_count = session.get("capture_settings", {}).get("frame_count", "")
            exposure_time = session.get("capture_settings", {}).get("exposure_time", "")
            
            # Format exposure time
            exposure_display = f"{exposure_time}s" if exposure_time else ""
            
            # Insert item with status-based formatting
            item_id = self.schedule_tree.insert("", tk.END, values=(
                start_time,
                target_name,
                display_status,
                frame_count,
                exposure_display
            ))
            
            # Apply different styling based on status
            if status == "ToDo":
                # Queued sessions - normal appearance (can be executed)
                self.schedule_tree.set(item_id, "status", "Queued")
            elif status == "Running":
                # Running sessions - highlight in blue
                self.schedule_tree.item(item_id, tags=("running",))
            elif status == "Done":
                # Completed sessions - highlight in green
                self.schedule_tree.item(item_id, tags=("completed",))
            elif status == "Failed":
                # Failed sessions - highlight in red
                self.schedule_tree.item(item_id, tags=("failed",))
        
        # Configure tags for visual styling
        self.schedule_tree.tag_configure("running", background="#e6f3ff", foreground="#0066cc")
        self.schedule_tree.tag_configure("completed", background="#e6ffe6", foreground="#006600")
        self.schedule_tree.tag_configure("failed", background="#ffe6e6", foreground="#cc0000")
            
    def on_schedule_select(self, event):
        """Handle schedule tree selection."""
        selection = self.schedule_tree.selection()
        if not selection:
            return
            
        item = self.schedule_tree.item(selection[0])
        values = item["values"]
        
        if values:
            start_time = values[0]
            target_name = values[1]
            status = values[2]
            frame_count = values[3]
            exposure = values[4]
            
            # Determine session's current status and executability
            execution_status = ""
            if status == "Queued":
                execution_status = "✓ Ready for execution when scheduled time arrives"
            elif status == "Running":
                execution_status = "⚡ Currently executing"
            elif status == "Completed":
                execution_status = "✓ Execution completed successfully"
            elif status == "Failed":
                execution_status = "✗ Execution failed - needs to be reset to Available"
            
            # Display session details with status information
            details = f"""Selected Session Details:

Start Time: {start_time}
Target: {target_name}
Status: {status}
Frame Count: {frame_count}
Exposure: {exposure}

Execution Status:
{execution_status}

Notes:
- Only sessions with 'Queued' status can be executed by the scheduler
- To re-run a Failed/Completed session, move it back to Available first
- Running sessions cannot be modified until completion
"""
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, details)
            
    def start_scheduler(self):
        """Start the scheduling engine."""
        try:
            self.scheduler.start()
            self.update_scheduler_status()  # Update status display
            self.log_scheduler_event("start", "Telescope scheduling engine activated")
            self.logger.info("Scheduler started")
        except Exception as e:
            self.log_scheduler_event("session_error", f"Failed to start scheduler: {e}")
            messagebox.showerror("Error", f"Failed to start scheduler: {e}")
            self.logger.error(f"Failed to start scheduler: {e}")
            
    def stop_scheduler(self):
        """Stop the scheduling engine."""
        try:
            self.scheduler.stop()
            self.update_scheduler_status()  # Update status display
            self.log_scheduler_event("stop", "Telescope scheduling engine deactivated")
            self.logger.info("Scheduler stopped")
        except Exception as e:
            self.log_scheduler_event("session_error", f"Failed to stop scheduler: {e}")
            messagebox.showerror("Error", f"Failed to stop scheduler: {e}")
            self.logger.error(f"Failed to stop scheduler: {e}")
            
    def update_scheduler_status(self):
        """Update the scheduler status display."""
        try:
            # Just update button states - status is now shown in main window status bar
            self.update_button_states()
        except Exception as e:
            self.logger.error(f"Failed to update scheduler status: {e}")
            
    def update_button_states(self):
        """Update the enabled/disabled state of control buttons based on scheduler status."""
        try:
            is_running = hasattr(self.scheduler, 'is_running') and self.scheduler.is_running
            is_connected = self.scheduler.dwarf_controller.is_connected()
            
            if hasattr(self, 'start_button') and hasattr(self, 'stop_button'):
                if is_running:
                    # Scheduler is running - disable start, enable stop
                    self.start_button.config(state=tk.DISABLED)
                    self.stop_button.config(state=tk.NORMAL)
                else:
                    # Scheduler is stopped - enable start, disable stop
                    self.start_button.config(state=tk.NORMAL)
                    self.stop_button.config(state=tk.DISABLED)
                    
            # Update connection button state and text
            if hasattr(self, 'connection_button'):
                controller = self.scheduler.dwarf_controller
                
                # Check connection state priority: connecting > connected > disconnected
                if hasattr(controller, 'connecting') and controller.connecting:
                    # Connection in progress - show cancel option
                    self.connection_button.config(text="✖ Cancel", style="Disconnected.TButton", state=tk.NORMAL)
                elif controller.connected:  # Use direct connected flag instead of is_connected() method
                    # Connected - show disconnect option
                    self.connection_button.config(text="✓ Disconnect", style="Connected.TButton", state=tk.NORMAL)
                else:
                    # Disconnected - show connect option
                    self.connection_button.config(text="⚡ Connect", style="Disconnected.TButton", state=tk.NORMAL)
                    
        except Exception as e:
            self.logger.error(f"Failed to update button states: {e}")
            
    def toggle_telescope_connection(self):
        """Toggle telescope connection (connect/disconnect)."""
        try:
            controller = self.scheduler.dwarf_controller
            
            # Check if we're currently in a connecting state
            if hasattr(controller, 'connecting') and controller.connecting:
                # Cancel connection attempt
                self.add_log_message("INFO", "Cancelling connection attempt...")
                self.update_telescope_status_display("Cancelling...")
                self.connection_button.config(text="Cancelling...", state=tk.DISABLED)
                
                def cancel_callback():
                    """Handle connection cancellation."""
                    try:
                        controller.cancel_connection()  # Use proper cancel method
                        self.frame.after(0, lambda: [
                            self.add_log_message("INFO", "Connection attempt cancelled"),
                            self.update_telescope_status_display("✗ Cancelled"),
                            self.update_button_states()
                        ])
                    except Exception as e:
                        self.frame.after(0, lambda: [
                            self.add_log_message("ERROR", f"Error cancelling connection: {e}"),
                            self.update_telescope_status_display("✗ Cancel Error"),
                            self.update_button_states()
                        ])
                
                import threading
                threading.Thread(target=cancel_callback, daemon=True).start()
                
            elif controller.is_connected():
                # Disconnect
                self.add_log_message("INFO", "Disconnecting from telescope...")
                self.update_telescope_status_display("Disconnecting...")
                self.connection_button.config(text="Disconnecting...", state=tk.DISABLED)
                
                def disconnect_callback():
                    """Handle disconnect completion."""
                    try:
                        controller.disconnect()
                        self.frame.after(0, lambda: [
                            self.add_log_message("INFO", "Disconnected from telescope"),
                            self.update_telescope_status_display("✗ Disconnected"),
                            self.update_button_states()
                        ])
                    except Exception as e:
                        self.frame.after(0, lambda: [
                            self.add_log_message("ERROR", f"Error during disconnect: {e}"),
                            self.update_telescope_status_display("✗ Disconnect Error"),
                            self.update_button_states()
                        ])
                
                # Run disconnect in background to avoid blocking GUI
                import threading
                threading.Thread(target=disconnect_callback, daemon=True).start()
                
            else:
                # Connect
                self.add_log_message("INFO", "Connecting to telescope...")
                self.update_telescope_status_display("Connecting...")
                # Change button to show "Cancel" during connection attempt
                self.connection_button.config(text="✖ Cancel", style="Disconnected.TButton", state=tk.NORMAL)
                
                def connect_callback(success, message):
                    """Handle connection result."""
                    self.frame.after(0, lambda: [
                        self._handle_connection_result(success, message)
                    ])
                
                # Use threaded connection with reasonable timeout (3 retries * ~10s each = ~30s max)
                controller.connect(timeout=10, callback=connect_callback)
                
        except Exception as e:
            self.add_log_message("ERROR", f"Error toggling connection: {e}")
            self.update_telescope_status_display("✗ Connection Error")
            if hasattr(self, 'connection_button'):
                self.connection_button.config(state=tk.NORMAL)
            
    def _handle_connection_result(self, success, message):
        """Handle the result of a connection attempt."""
        try:
            if success:
                self.add_log_message("INFO", f"Successfully connected: {message}")
                
                # Get detailed status for display - use threaded call to avoid blocking GUI
                def get_status_and_update():
                    """Get telescope status in background thread."""
                    try:
                        status_info = self.scheduler.get_telescope_status()
                        status_text = "✓ Connected\nBasic Info"
                        
                        if status_info.get("connected", False):
                            model = status_info.get('model', 'DWARF3')
                            api_mode = status_info.get('api_mode', 'HTTP')
                            status_text = f"✓ {model}\nMode: {api_mode}\nConnected"
                        
                        # Update GUI from main thread
                        self.frame.after(0, lambda: self.update_telescope_status_display(status_text))
                    except Exception as e:
                        self.logger.error(f"Error getting telescope status: {e}")
                        self.frame.after(0, lambda: self.update_telescope_status_display("✓ Connected\nStatus Unknown"))
                
                # Start status update in background
                import threading
                threading.Thread(target=get_status_and_update, daemon=True).start()
                
                # Immediately show basic connected status
                self.update_telescope_status_display("✓ Connected\nGetting Info...")
                
            else:
                self.add_log_message("ERROR", f"Connection failed: {message}")
                self.update_telescope_status_display("✗ Connection Failed")
                
            # Update button states regardless of result
            self.update_button_states()
            
        except Exception as e:
            self.logger.error(f"Error handling connection result: {e}")
            self.add_log_message("ERROR", f"Error handling connection: {e}")
            
    def remove_from_queue(self):
        """Remove selected session from queue (only works for Queued sessions)."""
        selection = self.schedule_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to remove.")
            return
            
        item = self.schedule_tree.item(selection[0])
        values = item["values"]
        
        if not values:
            return
            
        target_name = values[1]
        status = values[2]
        
        # Only allow removal of queued sessions
        if status != "Queued":
            messagebox.showwarning("Invalid Action", 
                                 f"Cannot remove {status.lower()} sessions from queue.\n"
                                 f"Only 'Queued' sessions can be removed.\n"
                                 f"Use 'Reset to Available' for completed/failed sessions.")
            return
            
        if messagebox.askyesno("Confirm", f"Remove '{target_name}' from queue and move back to Available?"):
            try:
                start_time = values[0]
                
                # Find the session file in ToDo directory
                success = self._find_and_move_session(target_name, start_time, "ToDo", "Available")
                
                if success:
                    self.refresh_schedule()
                    self.log_scheduler_event("info", f"Session '{target_name}' removed from queue and moved to Available")
                else:
                    messagebox.showerror("Error", "Failed to move session back to Available folder!")
                    
            except Exception as e:
                self.logger.error(f"Error removing session from queue: {e}")
                messagebox.showerror("Error", f"Failed to remove session: {e}")
    
    def reset_to_available(self):
        """Reset selected session to Available status (works for Done/Failed sessions)."""
        selection = self.schedule_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to reset.")
            return
            
        item = self.schedule_tree.item(selection[0])
        values = item["values"]
        
        if not values:
            return
            
        target_name = values[1]
        status = values[2]
        
        # Only allow reset of completed/failed sessions
        if status not in ["Completed", "Failed"]:
            messagebox.showwarning("Invalid Action", 
                                 f"Cannot reset {status.lower()} sessions.\n"
                                 f"Only 'Completed' or 'Failed' sessions can be reset to Available.")
            return
            
        if messagebox.askyesno("Confirm", f"Reset '{target_name}' to Available for re-scheduling?"):
            try:
                start_time = values[0]
                
                # Determine source directory based on status
                source_dir = "Done" if status == "Completed" else "Failed"
                
                # Move session back to Available
                success = self._find_and_move_session(target_name, start_time, source_dir, "Available")
                
                if success:
                    self.refresh_schedule()
                    self.log_scheduler_event("info", f"Session '{target_name}' reset to Available from {status}")
                else:
                    messagebox.showerror("Error", f"Failed to reset session to Available!")
                    
            except Exception as e:
                self.logger.error(f"Error resetting session: {e}")
                messagebox.showerror("Error", f"Failed to reset session: {e}")
    
    def delete_session_from_schedule(self):
        """Delete selected session permanently."""
        selection = self.schedule_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to delete.")
            return
            
        item = self.schedule_tree.item(selection[0])
        values = item["values"]
        
        if not values:
            return
            
        target_name = values[1]
        status = values[2]
        
        # Don't allow deletion of running sessions
        if status == "Running":
            messagebox.showwarning("Invalid Action", "Cannot delete running sessions. Please wait for completion or stop the scheduler.")
            return
            
        if messagebox.askyesno("Confirm Delete", 
                              f"Permanently delete session '{target_name}'?\n"
                              f"This action cannot be undone."):
            try:
                start_time = values[0]
                
                # Determine source directory based on status
                status_to_dir = {
                    "Queued": "ToDo",
                    "Completed": "Done", 
                    "Failed": "Failed"
                }
                source_dir = status_to_dir.get(status)
                
                if source_dir:
                    success = self._find_and_delete_session(target_name, start_time, source_dir)
                    
                    if success:
                        self.refresh_schedule()
                        self.log_scheduler_event("info", f"Session '{target_name}' deleted permanently")
                    else:
                        messagebox.showerror("Error", "Failed to delete session!")
                else:
                    messagebox.showerror("Error", f"Cannot delete session with status: {status}")
                    
            except Exception as e:
                self.logger.error(f"Error deleting session: {e}")
                messagebox.showerror("Error", f"Failed to delete session: {e}")
    
    def _find_and_move_session(self, target_name, start_time, from_dir, to_dir):
        """Helper method to find and move a session between directories."""
        try:
            sessions_path = f"Sessions/{from_dir}"
            if not os.path.exists(sessions_path):
                return False
                
            for filename in os.listdir(sessions_path):
                if filename.endswith('.json'):
                    session_data = self.session_manager.load_session(filename, sessions_path)
                    if (session_data and 
                        session_data.get("target_name") == target_name and 
                        session_data.get("start_time") == start_time):
                        
                        return self.session_manager.move_session(filename, from_dir, to_dir)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error finding/moving session: {e}")
            return False
    
    def _find_and_delete_session(self, target_name, start_time, source_dir):
        """Helper method to find and delete a session."""
        try:
            sessions_path = f"Sessions/{source_dir}"
            if not os.path.exists(sessions_path):
                return False
                
            for filename in os.listdir(sessions_path):
                if filename.endswith('.json'):
                    session_data = self.session_manager.load_session(filename, sessions_path)
                    if (session_data and 
                        session_data.get("target_name") == target_name and 
                        session_data.get("start_time") == start_time):
                        
                        return self.session_manager.delete_session(filename, sessions_path)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error finding/deleting session: {e}")
            return False
        
    def add_log_message(self, level, message):
        """Add a message to the log output with timestamp and formatting."""
        if not hasattr(self, 'log_text'):
            return
            
        # Filter by log level if specified
        level_hierarchy = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        current_level = self.log_level_var.get() if hasattr(self, 'log_level_var') else "INFO"
        
        if level_hierarchy.get(level, 1) < level_hierarchy.get(current_level, 1):
            return
            
        # Add timestamp
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}\n"
        
        # Insert message with appropriate color
        self.log_text.insert(tk.END, formatted_message, level)
        
        # Auto-scroll if enabled
        if hasattr(self, 'auto_scroll_var') and self.auto_scroll_var.get():
            self.log_text.see(tk.END)
            
        # Limit log size to prevent memory issues (keep last 1000 lines)
        lines = self.log_text.get("1.0", tk.END).split('\n')
        if len(lines) > 1000:
            # Remove oldest lines
            lines_to_remove = len(lines) - 1000
            self.log_text.delete("1.0", f"{lines_to_remove}.0")
            
    def add_colored_log_message(self, level, indicator, indicator_tag, message):
        """Add a message with colored indicator to the log output."""
        if not hasattr(self, 'log_text'):
            return
            
        # Filter by log level if specified
        level_hierarchy = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        current_level = self.log_level_var.get() if hasattr(self, 'log_level_var') else "INFO"
        
        if level_hierarchy.get(level, 1) < level_hierarchy.get(current_level, 1):
            return
            
        # Add timestamp and level
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}] {level}: "
        
        # Insert the prefix with level color
        self.log_text.insert(tk.END, prefix, level)
        
        # Insert the colored indicator
        self.log_text.insert(tk.END, indicator, indicator_tag)
        
        # Insert the rest of the message with level color
        self.log_text.insert(tk.END, f"{message}\n", level)
        
        # Auto-scroll if enabled
        if hasattr(self, 'auto_scroll_var') and self.auto_scroll_var.get():
            self.log_text.see(tk.END)
            
        # Limit log size to prevent memory issues (keep last 1000 lines)
        lines = self.log_text.get("1.0", tk.END).split('\n')
        if len(lines) > 1000:
            # Remove oldest lines
            lines_to_remove = len(lines) - 1000
            self.log_text.delete("1.0", f"{lines_to_remove}.0")
            
    def save_log(self):
        """Save current log content to file."""
        if not hasattr(self, 'log_text'):
            return
            
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            title="Save Session Log",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    content = self.log_text.get("1.0", tk.END)
                    f.write(content)
                self.add_log_message("INFO", f"Log saved to {filename}")
            except Exception as e:
                self.add_log_message("ERROR", f"Failed to save log: {e}")
                messagebox.showerror("Save Error", f"Failed to save log file:\n{e}")
                
    def log_scheduler_event(self, event_type, message):
        """Log scheduler events with appropriate formatting."""
        if event_type == "start":
            self.add_colored_log_message("INFO", "[START]", "START_TAG", f" Scheduler started: {message}")
        elif event_type == "stop":
            self.add_colored_log_message("INFO", "[STOP]", "STOP_TAG", f" Scheduler stopped: {message}")
        elif event_type == "session_start":
            self.add_colored_log_message("INFO", "[SESSION]", "SESSION_TAG", f" Session started: {message}")
        elif event_type == "session_complete":
            self.add_colored_log_message("SUCCESS", "[COMPLETE]", "COMPLETE_TAG", f" Session completed: {message}")
        elif event_type == "session_error":
            self.add_colored_log_message("ERROR", "[ERROR]", "ERROR_TAG", f" Session error: {message}")
        elif event_type == "warning":
            self.add_colored_log_message("WARNING", "[WARNING]", "WARNING_TAG", f" Warning: {message}")
        elif event_type == "info":
            self.add_colored_log_message("INFO", "[INFO]", "INFO_TAG", f" {message}")
        else:
            self.add_log_message("DEBUG", message)
            
    def on_scheduler_status_update(self, status_message):
        """Callback for scheduler status updates."""
        # This method will be called by the scheduler to provide status updates
        self.add_log_message("INFO", status_message)
        
        # Update the scheduler status display and button states
        self.update_scheduler_status()
        
        # Update button states after status changes
        self.update_button_states()
        
    def on_scheduler_session_update(self, session_data):
        """Callback for scheduler session updates."""
        # This method will be called by the scheduler to provide session updates
        session_name = session_data.get("target_name", "Unknown")
        status = session_data.get("status", "Unknown")
        
        if status == "starting":
            self.log_scheduler_event("session_start", f"{session_name} - Session initialization")
        elif status == "capturing":
            frames = session_data.get("frames_captured", 0)
            total_frames = session_data.get("frame_count", 0)
            self.log_scheduler_event("info", f"{session_name} - Capturing frame {frames}/{total_frames}")
        elif status == "completed":
            frames = session_data.get("frames_captured", 0)
            duration = session_data.get("duration", "Unknown")
            self.log_scheduler_event("session_complete", f"{session_name} - {frames} frames captured in {duration}")
        elif status == "failed":
            error = session_data.get("error", "Unknown error")
            self.log_scheduler_event("session_error", f"{session_name} - {error}")
        elif status == "cancelled":
            self.log_scheduler_event("warning", f"{session_name} - Session cancelled")
        else:
            self.log_scheduler_event("info", f"{session_name} - {status}")
            
        # Refresh the schedule display to show updated status
        self.refresh_schedule()
        
    def test_telescope_connection(self):
        """Test telescope connection in background."""
        try:
            self.add_log_message("INFO", "Testing telescope connection...")
            
            # Disable button during test and change text
            if hasattr(self, 'test_connection_button'):
                self.test_connection_button.config(state=tk.DISABLED, text="Testing...")
            
            def test_callback(success, message):
                """Handle test result."""
                self.frame.after(0, lambda: [
                    self._restore_test_button(),
                    self._handle_test_result(success, message)
                ])
            
            # Use shorter timeout for testing - this is a one-time test, not a keepalive
            self.scheduler.dwarf_controller.test_connection(callback=test_callback)
            
        except Exception as e:
            self.add_log_message("ERROR", f"Error testing connection: {e}")
            self._restore_test_button()
    
    def _restore_test_button(self):
        """Restore test button to normal state."""
        if hasattr(self, 'test_connection_button'):
            self.test_connection_button.config(state=tk.NORMAL, text="Test Connection")
    
    def _handle_test_result(self, success, message):
        """Handle test connection result."""
        try:
            if success:
                self.add_log_message("INFO", f"Connection test successful: {message}")
                self.update_telescope_status_display("✓ Test Successful")
            else:
                self.add_log_message("ERROR", f"Connection test failed: {message}")
                self.update_telescope_status_display("✗ Test Failed")
                
            # Update button states after test
            self.update_button_states()
            
        except Exception as e:
            self.logger.error(f"Error handling test result: {e}")
            self.add_log_message("ERROR", f"Error handling test: {e}")
    
    def update_telescope_status_display(self, status_text):
        """Update the telescope status display."""
        try:
            self.telescope_status_text.config(state=tk.NORMAL)
            self.telescope_status_text.delete("1.0", tk.END)
            self.telescope_status_text.insert("1.0", status_text)
            self.telescope_status_text.config(state=tk.DISABLED)
        except Exception as e:
            self.logger.error(f"Failed to update telescope status display: {e}")
    
    def start_periodic_telescope_status_update(self):
        """Start periodic telescope status updates."""
        def update_status():
            # Check if updates are still active
            if not self.periodic_updates_active:
                return
                
            try:
                if hasattr(self, 'telescope_status_text'):
                    # Get status in background thread to avoid GUI blocking
                    def get_status_threaded():
                        """Get telescope status in background thread."""
                        try:
                            status_info = self.scheduler.get_telescope_status()
                            
                            # Update GUI from main thread
                            self.frame.after(0, lambda: self._update_periodic_status(status_info))
                        except Exception as e:
                            self.logger.error(f"Error getting telescope status: {e}")
                            # Update GUI with error state
                            self.frame.after(0, lambda: self._update_periodic_status({"connected": False, "error": True}))
                    
                    # Start status retrieval in background thread
                    import threading
                    threading.Thread(target=get_status_threaded, daemon=True).start()
                    
            except Exception as e:
                self.logger.error(f"Error in periodic telescope status update: {e}")
            
            # Schedule next update - more frequent during connection attempts, less frequent otherwise
            if self.periodic_updates_active:
                controller = self.scheduler.dwarf_controller
                # Check if connecting - if so, update more frequently for responsive UI
                if hasattr(controller, 'connecting') and controller.connecting:
                    update_interval = 2000  # 2 seconds during connection attempts
                else:
                    update_interval = 30000  # 30 seconds during normal operation
                    
                self.frame.after(update_interval, update_status)
        
        # Start the periodic updates
        self.frame.after(10000, update_status)  # First update after 10 seconds
    
    def _update_periodic_status(self, status_info):
        """Update periodic status display (called from main thread)."""
        try:
            if status_info.get("connected", False):
                model = status_info.get('model', 'DWARF3')
                api_mode = status_info.get('api_mode', 'HTTP')
                
                # Create compact status display
                status_text = f"✓ {model}\n"
                status_text += f"Mode: {api_mode}\n"
                
                # Add key info if available
                if 'firmware_version' in status_info and status_info['firmware_version'] != "Connected via API":
                    fw = status_info['firmware_version'][:10]
                    status_text += f"FW: {fw}\n"
                
                if api_mode == "dwarf_python_api":
                    status_text += "Real-time: ✓"
                else:
                    status_text += "Basic: ✓"
                    
            else:
                status_text = "✗ Disconnected"
            
            self.update_telescope_status_display(status_text)
            
            # Also update button states to handle connecting/connected/disconnected states
            self.update_button_states()
            
        except Exception as e:
            self.logger.error(f"Error updating periodic status display: {e}")
    
    def stop_periodic_updates(self):
        """Stop periodic telescope status updates."""
        self.periodic_updates_active = False
