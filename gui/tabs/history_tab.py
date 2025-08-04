"""
History Tab - Display and manage session history with statistics.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from core.history_manager import HistoryManager


class HistoryTab:
    """History tab for displaying session history and statistics."""
    
    def __init__(self, parent, config_manager):
        self.parent = parent
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Create main frame first
        self.frame = ttk.Frame(self.parent)
        
        # Variables for filters
        self.date_from_var = tk.StringVar()
        self.date_to_var = tk.StringVar()
        self.target_filter_var = tk.StringVar()
        self.status_filter_var = tk.StringVar(value="All")
        
        # Initialize history manager
        try:
            self.history_manager = HistoryManager(config_manager=config_manager)
            self.logger.info("HistoryManager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize HistoryManager: {e}")
            self.history_manager = None
        
        # Create widgets
        self.create_widgets()
        
        # Initial refresh
        if self.history_manager:
            self.logger.info("Initializing history tab - refreshing files and history")
            self.refresh_history_files()
            self.refresh_history()
        else:
            self.logger.error("History manager not available during initialization")
        
    def create_widgets(self):
        """Create and arrange the history tab widgets."""
        self.frame = ttk.Frame(self.parent)
        
        # Main container with paned window - matching sessions tab style
        paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - History files and controls
        left_frame = ttk.LabelFrame(paned, text="History Files", padding=10)
        paned.add(left_frame, weight=1)
        
        self.create_history_files_panel(left_frame)
        
        # Right panel - History display and details
        right_frame = ttk.LabelFrame(paned, text="Session History", padding=10)
        paned.add(right_frame, weight=2)
        
        # Create notebook for organizing right panel sections
        right_notebook = ttk.Notebook(right_frame)
        right_notebook.pack(fill=tk.BOTH, expand=True)
        
        # History View Tab - Main history display with filters and tree
        history_view_frame = ttk.Frame(right_notebook)
        right_notebook.add(history_view_frame, text="History View")
        
        # Create vertical paned window for history view
        history_paned = ttk.PanedWindow(history_view_frame, orient=tk.VERTICAL)
        history_paned.pack(fill=tk.BOTH, expand=True)
        
        # Top section - filters and history tree
        top_frame = ttk.Frame(history_paned)
        history_paned.add(top_frame, weight=3)
        
        self.create_filter_controls(top_frame)
        self.create_history_tree(top_frame)
        
        # Bottom section - details
        details_frame = ttk.Frame(history_paned)
        history_paned.add(details_frame, weight=2)
        
        self.create_details_panel(details_frame)
        
        # Statistics Tab
        stats_frame = ttk.Frame(right_notebook)
        right_notebook.add(stats_frame, text="Statistics")
        
        self.create_statistics_panel(stats_frame)
        
    def create_history_files_panel(self, parent):
        """Create history files list panel."""
        self.logger.info("Creating history files panel...")
        
        # Control buttons - matching sessions tab style
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(
            button_frame, 
            text="Load All", 
            command=self.load_all_files
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Load Selected", 
            command=self.load_selected_file
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Delete", 
            command=self.delete_selected_file
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame, 
            text="Refresh", 
            command=self.refresh_history_files
        ).pack(side=tk.LEFT)
        
        # Files list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Listbox with scrollbar - matching sessions tab style
        self.files_listbox = tk.Listbox(list_frame, height=20)
        files_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.files_listbox.yview)
        self.files_listbox.configure(yscrollcommand=files_scroll.set)
        
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        files_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind events
        self.files_listbox.bind("<<ListboxSelect>>", self.on_file_select)
        self.files_listbox.bind("<Double-Button-1>", self.on_file_double_click)
        
        # File info display
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(info_frame, text="File Information:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        
        self.file_info_label = ttk.Label(
            info_frame, 
            text="Select a file to view details", 
            justify=tk.LEFT, 
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.file_info_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Context menu
        self.create_files_context_menu()
        
    def create_files_context_menu(self):
        """Create context menu for files list."""
        self.files_context_menu = tk.Menu(self.files_listbox, tearoff=0)
        self.files_context_menu.add_command(label="Load File", command=self.load_selected_file)
        self.files_context_menu.add_command(label="Load All Files", command=self.load_all_files)
        self.files_context_menu.add_separator()
        self.files_context_menu.add_command(label="Delete File", command=self.delete_selected_file)
        self.files_context_menu.add_command(label="Refresh List", command=self.refresh_history_files)
        
        self.files_listbox.bind("<Button-3>", self.show_files_context_menu)
        
    def show_files_context_menu(self, event):
        """Show files context menu."""
        try:
            self.files_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.files_context_menu.grab_release()
        
    def create_filter_controls(self, parent):
        """Create filter controls for history display."""
        # Filter controls frame
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # First row - date filters
        row1 = ttk.Frame(filter_frame)
        row1.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(row1, text="From:").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.date_from_var, width=12).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(row1, text="To:").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.date_to_var, width=12).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(row1, text="Target:").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.target_filter_var, width=15).pack(side=tk.LEFT, padx=(5, 0))
        
        # Second row - status and buttons
        row2 = ttk.Frame(filter_frame)
        row2.pack(fill=tk.X)
        
        ttk.Label(row2, text="Status:").pack(side=tk.LEFT)
        status_combo = ttk.Combobox(
            row2, 
            textvariable=self.status_filter_var, 
            values=["All", "Completed", "Failed", "Cancelled"], 
            width=12,
            state="readonly"
        )
        status_combo.pack(side=tk.LEFT, padx=(5, 15))
        
        # Control buttons
        ttk.Button(row2, text="Apply Filter", command=self.apply_filter).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row2, text="Clear", command=self.clear_filter).pack(side=tk.LEFT, padx=(0, 15))
        
        # Utility buttons
        ttk.Button(row2, text="Refresh", command=self.refresh_history).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(row2, text="Export CSV", command=self.export_csv).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(row2, text="Clear History", command=self.clear_history).pack(side=tk.RIGHT, padx=(5, 0))
        
    def create_history_tree(self, parent):
        """Create the history tree view."""
        # Tree container
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview
        columns = ("date", "time", "target", "status", "frames", "exposure", "duration", "size")
        self.history_tree = ttk.Treeview(
            tree_frame, 
            columns=columns, 
            show="headings", 
            height=15
        )
        
        # Configure columns
        column_config = [
            ("date", "Date", 100),
            ("time", "Time", 80),
            ("target", "Target", 140),
            ("status", "Status", 90),
            ("frames", "Frames", 80),
            ("exposure", "Exposure", 90),
            ("duration", "Duration", 90),
            ("size", "File Size", 90)
        ]
        
        for col_id, header, width in column_config:
            self.history_tree.heading(col_id, text=header)
            self.history_tree.column(col_id, width=width, anchor=tk.CENTER)
        
        # Create scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.history_tree.xview)
        self.history_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        # Pack scrollbars first, then tree
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind events
        self.history_tree.bind("<<TreeviewSelect>>", self.on_history_select)
        self.history_tree.bind("<Double-1>", self.on_history_double_click)
        
        # Context menu
        self.create_context_menu()
        
    def create_details_panel(self, parent):
        """Create session details panel."""
        # Create notebook for details sections
        details_notebook = ttk.Notebook(parent)
        details_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Session details tab
        details_frame = ttk.Frame(details_notebook)
        details_notebook.add(details_frame, text="Session Details")
        
        # Create horizontal paned window for side-by-side details
        details_paned = ttk.PanedWindow(details_frame, orient=tk.HORIZONTAL)
        details_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left side - session info
        left_details = ttk.Frame(details_paned)
        details_paned.add(left_details, weight=1)
        
        ttk.Label(left_details, text="Session Information", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        self.details_text = tk.Text(
            left_details, 
            height=10, 
            width=40, 
            wrap=tk.WORD,
            font=("Segoe UI", 9)
        )
        details_scroll = ttk.Scrollbar(left_details, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scroll.set)
        
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Right side - settings used
        right_details = ttk.Frame(details_paned)
        details_paned.add(right_details, weight=1)
        
        ttk.Label(right_details, text="Settings Used", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        self.settings_text = tk.Text(
            right_details, 
            height=10, 
            width=40, 
            wrap=tk.WORD,
            font=("Segoe UI", 9)
        )
        settings_scroll = ttk.Scrollbar(right_details, orient=tk.VERTICAL, command=self.settings_text.yview)
        self.settings_text.configure(yscrollcommand=settings_scroll.set)
        
        self.settings_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        settings_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
    def create_statistics_panel(self, parent):
        """Create statistics display panel."""
        stats_main = ttk.Frame(parent)
        stats_main.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Summary statistics header
        summary_header = ttk.Label(stats_main, text="Summary Statistics", font=("Segoe UI", 10, "bold"))
        summary_header.pack(anchor=tk.W, pady=(0, 10))
        
        # Summary statistics container
        summary_frame = ttk.Frame(stats_main)
        summary_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Create statistics labels
        stats_grid = ttk.Frame(summary_frame)
        stats_grid.pack(fill=tk.X)
        
        # Total sessions
        ttk.Label(stats_grid, text="Total Sessions:").grid(row=0, column=0, sticky=tk.W, padx=(0, 20))
        self.total_sessions_label = ttk.Label(stats_grid, text="0")
        self.total_sessions_label.grid(row=0, column=1, sticky=tk.W)
        
        # Successful sessions
        ttk.Label(stats_grid, text="Successful:").grid(row=0, column=2, sticky=tk.W, padx=(20, 20))
        self.successful_sessions_label = ttk.Label(stats_grid, text="0")
        self.successful_sessions_label.grid(row=0, column=3, sticky=tk.W)
        
        # Total frames
        ttk.Label(stats_grid, text="Total Frames:").grid(row=1, column=0, sticky=tk.W, padx=(0, 20))
        self.total_frames_label = ttk.Label(stats_grid, text="0")
        self.total_frames_label.grid(row=1, column=1, sticky=tk.W)
        
        # Total exposure time
        ttk.Label(stats_grid, text="Total Exposure:").grid(row=1, column=2, sticky=tk.W, padx=(20, 20))
        self.total_exposure_label = ttk.Label(stats_grid, text="0h 0m")
        self.total_exposure_label.grid(row=1, column=3, sticky=tk.W)
        
        # Most captured target
        ttk.Label(stats_grid, text="Most Captured:").grid(row=2, column=0, sticky=tk.W, padx=(0, 20))
        self.most_captured_label = ttk.Label(stats_grid, text="-")
        self.most_captured_label.grid(row=2, column=1, sticky=tk.W)
        
        # Average session duration
        ttk.Label(stats_grid, text="Avg Duration:").grid(row=2, column=2, sticky=tk.W, padx=(20, 20))
        self.avg_duration_label = ttk.Label(stats_grid, text="0m")
        self.avg_duration_label.grid(row=2, column=3, sticky=tk.W)
        
        # Monthly breakdown header
        monthly_header = ttk.Label(stats_main, text="Monthly Breakdown", font=("Segoe UI", 10, "bold"))
        monthly_header.pack(anchor=tk.W, pady=(15, 10))
        
        # Monthly breakdown container
        monthly_frame = ttk.Frame(stats_main)
        monthly_frame.pack(fill=tk.BOTH, expand=True)
        
        # Monthly stats tree
        monthly_columns = ("month", "sessions", "frames", "exposure", "success_rate")
        self.monthly_tree = ttk.Treeview(monthly_frame, columns=monthly_columns, show="headings", height=8)
        
        self.monthly_tree.heading("month", text="Month")
        self.monthly_tree.heading("sessions", text="Sessions")
        self.monthly_tree.heading("frames", text="Frames")
        self.monthly_tree.heading("exposure", text="Exposure")
        self.monthly_tree.heading("success_rate", text="Success %")
        
        self.monthly_tree.column("month", width=100)
        self.monthly_tree.column("sessions", width=80)
        self.monthly_tree.column("frames", width=80)
        self.monthly_tree.column("exposure", width=100)
        self.monthly_tree.column("success_rate", width=80)
        
        monthly_scroll = ttk.Scrollbar(monthly_frame, orient=tk.VERTICAL, command=self.monthly_tree.yview)
        self.monthly_tree.configure(yscrollcommand=monthly_scroll.set)
        
        self.monthly_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        monthly_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
    def create_context_menu(self):
        """Create context menu for history tree."""
        self.context_menu = tk.Menu(self.history_tree, tearoff=0)
        self.context_menu.add_command(label="View Details", command=self.view_details)
        self.context_menu.add_command(label="Open Files", command=self.open_files)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Repeat Session", command=self.repeat_session)
        self.context_menu.add_command(label="Export Session", command=self.export_session)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete Entry", command=self.delete_entry)
        
        self.history_tree.bind("<Button-3>", self.show_context_menu)
        
    def show_context_menu(self, event):
        """Show context menu."""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
            
    def refresh_history(self):
        """Refresh the history display."""
        if not hasattr(self, 'history_manager') or self.history_manager is None:
            # If history manager failed to initialize, show error message
            self.show_error_message("History Manager not available")
            return
            
        if not hasattr(self, 'history_tree'):
            # If widgets haven't been created yet, skip refresh
            return
            
        # Clear current items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
            
        # Load history data
        try:
            history_data = self.history_manager.get_history()
            
            for record in history_data:
                self.history_tree.insert("", tk.END, values=(
                    record.get("date", ""),
                    record.get("time", ""),
                    record.get("target", ""),
                    record.get("status", ""),
                    record.get("frames_captured", ""),
                    f"{record.get('exposure_time', '')}s",
                    record.get("duration", ""),
                    record.get("file_size", "")
                ))
                
            # Update statistics
            self.update_statistics()
            
            # Also refresh the files list
            self.refresh_history_files()
            
        except Exception as e:
            self.logger.error(f"Failed to refresh history: {e}")
            self.show_error_message(f"Failed to load history: {e}")
    
    def show_error_message(self, message):
        """Show error message in the tab."""
        # Clear any existing widgets
        for widget in self.frame.winfo_children():
            widget.destroy()
            
        # Show error message
        error_frame = ttk.Frame(self.frame)
        error_frame.pack(expand=True, fill='both')
        
        error_label = ttk.Label(error_frame, 
                               text=f"History Tab Error\n\n{message}\n\nPlease check the logs for more details.",
                               justify='center')
        error_label.pack(expand=True)
        
    def apply_filter(self):
        """Apply filters to history display."""
        date_from = self.date_from_var.get()
        date_to = self.date_to_var.get()
        target_filter = self.target_filter_var.get()
        status_filter = self.status_filter_var.get()
        
        try:
            filtered_data = self.history_manager.get_filtered_history(
                date_from=date_from,
                date_to=date_to,
                target_filter=target_filter,
                status_filter=status_filter
            )
            
            # Clear and populate tree with filtered data
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
                
            for record in filtered_data:
                self.history_tree.insert("", tk.END, values=(
                    record.get("date", ""),
                    record.get("time", ""),
                    record.get("target", ""),
                    record.get("status", ""),
                    record.get("frames_captured", ""),
                    f"{record.get('exposure_time', '')}s",
                    record.get("duration", ""),
                    record.get("file_size", "")
                ))
                
        except Exception as e:
            messagebox.showerror("Filter Error", f"Failed to apply filter: {e}")
            
    def clear_filter(self):
        """Clear all filters and show full history."""
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.target_filter_var.set("")
        self.status_filter_var.set("All")
        self.load_all_files()  # Reset to show all files
        self.refresh_history()
            
    def on_history_select(self, event):
        """Handle history tree selection."""
        selection = self.history_tree.selection()
        if not selection:
            return
            
        item = self.history_tree.item(selection[0])
        values = item["values"]
        
        if values:
            # Get detailed session information
            session_details = self.history_manager.get_session_details(values[0], values[1], values[2])
            
            # Display session details
            if session_details:
                details_text = f"""Session: {session_details.get('session_name', 'Unknown')}
