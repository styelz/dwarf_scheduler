#!/usr/bin/env python3
"""
Simple demo of non-blocking telescope operations
"""
import sys
import time
import tkinter as tk
from tkinter import ttk
sys.path.append('.')

from core.config_manager import ConfigManager
from core.dwarf_controller import DwarfController

class TelescopeDemo:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Non-Blocking Telescope Demo")
        self.root.geometry("500x400")
        
        # Initialize telescope controller
        self.config_manager = ConfigManager()
        self.controller = DwarfController(self.config_manager)
        
        self.create_widgets()
        
    def create_widgets(self):
        # Status display
        self.status_text = tk.Text(self.root, height=15, width=60)
        self.status_text.pack(padx=10, pady=10)
        
        # Buttons frame
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)
        
        # Test connection button
        ttk.Button(button_frame, text="Test Connection", 
                  command=self.test_connection).pack(side=tk.LEFT, padx=5)
        
        # Get status button
        ttk.Button(button_frame, text="Get Status", 
                  command=self.get_status).pack(side=tk.LEFT, padx=5)
        
        # Clear log button
        ttk.Button(button_frame, text="Clear Log", 
                  command=self.clear_log).pack(side=tk.LEFT, padx=5)
        
        # Countdown label to show GUI is responsive
        self.countdown_label = ttk.Label(self.root, text="GUI Responsive: 0")
        self.countdown_label.pack(pady=5)
        
        # Start countdown to show GUI responsiveness
        self.counter = 0
        self.update_counter()
        
    def log_message(self, message):
        """Add message to status text."""
        timestamp = time.strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.root.update_idletasks()
        
    def test_connection(self):
        """Test connection using non-blocking API."""
        self.log_message("Starting non-blocking connection test...")
        
        def connection_callback(success, message):
            # This callback runs in the background thread
            # Schedule GUI update in main thread
            self.root.after(0, lambda: self.log_message(f"Connection result: {success} - {message}"))
        
        # This returns immediately without blocking the GUI
        future = self.controller.test_connection(callback=connection_callback)
        self.log_message("Connection test initiated (GUI remains responsive)")
        
    def get_status(self):
        """Get telescope status using non-blocking API."""
        self.log_message("Starting non-blocking status check...")
        
        def status_callback(status):
            # This callback runs in the background thread
            # Schedule GUI update in main thread
            self.root.after(0, lambda: self.log_message(f"Status: {status}"))
        
        # This returns immediately without blocking the GUI
        future = self.controller.get_detailed_telescope_status(callback=status_callback)
        self.log_message("Status check initiated (GUI remains responsive)")
        
    def clear_log(self):
        """Clear the status log."""
        self.status_text.delete(1.0, tk.END)
        
    def update_counter(self):
        """Update counter to show GUI responsiveness."""
        self.counter += 1
        self.countdown_label.config(text=f"GUI Responsive: {self.counter}")
        self.root.after(1000, self.update_counter)  # Update every second
        
    def on_closing(self):
        """Handle window closing."""
        self.log_message("Cleaning up...")
        self.controller.cleanup()
        self.root.destroy()
        
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.log_message("Telescope Demo Started")
        self.log_message(f"Controller mode: {'dwarf_python_api' if self.controller.use_dwarf_api else 'HTTP'}")
        self.log_message(f"Target IP: {self.controller.ip}")
        self.log_message("Click buttons to test non-blocking operations")
        self.root.mainloop()

if __name__ == "__main__":
    demo = TelescopeDemo()
    demo.run()
