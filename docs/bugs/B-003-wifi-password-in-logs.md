# B-003: Wi-Fi password logged in plaintext

Status: Open
Last updated: 2026-03-07
Severity: High

## Description

`pi-s3-sync/scripts/sync_s3_from_sd.py` logs the full `nmcli` connection command including the Wi-Fi password in plaintext. This appears in journald logs accessible to anyone with log access.

## Location

`pi-s3-sync/scripts/sync_s3_from_sd.py` — in the `ensure_wifi_connection()` function, the debug/info logging includes the command string with `wifi-sec.psk`.

## Fix

Redact password from log output before printing. Replace the actual password with `***` in the logged command string while keeping the real password in the executed command.