Target: {values[2]}
Date: {values[0]} {values[1]}
Status: {values[3]}
Duration: {values[6]}

Coordinates:
RA: {session_details.get('ra', 'N/A')}
DEC: {session_details.get('dec', 'N/A')}

Capture Results:
Frames Captured: {values[4]}
Total Exposure: {session_details.get('total_exposure', 'N/A')}
File Size: {values[7]}

Notes:
{session_details.get('notes', 'None')}"""
                
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, details_text)
                
                # Display settings used
                settings_text = f"""Capture Settings:
Exposure: {values[5]}
Gain: {session_details.get('gain', 'N/A')}
Binning: {session_details.get('binning', 'N/A')}
Filter: {session_details.get('filter', 'N/A')}

Calibration:
Auto Focus: {session_details.get('auto_focus', 'N/A')}
Plate Solving: {session_details.get('plate_solve', 'N/A')}
Auto Guiding: {session_details.get('auto_guide', 'N/A')}

Environment:
Temperature: {session_details.get('temperature', 'N/A')}°C
Humidity: {session_details.get('humidity', 'N/A')}%
Seeing: {session_details.get('seeing', 'N/A')}"""
                
                self.settings_text.delete(1.0, tk.END)
                self.settings_text.insert(1.0, settings_text)
                
    def on_history_double_click(self, event):
        """Handle double-click on history item."""
        self.view_details()
        
    def update_statistics(self):
        """Update statistics display."""
        if not self.history_manager:
            return
            
        try:
            stats = self.history_manager.get_statistics()
            
            # Check if statistics widgets exist before updating
            if hasattr(self, 'total_sessions_label'):
                self.total_sessions_label.config(text=str(stats.get('total_sessions', 0)))
            if hasattr(self, 'successful_sessions_label'):
                self.successful_sessions_label.config(text=str(stats.get('successful_sessions', 0)))
            if hasattr(self, 'total_frames_label'):
                self.total_frames_label.config(text=str(stats.get('total_frames', 0)))
            
            if hasattr(self, 'total_exposure_label'):
                total_exposure_hours = stats.get('total_exposure_hours', 0)
                hours = int(total_exposure_hours)
                minutes = int((total_exposure_hours - hours) * 60)
                self.total_exposure_label.config(text=f"{hours}h {minutes}m")
            
            if hasattr(self, 'most_captured_label'):
                self.most_captured_label.config(text=stats.get('most_captured_target', '-'))
            if hasattr(self, 'avg_duration_label'):
                self.avg_duration_label.config(text=f"{stats.get('avg_duration_minutes', 0):.1f}m")
            
            # Update monthly breakdown
            if hasattr(self, 'monthly_tree'):
                for item in self.monthly_tree.get_children():
                    self.monthly_tree.delete(item)
                    
                monthly_stats = stats.get('monthly_breakdown', [])
                for month_data in monthly_stats:
                    self.monthly_tree.insert("", tk.END, values=(
                        month_data.get('month', ''),
                        month_data.get('sessions', 0),
                        month_data.get('frames', 0),
                        f"{month_data.get('exposure_hours', 0):.1f}h",
                        f"{month_data.get('success_rate', 0):.1f}%"
                    ))
                    
        except Exception as e:
            self.logger.error(f"Failed to update statistics: {e}")
            
    def export_csv(self):
        """Export history to CSV file."""
        filename = filedialog.asksaveasfilename(
            title="Export History",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                self.history_manager.export_to_csv(filename)
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")
                
    def clear_history(self):
        """Clear all history data."""
        if messagebox.askyesno("Confirm Clear", 
                             "This will permanently delete all history data.\n"
                             "Are you sure you want to continue?"):
            try:
                self.history_manager.clear_history()
                self.refresh_history()
            except Exception as e:
                messagebox.showerror("Clear Error", f"Failed to clear history: {e}")
                
    def view_details(self):
        """View detailed information for selected session."""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to view details.")
            return
            
        # This would open a detailed view window
        messagebox.showinfo("Details", "Detailed view window not implemented yet.")
        
    def open_files(self):
        """Open captured files for selected session."""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to open files.")
            return
            
        # This would open the file explorer to the session's files
        messagebox.showinfo("Open Files", "File opening not implemented yet.")
        
    def repeat_session(self):
        """Create a new session based on selected history entry."""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to repeat.")
            return
            
        # This would create a new session with the same settings
        messagebox.showinfo("Repeat", "Session repeat not implemented yet.")
        
    def export_session(self):
        """Export selected session data."""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to export.")
            return
            
        # This would export the session data to a file
        messagebox.showinfo("Export", "Session export not implemented yet.")
        
    def delete_entry(self):
        """Delete selected history entry."""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a session to delete.")
            return
            
        item = self.history_tree.item(selection[0])
        values = item["values"]
        
        if messagebox.askyesno("Confirm Delete", 
                             f"Delete history entry for {values[2]} on {values[0]}?"):
            try:
                self.history_manager.delete_entry(values[0], values[1], values[2])
                self.refresh_history()
            except Exception as e:
                messagebox.showerror("Delete Error", f"Failed to delete entry: {e}")
                
    def refresh_history_files(self):
        """Refresh the history files list."""
        if not self.history_manager:
            self.logger.warning("History manager not available for file refresh")
            return
            
        if not hasattr(self, 'files_listbox'):
            self.logger.warning("Files listbox not created yet")
            return
            
        try:
            # Clear current list
            self.files_listbox.delete(0, tk.END)
            
            # Get available history files
            history_files = self.history_manager.get_history_files()
            self.logger.info(f"Found {len(history_files)} history files")
            
            if not history_files:
                # Add a message if no files found
                self.files_listbox.insert(tk.END, "No history files found")
                self.file_info_label.config(text="No history files available. History will be created when sessions are completed.")
            else:
                for file_info in history_files:
                    display_name = f"{file_info['date']} ({file_info['sessions']} sessions)"
                    self.files_listbox.insert(tk.END, display_name)
                    
                self.file_info_label.config(text="Select a history file to view info")
                
        except Exception as e:
            self.logger.error(f"Failed to refresh history files: {e}")
            # Show error in the listbox
            self.files_listbox.delete(0, tk.END)
            self.files_listbox.insert(tk.END, f"Error loading files: {str(e)}")
            self.file_info_label.config(text=f"Error: {str(e)}")
            
    def on_file_select(self, event):
        """Handle file selection in listbox."""
        selection = self.files_listbox.curselection()
        if not selection:
            return
            
        try:
            # Get file info for selected index
            history_files = self.history_manager.get_history_files()
            if selection[0] < len(history_files):
                file_info = history_files[selection[0]]
                
                info_text = f"""Date: {file_info['date']}
