"""
Dwarf3 telescope command mappings for enhanced logging.
Maps command numbers to human-readable descriptions.
"""

# Command mappings based on dwarf_python_api protocol definitions
DWARF_COMMAND_MAP = {
    # Camera Control Commands (10000-10999)
    10000: "CMD_CAMERA_TELE_OPEN_CAMERA - Turn on the camera",
    10001: "CMD_CAMERA_TELE_CLOSE_CAMERA - Turn off the camera", 
    10002: "CMD_CAMERA_TELE_PHOTOGRAPH - Take photos",
    10003: "CMD_CAMERA_TELE_BURST - Start continuous shooting",
    10004: "CMD_CAMERA_TELE_STOP_BURST - Stop continuous shooting",
    10005: "CMD_CAMERA_TELE_START_RECORD - Start recording",
    10006: "CMD_CAMERA_TELE_STOP_RECORD - Stop recording",
    10007: "CMD_CAMERA_TELE_SET_EXP_MODE - Set exposure mode",
    10008: "CMD_CAMERA_TELE_GET_EXP_MODE - Get exposure mode",
    10009: "CMD_CAMERA_TELE_SET_EXP - Set exposure value",
    10010: "CMD_CAMERA_TELE_GET_EXP - Get exposure value",
    10011: "CMD_CAMERA_TELE_SET_GAIN_MODE - Set gain mode",
    10012: "CMD_CAMERA_TELE_GET_GAIN_MODE - Get gain mode",
    10013: "CMD_CAMERA_TELE_SET_GAIN - Set gain value",
    10014: "CMD_CAMERA_TELE_GET_GAIN - Get gain value",
    10015: "CMD_CAMERA_TELE_SET_BRIGHTNESS - Set brightness",
    10016: "CMD_CAMERA_TELE_GET_BRIGHTNESS - Get brightness",
    10017: "CMD_CAMERA_TELE_SET_CONTRAST - Set contrast",
    10018: "CMD_CAMERA_TELE_GET_CONTRAST - Get contrast",
    10019: "CMD_CAMERA_TELE_SET_SATURATION - Set saturation",
    10020: "CMD_CAMERA_TELE_GET_SATURATION - Get saturation",
    10039: "CMD_CAMERA_TELE_GET_SYSTEM_WORKING_STATE - Get system working state",
    
    # Astronomical Commands
    11000: "CMD_ASTRO_START_CALIBRATION - Start astronomical calibration",
    11001: "CMD_ASTRO_STOP_CALIBRATION - Stop astronomical calibration", 
    11002: "CMD_ASTRO_GOTO_MERIDIAN - Go to meridian",
    11003: "CMD_ASTRO_GOTO_SOUTH_MERIDIAN - Go to south meridian",
    11004: "CMD_ASTRO_START_GOTO_DSO - Start GOTO to deep sky object",
    11005: "CMD_ASTRO_STOP_GOTO - Stop GOTO",
    11006: "CMD_ASTRO_START_TRACKING - Start tracking",
    11007: "CMD_ASTRO_STOP_TRACKING - Stop tracking",
    
    # Focus Commands
    12000: "CMD_FOCUS_START_AUTO_FOCUS - Start auto focus",
    12001: "CMD_FOCUS_STOP_AUTO_FOCUS - Stop auto focus",
    12002: "CMD_FOCUS_START_GOTO_FOCUS - Go to focus position",
    12003: "CMD_FOCUS_STOP_GOTO_FOCUS - Stop focus movement",
    
    # Notification Commands (15200-15499)
    15200: "CMD_NOTIFY_TELE_WIDI_PICTURE_MATCHING - Telephoto wide-angle image matching",
    15201: "CMD_NOTIFY_ELE - Battery notification",
    15202: "CMD_NOTIFY_CHARGE - Charge status notification", 
    15203: "CMD_NOTIFY_SDCARD_INFO - SD card capacity notification",
    15204: "CMD_NOTIFY_TELE_RECORD_TIME - Recording time",
    15205: "CMD_NOTIFY_TELE_TIMELAPSE_OUT_TIME - Telephoto time-lapse photography time",
    15206: "CMD_NOTIFY_STATE_CAPTURE_RAW_DARK - Dark field shooting state",
    15207: "CMD_NOTIFY_PROGRASS_CAPTURE_RAW_DARK - Dark field shooting progress",
    15208: "CMD_NOTIFY_STATE_CAPTURE_RAW_LIVE_STACKING - Astronomical overlay shooting status",
    15209: "CMD_NOTIFY_PROGRASS_CAPTURE_RAW_LIVE_STACKING - Astronomical overlay shooting progress",
    15210: "CMD_NOTIFY_STATE_ASTRO_CALIBRATION - Astronomical calibration status",
    15211: "CMD_NOTIFY_STATE_ASTRO_GOTO - Astronomical GOTO status",
    15212: "CMD_NOTIFY_STATE_ASTRO_TRACKING - Astronomical tracking status",
    15213: "CMD_NOTIFY_TELE_SET_PARAM - Telephoto parameter echo",
    15214: "CMD_NOTIFY_WIDE_SET_PARAM - Wide-angle parameter echo",
    15215: "CMD_NOTIFY_TELE_FUNCTION_STATE - Telephoto functional status",
    15216: "CMD_NOTIFY_WIDE_FUNCTION_STATE - Wide-angle functional status",
    15217: "CMD_NOTIFY_SET_FEATURE_PARAM - Feature parameter echo",
    15218: "CMD_NOTIFY_TELE_BURST_PROGRESS - Telephoto continuous shooting progress",
    15219: "CMD_NOTIFY_PANORAMA_PROGRESS - Telephoto panoramic shooting progress",
    15220: "CMD_NOTIFY_WIDE_BURST_PROGRESS - Wide-angle continuous shooting progress",
    15221: "CMD_NOTIFY_RGB_STATE - RGB Ring Light Status",
    15222: "CMD_NOTIFY_POWER_IND_STATE - Power indicator status",
    15223: "CMD_NOTIFY_WS_HOST_SLAVE_MODE - Leader/follower mode notification",
    15224: "CMD_NOTIFY_MTP_STATE - MTP mode notification",
    15225: "CMD_NOTIFY_TRACK_RESULT - Tracking result notification",
    15226: "CMD_NOTIFY_WIDE_TIMELAPSE_OUT_TIME - Wide-angle time-lapse photography time",
    15227: "CMD_NOTIFY_CPU_MODE - CPU mode",
    15228: "CMD_NOTIFY_STATE_ASTRO_TRACKING_SPECIAL - Sun and moon tracking status",
    15229: "CMD_NOTIFY_POWER_OFF - Shutdown notification",
    15250: "CMD_NOTIFY_SKY_SEACHER_STATE - Sky detection status",
    15251: "CMD_NOTIFY_WIDE_MULTI_TRACK_RESULT - Wide-angle multi-target box result notification",
    15252: "CMD_NOTIFY_WIDE_TRACK_RESULT - Wide-angle single target box result notification",
    15257: "CMD_NOTIFY_FOCUS - Focus Position",
    
    # Internal/Undocumented Commands (observed in logs)
    15256: "CMD_INTERNAL_STREAM_INFO - Stream information update",
    15258: "CMD_INTERNAL_HOST_MODE - Host mode status",
    15261: "CMD_INTERNAL_CAMERA_STATUS - Camera status update", 
    15262: "CMD_INTERNAL_INIT_COMPLETE - Initialization complete",
    
    # Panorama Commands
    15500: "CMD_PANORAMA_START_GRID - Start panorama",
    15501: "CMD_PANORAMA_STOP - Stop panorama",
    15502: "CMD_PANORAMA_START_EULER_RANGE - Start panorama Euler Range",
}

def get_command_description(cmd_number):
    """Get human-readable description for a command number."""
    return DWARF_COMMAND_MAP.get(cmd_number, f"Unknown Command {cmd_number}")

def get_command_category(cmd_number):
    """Get the category of a command based on its number range."""
    if 10000 <= cmd_number <= 10999:
        return "Camera Control"
    elif 11000 <= cmd_number <= 11999:
        return "Astronomical"
    elif 12000 <= cmd_number <= 12999:
        return "Focus Control"
    elif 15200 <= cmd_number <= 15299:
        return "Status Notification"
    elif 15300 <= cmd_number <= 15399:
        return "Progress Notification"
    elif 15500 <= cmd_number <= 15599:
        return "Panorama"
    else:
        return "Other"
