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
from config import DEBUG

def setup_logging():
    """Set up logging configuration with rotation."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Determine logging level based on DEBUG setting
    log_level = logging.DEBUG if DEBUG else logging.INFO

    # Import RotatingFileHandler
    from logging.handlers import RotatingFileHandler
    
    # File handler with rotation (10MB max, keep 5 files)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'dwarf_scheduler.log'),
        maxBytes=10*1024*1024, 
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    logging.basicConfig(
        level=log_level,
        handlers=[file_handler, console_handler]
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
