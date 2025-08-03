<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Dwarf3 Telescope Scheduler - Copilot Instructions

This is a Python GUI application for controlling and scheduling Dwarf3 smart telescope observations.

## Project Context

- **Application Type**: Desktop GUI application using tkinter
- **Purpose**: Telescope session scheduling and automation
- **Target Hardware**: Dwarf3 smart telescope
- **Architecture**: Modular design with separate GUI, core logic, and data management

## Code Style Guidelines

- Follow PEP 8 Python style conventions
- Use type hints where appropriate
- Include comprehensive docstrings for classes and functions
- Use logging instead of print statements
- Handle exceptions gracefully with proper error messages

## Key Components

### GUI Layer (`gui/`)
- Main window with tabbed interface (Schedule, Sessions, Settings, History)
- Built with tkinter and ttk for modern appearance
- Event-driven architecture with callbacks
- Separation of UI logic from business logic

### Core Logic (`core/`)
- `ConfigManager`: JSON-based configuration management
- `SessionManager`: Session file operations and organization
- `Scheduler`: Threading-based session execution engine  
- `DwarfController`: REST API communication with telescope
- `HistoryManager`: CSV-based session history tracking

### Data Storage
- Sessions stored as JSON files in organized directories
- History tracked in CSV format
- Configuration in JSON format
- Automatic directory structure creation

## API Integration

The application communicates with Dwarf3 telescope via REST API:
- Base URL: `http://{ip}:{port}/api/`
- Endpoints for mount control, camera operations, focusing, guiding
- JSON request/response format
- Proper timeout and error handling

## Common Patterns

### Error Handling
```python
try:
    # Operation
    self.logger.info("Operation completed")
    return True
except Exception as e:
    self.logger.error(f"Operation failed: {e}")
    return False
```

### Configuration Access
```python
config = self.config_manager.get_setting("category", "key", default_value)
```

### Session File Operations
```python
session_data = self.session_manager.load_session(filename)
self.session_manager.save_session(session_data, status="Available")
```

### GUI Updates
```python
def update_display(self):
    # Clear existing data
    for item in self.tree.get_children():
        self.tree.delete(item)
    
    # Populate with new data
    for item in data:
        self.tree.insert("", tk.END, values=item)
```

## Threading Considerations

- Scheduler runs in background thread
- Use `threading.Event` for clean shutdown
- Update GUI from main thread only
- Use callbacks for cross-thread communication

## File Organization

- Session files named with timestamp and target: `YYYYMMDD_HHMMSS_TargetName.json`
- Organized in status-based directories (Available, ToDo, Running, Done, Failed)
- Automatic cleanup and archiving of old sessions

## Testing and Development

- Use logging extensively for debugging
- Test telescope communication with mock data when hardware unavailable
- Validate JSON data before file operations
- Handle network timeouts gracefully

## Security and Reliability

- Validate all user inputs
- Graceful degradation when telescope unavailable
- Automatic backup of important data
- Recovery from interrupted operations

When generating code for this project:
1. Maintain the existing architectural patterns
2. Add appropriate logging and error handling
3. Follow the established naming conventions
4. Consider thread safety for scheduler operations
5. Validate data before file/network operations
