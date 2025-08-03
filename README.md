# Dwarf3 Telescope Scheduler

A comprehensive Python GUI application for scheduling and managing Dwarf3 smart telescope observation sessions.

## Features

- **Session Management**: Create, edit, and manage telescope observation sessions
- **Scheduling**: Queue sessions for automatic execution at specified times
- **History Tracking**: Keep detailed records of completed sessions
- **Settings Configuration**: Configure telescope connection, location, and default parameters
- **Automated Capture**: Automatic focusing, plate solving, and image capture
- **GUI Interface**: User-friendly tabbed interface built with tkinter

## Project Structure

```
dwarf_scheduler/
├── main.py                 # Main application entry point
├── gui/                    # GUI components
│   ├── main_window.py     # Main application window
│   └── tabs/              # Individual tab implementations
│       ├── schedule_tab.py
│       ├── sessions_tab.py
│       ├── settings_tab.py
│       └── history_tab.py
├── core/                   # Core functionality
│   ├── config_manager.py  # Configuration management
│   ├── session_manager.py # Session file management
│   ├── scheduler.py       # Scheduling engine
│   ├── dwarf_controller.py# Telescope control
│   └── history_manager.py # History tracking
├── Sessions/              # Session storage directories
│   ├── Available/         # Available session templates
│   ├── ToDo/             # Scheduled sessions
│   ├── Running/          # Currently executing sessions
│   ├── Done/             # Completed sessions
│   ├── Failed/           # Failed sessions
│   └── History/          # Session history CSV files
├── config/               # Configuration files
├── logs/                 # Application logs
└── requirements.txt      # Python dependencies
```

## Installation

1. **Prerequisites**:
   - Python 3.8 or higher
   - Tkinter (usually included with Python)
   - Network connection to Dwarf3 telescope

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Application**:
   ```bash
   python main.py
   ```

## Configuration

### First Time Setup

1. **Telescope Connection**: 
   - Go to Settings → Telescope tab
   - Enter your Dwarf3 IP address (default: 192.168.4.1)
   - Test the connection

2. **Location Settings**:
   - Go to Settings → Location tab
   - Enter your geographic coordinates
   - Set your timezone

3. **Default Settings**:
   - Configure default capture parameters
   - Set preferred frame counts and exposure times

## Usage

### Creating Sessions

1. Go to the **Sessions** tab
2. Click **New Session**
3. Fill in session details:
   - Session name and target name
   - Start time for scheduling
   - Target coordinates (RA/DEC)
   - Capture settings (frames, exposure, gain)
   - Calibration options (auto focus, plate solving)

### Scheduling Sessions

1. Create or edit a session
2. Click **Add to Schedule**
3. Go to the **Schedule** tab
4. Start the scheduler to begin automatic execution

### Session File Management

The application automatically manages session files during scheduling:

- **Adding to Schedule**: Sessions move from `Sessions/Available/` to `Sessions/ToDo/`
- **Removing from Queue**: Sessions move back from `Sessions/ToDo/` to `Sessions/Available/`
- **During Execution**: Sessions move through `Running/`, then to `Done/` or `Failed/`

This prevents editing of scheduled sessions and maintains data integrity. See `SESSION_WORKFLOW.md` for detailed information.

### Viewing History

1. Go to the **History** tab
2. View completed sessions with detailed information
3. Use filters to find specific sessions
4. Export history data to CSV

## Session File Format

Sessions are stored as JSON files with the following structure:

```json
{
    "session_name": "M31_Session_001",
    "target_name": "M31 - Andromeda Galaxy",
    "start_time": "2024-08-04 22:00:00",
    "description": "Deep sky imaging of M31",
    "coordinates": {
        "ra": "00:42:44",
        "dec": "+41:16:09"
    },
    "capture_settings": {
        "frame_count": 50,
        "exposure_time": 120,
        "gain": 100,
        "binning": "1x1",
        "filter": "L"
    },
    "calibration": {
        "auto_focus": true,
        "plate_solve": true,
        "auto_guide": false,
        "settling_time": 10,
        "focus_timeout": 300
    }
}
```

## API Integration

The application communicates with the Dwarf3 telescope through its REST API. Key endpoints used:

- `/api/status` - Get telescope status
- `/api/mount/goto` - Move to coordinates  
- `/api/camera/capture` - Capture images
- `/api/camera/autofocus` - Perform auto focus
- `/api/mount/platesolve` - Plate solving
- `/api/guiding/start` - Start auto guiding

## Logging

Application logs are stored in the `logs/` directory:
- `dwarf_scheduler.log` - Main application log
- Log level can be configured in Settings → Advanced

## Troubleshooting

### Connection Issues

1. **Cannot connect to telescope**:
   - Verify Dwarf3 is powered on and WiFi is active
   - Check IP address in Settings
   - Ensure computer is connected to Dwarf3 WiFi network

2. **Sessions not executing**:
   - Check if scheduler is started
   - Verify session start times are in the future
   - Check logs for error messages

### Session Problems

1. **Auto focus fails**:
   - Ensure target is bright enough
   - Check focus timeout settings
   - Try manual focusing first

2. **Plate solving fails**:
   - Verify coordinates are correct
   - Ensure sufficient stars in field
   - Check internet connection for star database

## Development

### Adding New Features

1. **GUI Components**: Add new tabs in `gui/tabs/`
2. **Core Logic**: Extend functionality in `core/`
3. **Configuration**: Update `config_manager.py` for new settings

### Testing

Run the application in development mode:
```bash
python main.py --debug
```

## License

This project is open source. Please check the license file for details.

## Contributing

Contributions are welcome! Please submit issues and pull requests on the project repository.

## Support

For questions and support:
- Check the logs for error messages
- Review the troubleshooting section
- Submit issues on the project repository
