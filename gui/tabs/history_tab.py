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
            self.history_manager = HistoryManager()
            self.logger.info("HistoryManager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize HistoryManager: {e}")
            self.history_manager = None
        
        # Create widgets
        self.create_widgets()
        
        # Initial refresh
        if self.history_manager:
            self.refresh_history()
        
    def create_widgets(self):
        """Create and arrange the history tab widgets."""
        if not self.history_manager:
            self.create_error_display()
            return
            
        # Main container
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create paned window for resizable sections
        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Top section - filters and history tree
        top_frame = ttk.Frame(paned)
        paned.add(top_frame, weight=3)
        
        self.create_filter_controls(top_frame)
        self.create_history_tree(top_frame)
        
        # Bottom section - statistics
        bottom_frame = ttk.Frame(paned)
        paned.add(bottom_frame, weight=2)
        
        self.create_statistics_panel(bottom_frame)
        
    def create_error_display(self):
        """Create error display when history manager is not available."""
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="History Manager Error", 
                 font=('Arial', 16)).pack(expand=True)
        ttk.Label(main_frame, text="Unable to initialize history management.\nHistory features are not available.",
                 justify=tk.CENTER).pack(expand=True, pady=20)
        
    def create_filter_controls(self, parent):
        """Create filter controls for history display."""
        filter_frame = ttk.LabelFrame(parent, text="Filters", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Filter controls in a grid
        controls_frame = ttk.Frame(filter_frame)
        controls_frame.pack(fill=tk.X)
        
        # Date range filters
        ttk.Label(controls_frame, text="From:").grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
        self.date_from_entry = ttk.Entry(controls_frame, textvariable=self.date_from_var, width=12)
        self.date_from_entry.grid(row=0, column=1, padx=(0, 10), sticky=tk.W)
        
        ttk.Label(controls_frame, text="To:").grid(row=0, column=2, padx=(0, 5), sticky=tk.W)
        self.date_to_entry = ttk.Entry(controls_frame, textvariable=self.date_to_var, width=12)
        self.date_to_entry.grid(row=0, column=3, padx=(0, 10), sticky=tk.W)
        
        # Target filter
        ttk.Label(controls_frame, text="Target:").grid(row=0, column=4, padx=(0, 5), sticky=tk.W)
        self.target_entry = ttk.Entry(controls_frame, textvariable=self.target_filter_var, width=15)
        self.target_entry.grid(row=0, column=5, padx=(0, 10), sticky=tk.W)
        
        # Status filter
        ttk.Label(controls_frame, text="Status:").grid(row=0, column=6, padx=(0, 5), sticky=tk.W)
        self.status_combo = ttk.Combobox(controls_frame, textvariable=self.status_filter_var, 
                                        values=["All", "Completed", "Failed", "Cancelled"], 
                                        width=12, state="readonly")
        self.status_combo.grid(row=0, column=7, padx=(0, 10), sticky=tk.W)
        
        # Buttons
        ttk.Button(controls_frame, text="Apply Filters", 
                  command=self.apply_filters).grid(row=0, column=8, padx=(10, 5), sticky=tk.W)
        ttk.Button(controls_frame, text="Clear", 
                  command=self.clear_filters).grid(row=0, column=9, padx=(0, 5), sticky=tk.W)
        ttk.Button(controls_frame, text="Refresh", 
                  command=self.refresh_history).grid(row=0, column=10, padx=(5, 0), sticky=tk.W)
        
    def create_history_tree(self, parent):
        """Create the history treeview."""
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview with columns
        columns = ("date", "time", "target", "status", "frames", "exposure", "duration", "size")
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.history_tree.heading("date", text="Date")
        self.history_tree.heading("time", text="Time")
        self.history_tree.heading("target", text="Target")
        self.history_tree.heading("status", text="Status")
        self.history_tree.heading("frames", text="Frames")
        self.history_tree.heading("exposure", text="Exposure")
        self.history_tree.heading("duration", text="Duration")
        self.history_tree.heading("size", text="Size")
        
        # Set column widths
        self.history_tree.column("date", width=80)
        self.history_tree.column("time", width=60)
        self.history_tree.column("target", width=120)
        self.history_tree.column("status", width=80)
        self.history_tree.column("frames", width=60)
        self.history_tree.column("exposure", width=80)
        self.history_tree.column("duration", width=80)
        self.history_tree.column("size", width=80)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.history_tree.xview)
        self.history_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def create_statistics_panel(self, parent):
        """Create the statistics panel."""
        stats_notebook = ttk.Notebook(parent)
        stats_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Overview tab
        overview_frame = ttk.Frame(stats_notebook)
        stats_notebook.add(overview_frame, text="Overview")
        
        # Statistics grid
        stats_grid = ttk.Frame(overview_frame)
        stats_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Total sessions
        ttk.Label(stats_grid, text="Total Sessions:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.total_sessions_label = ttk.Label(stats_grid, text="0", font=('Arial', 10, 'bold'))
        self.total_sessions_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Successful sessions
        ttk.Label(stats_grid, text="Successful:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.successful_sessions_label = ttk.Label(stats_grid, text="0", font=('Arial', 10, 'bold'))
        self.successful_sessions_label.grid(row=0, column=3, sticky=tk.W)
        
        # Total frames
        ttk.Label(stats_grid, text="Total Frames:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        self.total_frames_label = ttk.Label(stats_grid, text="0", font=('Arial', 10, 'bold'))
        self.total_frames_label.grid(row=1, column=1, sticky=tk.W, padx=(0, 20))
        
        # Total exposure
        ttk.Label(stats_grid, text="Total Exposure:").grid(row=1, column=2, sticky=tk.W, padx=(0, 5))
        self.total_exposure_label = ttk.Label(stats_grid, text="0h 0m", font=('Arial', 10, 'bold'))
        self.total_exposure_label.grid(row=1, column=3, sticky=tk.W)
        
        # Monthly breakdown tab
        monthly_frame = ttk.Frame(stats_notebook)
        stats_notebook.add(monthly_frame, text="Monthly")
        
        # Monthly stats tree
        monthly_columns = ("month", "sessions", "frames", "exposure", "success_rate")
        self.monthly_tree = ttk.Treeview(monthly_frame, columns=monthly_columns, show="headings", height=10)
        
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
        
    def apply_filters(self):
        """Apply current filter settings."""
        self.refresh_history()
        
    def clear_filters(self):
        """Clear all filters."""
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.target_filter_var.set("")
        self.status_filter_var.set("All")
        self.refresh_history()
        
    def refresh_history(self):
        """Refresh the history display."""
        if not self.history_manager:
            return
            
        # Clear current items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
            
        try:
            # Load history data
            history_data = self.history_manager.get_history()
            
            # Apply filters
            filtered_data = self.filter_history(history_data)
            
            # Populate tree
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
                
            # Update statistics
            self.update_statistics()
            
        except Exception as e:
            self.logger.error(f"Failed to refresh history: {e}")
            
    def filter_history(self, history_data):
        """Apply current filters to history data."""
        filtered = history_data
        
        # Date range filter
        date_from = self.date_from_var.get().strip()
        date_to = self.date_to_var.get().strip()
        
        if date_from or date_to:
            # Implement date filtering logic here
            pass
            
        # Target filter
        target_filter = self.target_filter_var.get().strip().lower()
        if target_filter:
            filtered = [r for r in filtered if target_filter in r.get("target", "").lower()]
            
        # Status filter
        status_filter = self.status_filter_var.get()
        if status_filter != "All":
            filtered = [r for r in filtered if r.get("status", "") == status_filter]
            
        return filtered
        
    def update_statistics(self):
        """Update statistics display."""
        if not self.history_manager:
            return
            
        try:
            stats = self.history_manager.get_statistics()
            
            self.total_sessions_label.config(text=str(stats.get('total_sessions', 0)))
            self.successful_sessions_label.config(text=str(stats.get('successful_sessions', 0)))
            self.total_frames_label.config(text=str(stats.get('total_frames', 0)))
            
            total_exposure_hours = stats.get('total_exposure_hours', 0)
            hours = int(total_exposure_hours)
            minutes = int((total_exposure_hours - hours) * 60)
            self.total_exposure_label.config(text=f"{hours}h {minutes}m")
            
            # Update monthly breakdown
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
