# B-004: Potential command injection in Wi-Fi connection

Status: Closed
Last updated: 2026-03-07
Severity: High

## Description

`pi-s3-sync/scripts/sync_s3_from_sd.py` passes SSID and password from `wifi.json` to `nmcli` via `subprocess.run()`. If `wifi.json` is user-editable (it sits on a removable SD card), a crafted SSID or password could inject shell commands.

## Location

`pi-s3-sync/scripts/sync_s3_from_sd.py` — `ensure_wifi_connection()` function, where SSID/password are interpolated into the nmcli command.

## Current Mitigation

The script uses `subprocess.run()` with a command list (not `shell=True`), which prevents shell injection. However, nmcli itself may interpret special characters in SSID/password unexpectedly.

## Fix

1. Verify that `subprocess.run()` is called with a list, not a string (this is already the case — confirm)
2. Validate/sanitize SSID and password values before passing to nmcli
3. Consider using NetworkManager's D-Bus API via `pydbus` instead of shelling out to nmcli
