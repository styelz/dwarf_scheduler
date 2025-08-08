# Dwarf Python API: Command Reference & Integration Guide

This document provides an overview of the available commands, functions, and integration patterns for the Dwarf Python API, as found in the `dwarf_python_api` package. It covers the main modules, their key functions, and how to use them in your own Python applications.

---

## Table of Contents
- [Overview](#overview)
- [Configuration Management](#configuration-management)
- [Device Control & Utilities](#device-control--utilities)
- [WebSocket Communication](#websocket-communication)
- [FTP Utilities](#ftp-utilities)
- [Logging](#logging)
- [Data Utilities](#data-utilities)
- [Example Integration](#example-integration)
- [Protocol Command Codes (DwarfCMD)](#protocol-command-codes-dwarfcmd)

---

## Overview
The Dwarf Python API is organized into several modules:
- `get_config_data.py`: Read/update config values
- `get_live_data_dwarf.py`: FTP and live data utilities
- `lib/dwarf_utils.py`: Device control, config access, parsing
- `lib/websockets_utils.py`: WebSocket protocol, async client
- `lib/ftp_utils.py`: SSH/FTP helpers
- `lib/my_logger.py`: Logging
- `lib/data_utils.py`, `lib/data_wide_utils.py`: Exposure/gain tables
- `proto/`: Protocol buffer definitions

---

## Configuration Management
### `dwarf_python_api.get_config_data`
- **get_config_data(config_file=None, print_log=False)**: Returns a dict of config values from `config.py`.
- **update_config_data(id_param, value, print_log=False, config_file=None, tmp_file=None)**: Update a config value by key.
- **set_config_data(config_file, config_file_tmp, lock_file, print_log=False)**: Set config file paths.

#### Example:
```python
from dwarf_python_api import get_config_data
cfg = get_config_data.get_config_data()
get_config_data.update_config_data('client_id', 'NEWID')
```

---

## Device Control & Utilities
### `dwarf_python_api.lib.dwarf_utils`
- **perform_disconnect()**: Disconnects the device.
- **read_longitude() / read_latitude() / read_timezone()**: Read location/timezone from config.
- **read_camera_exposure() / read_camera_gain() / ...**: Read camera settings from config.
- **parse_ra_to_float(ra_str)**: Parse RA string to float.
- **parse_dec_to_float(dec_str)**: Parse Dec string to float.

#### Example:
```python
from dwarf_python_api.lib import dwarf_utils
lon = dwarf_utils.read_longitude()
```

---

## WebSocket Communication
### `dwarf_python_api.lib.websockets_utils`
- **connect_socket() / disconnect_socket()**: Manage WebSocket connection.
- **WebSocketClient**: Async client for protocol commands.
- **process_command(command, result)**: Validate command/result pairs.
- **ws_uri(dwarf_ip)**: Build WebSocket URI.
- **getDwarfCMDName(code)**: Get command name from code.

#### Example:
```python
from dwarf_python_api.lib import websockets_utils
websockets_utils.connect_socket()
```

---

## FTP Utilities
### `dwarf_python_api.get_live_data_dwarf`
- **download_file(ftp, remote_file, local_file)**: Download file via FTP.
- **getlistPhoto(cameraPhoto, indexStart, indexEnd)**: List photo files on device.
- **getLastPhoto(history, camera)**: Get last photo file.

### `dwarf_python_api.lib.ftp_utils`
- **update_client_id_from_last_session(dwarf_ip)**: Update client ID from device log via SSH.

---

## Logging
### `dwarf_python_api.lib.my_logger`
- **logger**: Standard Python logger instance.
- **logger.notice(msg)**, **logger.success(msg)**: Custom log levels.
- **update_log_file()**: Update log file handler based on config.

---

## Data Utilities
### `dwarf_python_api.lib.data_utils` / `data_wide_utils`
- **AllowedExposures / AllowedWideExposures**: Classes with exposure tables.
- **get_exposure_index_by_name(name)**: Get exposure index by name.
- **get_gain_index_by_name(name)**: Get gain index by name.

---

## Example Integration
```python
from dwarf_python_api.get_config_data import get_config_data
from dwarf_python_api.lib.dwarf_utils import perform_disconnect, read_longitude
from dwarf_python_api.lib.websockets_utils import connect_socket

# Read config
cfg = get_config_data()

# Connect to device
connect_socket()

# Read longitude
lon = read_longitude()

# Disconnect
perform_disconnect()
```

---

## Protocol Command Codes (DwarfCMD)

The following commands correspond to the codes used with `getDwarfCMDName(code)` and are available for use with the WebSocket protocol:

```
NO_CMD = 0
CMD_CAMERA_TELE_OPEN_CAMERA = 10000
CMD_CAMERA_TELE_CLOSE_CAMERA = 10001
CMD_CAMERA_TELE_PHOTOGRAPH = 10002
CMD_CAMERA_TELE_BURST = 10003
CMD_CAMERA_TELE_STOP_BURST = 10004
CMD_CAMERA_TELE_START_RECORD = 10005
CMD_CAMERA_TELE_STOP_RECORD = 10006
CMD_CAMERA_TELE_SET_EXP_MODE = 10007
CMD_CAMERA_TELE_GET_EXP_MODE = 10008
CMD_CAMERA_TELE_SET_EXP = 10009
CMD_CAMERA_TELE_GET_EXP = 10010
CMD_CAMERA_TELE_SET_GAIN_MODE = 10011
CMD_CAMERA_TELE_GET_GAIN_MODE = 10012
CMD_CAMERA_TELE_SET_GAIN = 10013
CMD_CAMERA_TELE_GET_GAIN = 10014
CMD_CAMERA_TELE_SET_BRIGHTNESS = 10015
CMD_CAMERA_TELE_GET_BRIGHTNESS = 10016
CMD_CAMERA_TELE_SET_CONTRAST = 10017
CMD_CAMERA_TELE_GET_CONTRAST = 10018
CMD_CAMERA_TELE_SET_SATURATION = 10019
CMD_CAMERA_TELE_GET_SATURATION = 10020
CMD_CAMERA_TELE_SET_HUE = 10021
CMD_CAMERA_TELE_GET_HUE = 10022
CMD_CAMERA_TELE_SET_SHARPNESS = 10023
CMD_CAMERA_TELE_GET_SHARPNESS = 10024
CMD_CAMERA_TELE_SET_WB_MODE = 10025
CMD_CAMERA_TELE_GET_WB_MODE = 10026
CMD_CAMERA_TELE_SET_WB_SCENE = 10027
CMD_CAMERA_TELE_GET_WB_SCENE = 10028
CMD_CAMERA_TELE_SET_WB_CT = 10029
CMD_CAMERA_TELE_GET_WB_CT = 10030
CMD_CAMERA_TELE_SET_IRCUT = 10031
CMD_CAMERA_TELE_GET_IRCUT = 10032
CMD_CAMERA_TELE_START_TIMELAPSE_PHOTO = 10033
CMD_CAMERA_TELE_STOP_TIMELAPSE_PHOTO = 10034
CMD_CAMERA_TELE_SET_ALL_PARAMS = 10035
CMD_CAMERA_TELE_GET_ALL_PARAMS = 10036
CMD_CAMERA_TELE_SET_FEATURE_PARAM = 10037
CMD_CAMERA_TELE_GET_ALL_FEATURE_PARAMS = 10038
CMD_CAMERA_TELE_GET_SYSTEM_WORKING_STATE = 10039
CMD_CAMERA_TELE_SET_JPG_QUALITY = 10040
CMD_CAMERA_TELE_PHOTO_RAW = 10041
CMD_CAMERA_TELE_SET_RTSP_BITRATE_TYPE = 10042
CMD_ASTRO_START_CALIBRATION = 11000
CMD_ASTRO_STOP_CALIBRATION = 11001
CMD_ASTRO_START_GOTO_DSO = 11002
CMD_ASTRO_START_GOTO_SOLAR_SYSTEM = 11003
CMD_ASTRO_STOP_GOTO = 11004
CMD_ASTRO_START_CAPTURE_RAW_LIVE_STACKING = 11005
CMD_ASTRO_STOP_CAPTURE_RAW_LIVE_STACKING = 11006
CMD_ASTRO_START_CAPTURE_RAW_DARK = 11007
CMD_ASTRO_STOP_CAPTURE_RAW_DARK = 11008
CMD_ASTRO_CHECK_GOT_DARK = 11009
CMD_ASTRO_GO_LIVE = 11010
CMD_ASTRO_START_TRACK_SPECIAL_TARGET = 11011
CMD_ASTRO_STOP_TRACK_SPECIAL_TARGET = 11012
CMD_ASTRO_START_ONE_CLICK_GOTO_DSO = 11013
CMD_ASTRO_START_ONE_CLICK_GOTO_SOLAR_SYSTEM = 11014
CMD_ASTRO_STOP_ONE_CLICK_GOTO = 11015
CMD_ASTRO_START_WIDE_CAPTURE_LIVE_STACKING = 11016
CMD_ASTRO_STOP_WIDE_CAPTURE_LIVE_STACKING = 11017
CMD_ASTRO_START_EQ_SOLVING = 11018
CMD_ASTRO_STOP_EQ_SOLVING = 11019
CMD_ASTRO_WIDE_GO_LIVE = 11020
CMD_ASTRO_START_CAPTURE_RAW_DARK_WITH_PARAM = 11021
CMD_ASTRO_STOP_CAPTURE_RAW_DARK_WITH_PARAM = 11022
CMD_ASTRO_GET_DARK_FRAME_LIST = 11023
CMD_ASTRO_DEL_DARK_FRAME_LIST = 11024
CMD_ASTRO_START_CAPTURE_WIDE_RAW_DARK_WITH_PARAM = 11025
CMD_ASTRO_STOP_CAPTURE_WIDE_RAW_DARK_WITH_PARAM = 11026
CMD_ASTRO_GET_WIDE_DARK_FRAME_LIST = 11027
CMD_ASTRO_DEL_WIDE_DARK_FRAME_LIST = 11028
CMD_CAMERA_WIDE_OPEN_CAMERA = 12000
CMD_CAMERA_WIDE_CLOSE_CAMERA = 12001
CMD_CAMERA_WIDE_SET_EXP_MODE = 12002
CMD_CAMERA_WIDE_GET_EXP_MODE = 12003
CMD_CAMERA_WIDE_SET_EXP = 12004
CMD_CAMERA_WIDE_GET_EXP = 12005
CMD_CAMERA_WIDE_SET_GAIN = 12006
CMD_CAMERA_WIDE_GET_GAIN = 12007
CMD_CAMERA_WIDE_SET_BRIGHTNESS = 12008
CMD_CAMERA_WIDE_GET_BRIGHTNESS = 12009
CMD_CAMERA_WIDE_SET_CONTRAST = 12010
CMD_CAMERA_WIDE_GET_CONTRAST = 12011
CMD_CAMERA_WIDE_SET_SATURATION = 12012
CMD_CAMERA_WIDE_GET_SATURATION = 12013
CMD_CAMERA_WIDE_SET_HUE = 12014
CMD_CAMERA_WIDE_GET_HUE = 12015
CMD_CAMERA_WIDE_SET_SHARPNESS = 12016
CMD_CAMERA_WIDE_GET_SHARPNESS = 12017
CMD_CAMERA_WIDE_SET_WB_MODE = 12018
CMD_CAMERA_WIDE_GET_WB_MODE = 12019
CMD_CAMERA_WIDE_SET_WB_CT = 12020
CMD_CAMERA_WIDE_GET_WB_CT = 12021
CMD_CAMERA_WIDE_PHOTOGRAPH = 12022
CMD_CAMERA_WIDE_BURST = 12023
CMD_CAMERA_WIDE_STOP_BURST = 12024
CMD_CAMERA_WIDE_START_TIMELAPSE_PHOTO = 12025
CMD_CAMERA_WIDE_STOP_TIMELAPSE_PHOTO = 12026
CMD_CAMERA_WIDE_GET_ALL_PARAMS = 12027
CMD_CAMERA_WIDE_SET_ALL_PARAMS = 12028
CMD_CAMERA_WIDE_START_RECORD = 12030
CMD_CAMERA_WIDE_STOP_RECORD = 12031
CMD_SYSTEM_SET_TIME = 13000
CMD_SYSTEM_SET_TIME_ZONE = 13001
CMD_SYSTEM_SET_MTP_MODE = 13002
CMD_SYSTEM_SET_CPU_MODE = 13003
CMD_SYSTEM_SET_MASTERLOCK = 13004
CMD_RGB_POWER_OPEN_RGB = 13500
CMD_RGB_POWER_CLOSE_RGB = 13501
CMD_RGB_POWER_POWER_DOWN = 13502
CMD_RGB_POWER_POWERIND_ON = 13503
CMD_RGB_POWER_POWERIND_OFF = 13504
CMD_RGB_POWER_REBOOT = 13505
CMD_STEP_MOTOR_RUN = 14000
CMD_STEP_MOTOR_RUN_TO = 14001
CMD_STEP_MOTOR_STOP = 14002
CMD_STEP_MOTOR_RESET = 14003
CMD_STEP_MOTOR_CHANGE_SPEED = 14004
CMD_STEP_MOTOR_CHANGE_DIRECTION = 14005
CMD_STEP_MOTOR_SERVICE_JOYSTICK = 14006
CMD_STEP_MOTOR_SERVICE_JOYSTICK_FIXED_ANGLE = 14007
CMD_STEP_MOTOR_SERVICE_JOYSTICK_STOP = 14008
CMD_STEP_MOTOR_SERVICE_DUAL_CAMERA_LINKAGE = 14009
CMD_STEP_MOTOR_RUN_IN_PULSE = 14010
CMD_STEP_MOTOR_GET_POSITION = 14011
CMD_TRACK_START_TRACK = 14800
CMD_TRACK_STOP_TRACK = 14801
CMD_SENTRY_MODE_START = 14802
CMD_SENTRY_MODE_STOP = 14803
CMD_MOT_START = 14804
CMD_MOT_TRACK_ONE = 14805
CMD_UFOTRACK_MODE_START = 14806
CMD_UFOTRACK_MODE_STOP = 14807
CMD_MOT_WIDE_TRACK_ONE = 14808
CMD_WIDE_TELE_TRACK_SWITCH = 14809
CMD_UFO_HAND_AOTO_MODE = 14810
CMD_FOCUS_AUTO_FOCUS = 15000
CMD_FOCUS_MANUAL_SINGLE_STEP_FOCUS = 15001
CMD_FOCUS_START_MANUAL_CONTINU_FOCUS = 15002
CMD_FOCUS_STOP_MANUAL_CONTINU_FOCUS = 15003
CMD_FOCUS_START_ASTRO_AUTO_FOCUS = 15004
CMD_FOCUS_STOP_ASTRO_AUTO_FOCUS = 15005
CMD_NOTIFY_TELE_WIDI_PICTURE_MATCHING = 15200
CMD_NOTIFY_ELE = 15201
CMD_NOTIFY_CHARGE = 15202
CMD_NOTIFY_SDCARD_INFO = 15203
CMD_NOTIFY_TELE_RECORD_TIME = 15204
CMD_NOTIFY_TELE_TIMELAPSE_OUT_TIME = 15205
CMD_NOTIFY_STATE_CAPTURE_RAW_DARK = 15206
CMD_NOTIFY_PROGRASS_CAPTURE_RAW_DARK = 15207
CMD_NOTIFY_STATE_CAPTURE_RAW_LIVE_STACKING = 15208
CMD_NOTIFY_PROGRASS_CAPTURE_RAW_LIVE_STACKING = 15209
CMD_NOTIFY_STATE_ASTRO_CALIBRATION = 15210
CMD_NOTIFY_STATE_ASTRO_GOTO = 15211
CMD_NOTIFY_STATE_ASTRO_TRACKING = 15212
CMD_NOTIFY_TELE_SET_PARAM = 15213
CMD_NOTIFY_WIDE_SET_PARAM = 15214
CMD_NOTIFY_TELE_FUNCTION_STATE = 15215
CMD_NOTIFY_WIDE_FUNCTION_STATE = 15216
CMD_NOTIFY_SET_FEATURE_PARAM = 15217
CMD_NOTIFY_TELE_BURST_PROGRESS = 15218
CMD_NOTIFY_PANORAMA_PROGRESS = 15219
CMD_NOTIFY_WIDE_BURST_PROGRESS = 15220
CMD_NOTIFY_RGB_STATE = 15221
CMD_NOTIFY_POWER_IND_STATE = 15222
CMD_NOTIFY_WS_HOST_SLAVE_MODE = 15223
CMD_NOTIFY_MTP_STATE = 15224
CMD_NOTIFY_TRACK_RESULT = 15225
CMD_NOTIFY_WIDE_TIMELAPSE_OUT_TIME = 15226
CMD_NOTIFY_CPU_MODE = 15227
CMD_NOTIFY_STATE_ASTRO_TRACKING_SPECIAL = 15228
CMD_NOTIFY_POWER_OFF = 15229
CMD_NOTIFY_ALBUM_UPDATE = 15230
CMD_NOTIFY_SENTRY_MODE_STATE = 15231
CMD_NOTIFY_SENTRY_MODE_TRACK_RESULT = 15232
CMD_NOTIFY_STATE_ASTRO_ONE_CLICK_GOTO = 15233
CMD_NOTIFY_STREAM_TYPE = 15234
CMD_NOTIFY_WIDE_RECORD_TIME = 15235
CMD_NOTIFY_STATE_WIDE_CAPTURE_RAW_LIVE_STACKING = 15236
CMD_NOTIFY_PROGRASS_WIDE_CAPTURE_RAW_LIVE_STACKING = 15237
CMD_NOTIFY_MULTI_TRACK_RESULT = 15238
CMD_NOTIFY_EQ_SOLVING_STATE = 15239
CMD_NOTIFY_UFO_MODE_STATE = 15240
CMD_NOTIFY_TELE_LONG_EXP_PROGRESS = 15241
CMD_NOTIFY_WIDE_LONG_EXP_PROGRESS = 15242
CMD_NOTIFY_TEMPERATURE = 15243
CMD_NOTIFY_PANORAMA_UPLOAD_COMPRESS_PROGRESS = 15244
CMD_NOTIFY_PANORAMA_UPLOAD_UPLOAD_PROGRESS = 15245
CMD_NOTIFY_PANORAMA_UPLOAD_COMPLETE = 15246
CMD_NOTIFY_STATE_CAPTURE_WIDE_RAW_DARK = 15247
CMD_NOTIFY_SHOOTING_SCHEDULE_RESULT_AND_STATE = 15248
CMD_NOTIFY_SHOOTING_TASK_STATE = 15249
CMD_NOTIFY_SKY_SEACHER_STATE = 15250
CMD_NOTIFY_WIDE_MULTI_TRACK_RESULT = 15251
CMD_NOTIFY_WIDE_TRACK_RESULT = 15252
CMD_NOTIFY_FOCUS = 15257
CMD_PANORAMA_START_GRID = 15500
CMD_PANORAMA_STOP = 15501
CMD_PANORAMA_START_EULER_RANGE = 15502
```

Each command can be sent via the WebSocket protocol using the API's command functions/classes. See the protocol and `websockets_utils.py` for details on usage.

---

## Functions in `dwarf_utils.py`

The following functions are available in `dwarf_python_api.lib.dwarf_utils`:

### Device/Session Control
- perform_disconnect()
- perform_getstatus()
- perform_goto(ra, dec, target)
- perform_goto_stellar(target_id, target_name)
- perform_open_camera()
- perform_takePhoto()
- perform_open_widecamera()
- perform_takeWidePhoto()
- perform_waitEndAstroPhoto()
- perform_waitEndAstroWidePhoto()
- perform_takeAstroPhoto()
- perform_stopAstroPhoto()
- perform_takeAstroWidePhoto()
- perform_stopAstroWidePhoto()
- perform_GoLive()
- perform_time()
- perform_timezone()
- perform_calibration()
- perform_stop_calibration()
- perform_stop_goto()
- perform_start_autofocus(infinite=False)
- perform_stop_autofocus()
- perform_decoding_test(show_test, show_test1, show_test2)
- perform_decode_wireshark(user_frame, masked, user_maskedcode)
- perform_get_all_camera_setting()
- perform_get_all_feature_camera_setting()
- perform_get_all_camera_wide_setting()
- perform_get_camera_setting(type)
- perform_update_camera_setting(type, value, dwarf_id="2")
- start_polar_align()
- stop_polar_align()
- motor_action(action, correction=0)

### Config/Status Readers
- read_longitude()
- read_latitude()
- read_timezone()
- read_camera_exposure()
- read_camera_gain()
- read_camera_IR()
- read_camera_binning()
- read_camera_format()
- read_camera_count()
- read_camera_wide_exposure()
- read_camera_wide_gain()
- read_bluetooth_ble_wifi_type()
- read_bluetooth_autoAP()
- read_bluetooth_country_list()
- read_bluetooth_country()
- read_bluetooth_ble_psd()
- read_bluetooth_autoSTA()
- read_bluetooth_ble_STA_ssid()
- read_bluetooth_ble_STA_pwd()
- save_bluetooth_config_from_ini_file()

### Utilities
- parse_ra_to_float(ra_string)
- parse_dec_to_float(dec_string)
- format_double(value_str)
- decimal_to_dms(decimal_degrees)
- get_result_value(type, result_cnx, is_double=False)
- get_result_polar_value(result_cnx)
- unset_HostMaster()
- set_HostMaster()

See the source code for argument details and return values. These functions cover device connection, camera control, session management, config reading, and various utility operations for the Dwarf system.
