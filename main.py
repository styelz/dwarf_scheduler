#!/usr/bin/env python3
"""
Dwarf3 Telescope Scheduler
A GUI application for scheduling and managing Dwarf3 smart telescope sessions.
"""

import tkinter as tk
from tkinter import ttk
import logging
from gui.main_window import MainWindow
from core.config_manager import ConfigManager
import os

def setup_logging():
    """Set up logging configuration."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'dwarf_scheduler.log')),
            logging.StreamHandler()
        ]
    )

def main():
    """Main entry point for the application."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize configuration
        config_manager = ConfigManager()
        
        # Create and run the main application
        root = tk.Tk()
        app = MainWindow(root, config_manager)
        
        logger.info("Starting Dwarf3 Telescope Scheduler")
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise

if __name__ == "__main__":
    main()
