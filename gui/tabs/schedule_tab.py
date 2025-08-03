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
        
        # Set up scheduler callbacks for real-time log updates
        self.scheduler.set_status_callback(self.on_scheduler_status_update)
        self.scheduler.set_session_callback(self.on_scheduler_session_update)
        
        self.create_widgets()
        self.refresh_schedule()
        
    def create_widgets(self):
        """Create and layout widgets for the schedule tab."""
        self.frame = ttk.Frame(self.parent)
        
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
        paned.add(left_frame, weight=1)
        
        # Schedule controls
        controls_frame = ttk.Frame(left_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(
            controls_frame, 
            text="Start Scheduler", 
            command=self.start_scheduler
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            controls_frame, 
            text="Stop Scheduler", 
            command=self.stop_scheduler
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            controls_frame, 
            text="Refresh", 
            command=self.refresh_schedule
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            controls_frame, 
            text="Clear Log", 
            command=self.clear_log
        ).pack(side=tk.LEFT, padx=(5, 0))
        
        # Schedule tree
        self.create_schedule_tree(left_frame)
        
        # Right panel - Session details
        right_frame = ttk.LabelFrame(paned, text="Session Details", padding=10)
        paned.add(right_frame, weight=1)
        
        self.create_session_details(right_frame)
        
        # Bottom section - Session log output (40% of total height)
        log_frame = ttk.LabelFrame(main_paned, text="Session Log Output", padding=10)
        main_paned.add(log_frame, weight=2)  # 40% of total height
        
        self.create_log_output(log_frame)
        
    def create_schedule_tree(self, parent):
        """Create the schedule queue tree view."""
        # Tree view for scheduled sessions
        columns = ("time", "target", "status", "frames", "exposure")
        self.schedule_tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.schedule_tree.heading("time", text="Start Time")
        self.schedule_tree.heading("target", text="Target")
        self.schedule_tree.heading("status", text="Status")
        self.schedule_tree.heading("frames", text="Frames")
        self.schedule_tree.heading("exposure", text="Exposure")
        
        self.schedule_tree.column("time", width=150)
        self.schedule_tree.column("target", width=120)
        self.schedule_tree.column("status", width=100)
        self.schedule_tree.column("frames", width=80)
        self.schedule_tree.column("exposure", width=80)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.schedule_tree.yview)
        tree_scroll_x = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.schedule_tree.xview)
        self.schedule_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        # Pack tree and scrollbars
        self.schedule_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind events
        self.schedule_tree.bind("<<TreeviewSelect>>", self.on_schedule_select)
        
    def create_session_details(self, parent):
        """Create session details panel."""
        # Details text widget
        self.details_text = tk.Text(parent, height=20, width=40, wrap=tk.WORD)
        details_scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scroll.set)
        
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Session control buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame, 
            text="Remove from Queue", 
            command=self.remove_from_queue
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Move Up", 
            command=self.move_up
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Move Down", 
            command=self.move_down
        ).pack(side=tk.LEFT)
        
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
        
        # Save log button
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
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='white'
        )
        
        log_scroll_y = ttk.Scrollbar(log_text_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll_x = ttk.Scrollbar(log_text_frame, orient=tk.HORIZONTAL, command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=log_scroll_y.set, xscrollcommand=log_scroll_x.set)
        
        # Pack log text and scrollbars
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        log_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Configure text tags for different log levels
        self.log_text.tag_config("DEBUG", foreground="#808080")
        self.log_text.tag_config("INFO", foreground="#ffffff")
        self.log_text.tag_config("WARNING", foreground="#ffaa00")
        self.log_text.tag_config("ERROR", foreground="#ff4444")
        self.log_text.tag_config("SUCCESS", foreground="#44ff44")
        
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
            
        # Load scheduled sessions
        scheduled_sessions = self.session_manager.get_scheduled_sessions()
        
        # Log the refresh activity
        if hasattr(self, 'add_log_message'):
            self.add_log_message("DEBUG", f"Schedule refreshed - {len(scheduled_sessions)} sessions in queue")
        
        for session in scheduled_sessions:
            self.schedule_tree.insert("", tk.END, values=(
                session.get("start_time", ""),
                session.get("target_name", ""),
                session.get("status", "Queued"),
                session.get("frame_count", ""),
                f"{session.get('exposure_time', '')}s"
            ))
            
    def on_schedule_select(self, event):
        """Handle schedule tree selection."""
        selection = self.schedule_tree.selection()
        if not selection:
            return
            
        item = self.schedule_tree.item(selection[0])
        values = item["values"]
        
        if values:
            # Display session details
            details = f"""Selected Session Details:

Start Time: {values[0]}
Target: {values[1]}
Status: {values[2]}
Frame Count: {values[3]}
Exposure: {values[4]}

Session will be executed when scheduled time arrives.
The telescope will automatically:
1. Move to target coordinates
2. Perform calibration if needed
3. Capture specified frames
4. Save results to history
"""
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, details)
            
    def start_scheduler(self):
        """Start the scheduling engine."""
        try:
            self.scheduler.start()
            self.log_scheduler_event("start", "Telescope scheduling engine activated")
            messagebox.showinfo("Scheduler", "Scheduler started successfully!")
            self.logger.info("Scheduler started")
        except Exception as e:
            self.log_scheduler_event("session_error", f"Failed to start scheduler: {e}")
            messagebox.showerror("Error", f"Failed to start scheduler: {e}")
            self.logger.error(f"Failed to start scheduler: {e}")
            
    def stop_scheduler(self):
        """Stop the scheduling engine."""
        try:
            self.scheduler.stop()
            self.log_scheduler_event("stop", "Telescope scheduling engine deactivated")
            messagebox.showinfo("Scheduler", "Scheduler stopped successfully!")
            self.logger.info("Scheduler stopped")
        except Exception as e:
            self.log_scheduler_event("session_error", f"Failed to stop scheduler: {e}")
            messagebox.showerror("Error", f"Failed to stop scheduler: {e}")
            self.logger.error(f"Failed to stop scheduler: {e}")
            
    def remove_from_queue(self):
        """Remove selected session from queue."""
        selection = self.schedule_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to remove.")
            return
            
        if messagebox.askyesno("Confirm", "Remove selected session from queue?"):
            try:
                # Get the selected session data from the tree
                item = self.schedule_tree.item(selection[0])
                values = item["values"]
                
                if values:
                    target_name = values[1]  # Target name is in column 1
                    start_time = values[0]   # Start time is in column 0
                    
                    # Find the corresponding session file in ToDo folder
                    scheduled_sessions = self.session_manager.get_scheduled_sessions()
                    session_to_remove = None
                    filename_to_move = None
                    
                    for session in scheduled_sessions:
                        if (session.get("target_name") == target_name and 
                            session.get("start_time") == start_time):
                            session_to_remove = session
                            # Try to use the actual filename from the session's created date or a more reliable method
                            # For now, we'll search for the file that matches this session
                            break
                    
                    if session_to_remove:
                        # Find the actual filename in the ToDo directory
                        todo_dir = "Sessions/ToDo"
                        if os.path.exists(todo_dir):
                            for filename in os.listdir(todo_dir):
                                if filename.endswith('.json'):
                                    session_data = self.session_manager.load_session(filename, todo_dir)
                                    if (session_data and 
                                        session_data.get("target_name") == target_name and 
                                        session_data.get("start_time") == start_time):
                                        filename_to_move = filename
                                        break
                        
                        if filename_to_move:
                            # Move session back from ToDo to Available
                            success = self.session_manager.move_session(filename_to_move, "ToDo", "Available")
                        else:
                            success = False
                        
                        if success:
                            # Refresh the schedule display
                            self.refresh_schedule()
                            self.log_scheduler_event("info", f"Session '{target_name}' removed from queue and moved to Available")
                            self.logger.info(f"Session '{target_name}' removed from queue and moved back to Available")
                            messagebox.showinfo("Success", f"Session '{target_name}' removed from schedule!")
                        else:
                            messagebox.showerror("Error", "Failed to move session back to Available folder!")
                    else:
                        # If we can't find the session file, just refresh the display
                        self.refresh_schedule()
                        self.logger.warning("Session removed from display but file not found")
                        
            except Exception as e:
                self.logger.error(f"Error removing session from queue: {e}")
                messagebox.showerror("Error", f"Failed to remove session: {e}")
            
    def move_up(self):
        """Move selected session up in queue."""
        selection = self.schedule_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to move.")
            return
            
        # Implementation for moving session up
        self.logger.info("Session moved up in queue")
        
    def move_down(self):
        """Move selected session down in queue."""
        selection = self.schedule_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to move.")
            return
            
        # Implementation for moving session down
        self.logger.info("Session moved down in queue")
        
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
                messagebox.showinfo("Log Saved", f"Session log saved to:\n{filename}")
            except Exception as e:
                self.add_log_message("ERROR", f"Failed to save log: {e}")
                messagebox.showerror("Save Error", f"Failed to save log file:\n{e}")
                
    def log_scheduler_event(self, event_type, message):
        """Log scheduler events with appropriate formatting."""
        if event_type == "start":
            self.add_log_message("INFO", f"🚀 Scheduler started: {message}")
        elif event_type == "stop":
            self.add_log_message("INFO", f"⏹️ Scheduler stopped: {message}")
        elif event_type == "session_start":
            self.add_log_message("INFO", f"📡 Session started: {message}")
        elif event_type == "session_complete":
            self.add_log_message("SUCCESS", f"✅ Session completed: {message}")
        elif event_type == "session_error":
            self.add_log_message("ERROR", f"❌ Session error: {message}")
        elif event_type == "warning":
            self.add_log_message("WARNING", f"⚠️ Warning: {message}")
        elif event_type == "info":
            self.add_log_message("INFO", f"ℹ️ {message}")
        else:
            self.add_log_message("DEBUG", message)
            
    def on_scheduler_status_update(self, status_message):
        """Callback for scheduler status updates."""
        # This method will be called by the scheduler to provide status updates
        self.add_log_message("INFO", status_message)
        
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
