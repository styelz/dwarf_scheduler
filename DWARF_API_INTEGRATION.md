# Enhanced Dwarf Controller Integration

## Overview
The `dwarf_controller.py` has been enhanced to integrate with the `dwarf_python_api` for more robust telescope control. The controller now supports dual modes:

1. **dwarf_python_api mode** (preferred): Uses websockets and protobuf for reliable communication
2. **HTTP mode** (fallback): Uses the original HTTP-based approach

## Key Enhancements

### 🔧 **Dual API Support**
- **Auto-detection**: Automatically detects if `dwarf_python_api` is available
- **Graceful fallback**: Falls back to HTTP mode if dwarf_python_api is unavailable
- **Mode indication**: Logs which mode is being used for troubleshooting

### 📡 **Connection Testing**
- **Enhanced connection test**: Uses `getDefaultParamsConfig` endpoint for HTTP mode
- **dwarf_python_api integration**: Uses `perform_getstatus()` for API mode
- **Telescope info extraction**: Extracts model, firmware version, camera details

### 🎯 **Telescope Control Functions**

#### **Session Management**
- `start_session()`: Opens camera using `perform_open_camera()` in API mode
- Enhanced session state tracking

#### **Auto Focus**
- `auto_focus()`: Uses `perform_start_autofocus(infinite=True/False)` in API mode
- Supports both automatic and infinite focus modes

#### **Telescope Movement**
- `goto_coordinates()`: Uses `perform_goto(ra, dec, target)` in API mode
- Improved coordinate handling and target naming

#### **Calibration**
- `perform_calibration()`: Uses `perform_calibration()` in API mode
- Simplified calibration process with better error handling

#### **Connection Management**
- `disconnect()`: Uses `perform_disconnect()` in API mode
- Proper cleanup of both websocket and HTTP connections

### 📋 **Dependencies Added**
```plaintext
protobuf>=3.20.0        # For dwarf_python_api protobuf messages
websockets>=10.0        # For websocket communication
filelock>=3.0.0         # For configuration file locking
```

### 🔧 **Configuration Management**
- **Automatic config creation**: Creates `config.py` for dwarf_python_api when needed
- **Settings integration**: Uses existing telescope settings (IP, port, timeout)
- **Dynamic configuration**: Updates dwarf_python_api config when settings change

## Usage

### **Automatic Mode Selection**
```python
# Controller automatically selects best available mode
controller = DwarfController(config_manager)
controller.connect()  # Uses dwarf_python_api if available, HTTP otherwise
```

### **Mode Checking**
```python
if controller.use_dwarf_api:
    print("Using robust dwarf_python_api")
else:
    print("Using HTTP fallback mode")
```

### **Enhanced Status Information**
```python
telescope_info = controller.get_telescope_info()
# Returns: model, firmware_version, api_mode, etc.
```

## Benefits

### 🚀 **Improved Reliability**
- **Websocket communication**: More reliable than HTTP for long operations
- **Protobuf messages**: Structured, validated communication protocol
- **Better error handling**: More detailed error reporting and recovery

### 🔄 **Backward Compatibility**
- **No breaking changes**: Existing HTTP functionality preserved
- **Gradual migration**: Can run with or without dwarf_python_api
- **Same interface**: All public methods remain unchanged

### 📊 **Enhanced Monitoring**
- **Connection status**: Better connection state tracking
- **Operation progress**: More detailed progress reporting
- **Telescope information**: Rich device information extraction

## Testing

### **Basic Connection Test**
```bash
python test_enhanced_controller.py
```

### **Full Integration Test**
```bash
python test_telescope_status.py
```

## Configuration Files

### **dwarf_python_api config.py** (auto-generated)
```python
DWARF_IP = "192.168.1.42"
DWARF_UI = "8080"
CLIENT_ID = "scheduler"
TIMEOUT_CMD = 10
# ... additional settings
```

### **scheduler settings.json** (existing)
```json
{
  "telescope": {
    "ip": "192.168.1.42",
    "port": 80,
    "timeout": 10
  }
}
```

## Error Handling

### **API Unavailable**
- Logs warning about missing dwarf_python_api
- Automatically falls back to HTTP mode
- No functional impact on scheduler operation

### **Connection Failures**
- Tries dwarf_python_api first (if available)
- Falls back to HTTP mode on API failure
- Detailed error logging for troubleshooting

### **Operation Failures**
- Improved error messages with mode indication
- Better recovery from failed operations
- Maintains connection state consistency

## Future Enhancements

1. **Real-time status updates** via websocket notifications
2. **Enhanced capture monitoring** with frame-by-frame progress
3. **Advanced telescope features** available only through dwarf_python_api
4. **Automatic firmware detection** and feature adaptation

This integration provides a robust foundation for telescope control while maintaining backward compatibility and enabling advanced features through the dwarf_python_api.
