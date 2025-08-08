# Dwarf3 Telescope Scheduler

A comprehensive Python GUI application for scheduling and managing Dwarf3 smart telescope observation sessions. Built with a modular architecture featuring dual-mode API communication, automated session management, and an intuitive tabbed interface.

## ✨ Key Features

- **📅 Session Scheduling**: Create, queue, and automatically execute telescope observation sessions
- **🎯 Target Management**: Direct Stellarium integration for easy target selection
- **📊 Real-time Monitoring**: Live telescope status, battery level, and storage tracking
- **📁 Smart File Management**: Automatic session file organization with status-based directories
- **🔄 Dual API Support**: Primary websocket/protobuf API with HTTP REST fallback
- **📈 Session History**: Comprehensive tracking and CSV export of all observations
- **⚙️ Configuration Management**: Persistent settings with INI and JSON config files
- **🖥️ Modern GUI**: User-friendly tabbed interface built with tkinter/ttk

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** (3.10+ recommended)
- **Windows/macOS/Linux** with tkinter support
- **Dwarf3 telescope** with WiFi connectivity
- **Network access** to telescope (WiFi or LAN)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/styelz/dwarf_scheduler.git
   cd dwarf_scheduler
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   
   # Required: Install local dependencies
   pip install -r requirements-local.txt --target .
   ```

3. **Launch the application**:
   ```bash
   python main.py
   ```

**Happy observing! 🔭✨**