Sessions: {file_info['sessions']}
File Size: {file_info['size']}
Last Modified: {file_info['modified']}"""
                
                self.file_info_label.config(text=info_text)
                
        except Exception as e:
            self.logger.error(f"Failed to get file info: {e}")
            
    def on_file_double_click(self, event):
        """Handle double-click on file - load selected file."""
        self.load_selected_file()
        
    def load_all_files(self):
        """Load history from all files."""
        if not self.history_manager:
            return
            
        try:
            # Set history manager to load all files
            self.history_manager.set_active_files(None)  # None means all files
            self.refresh_history()
            
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load all files: {e}")
            
    def load_selected_file(self):
        """Load history from selected file only."""
        selection = self.files_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a history file to load.")
            return
            
        try:
            # Get selected file
            history_files = self.history_manager.get_history_files()
            if selection[0] < len(history_files):
                selected_file = history_files[selection[0]]['filename']
                
                # Set history manager to load only selected file
                self.history_manager.set_active_files([selected_file])
                self.refresh_history()
                
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load selected file: {e}")
            
    def delete_selected_file(self):
        """Delete selected history file."""
        selection = self.files_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a history file to delete.")
            return
            
        try:
            # Get selected file info
            history_files = self.history_manager.get_history_files()
            if selection[0] < len(history_files):
                file_info = history_files[selection[0]]
                
                # Confirm deletion
                if messagebox.askyesno("Confirm Delete", 
                                     f"Delete history file for {file_info['date']}?\n"
                                     f"This will permanently delete {file_info['sessions']} session records."):
                    
                    # Delete the file
                    self.history_manager.delete_history_file(file_info['filename'])
                    
                    # Refresh lists
                    self.refresh_history_files()
                    self.refresh_history()
                    
        except Exception as e:
            messagebox.showerror("Delete Error", f"Failed to delete history file: {e}")
