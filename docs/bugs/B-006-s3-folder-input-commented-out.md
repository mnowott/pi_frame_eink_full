# B-006: SettingsApp s3_folder input commented out, hardcoded default

Status: Closed
Last updated: 2026-03-07
Severity: Medium

## Description

In `SettingsApp/settingsapp/app.py`, the `s3_folder` text input field is commented out. The code always writes `"s3_folder"` as the value regardless of what's in the loaded settings. Users cannot change the S3 subfolder name via the settings UI.

## Location

`s3_image_croper_ui_app/SettingsApp/settingsapp/app.py` — around line 242, the text input is commented out and a hardcoded `"s3_folder"` is used.

## Impact

If a user's `wifi.json` or sync config uses a different folder name, the SettingsApp will overwrite it with `"s3_folder"` on save, breaking the sync target path.

## Fix

Either:
1. Uncomment the `s3_folder` text input and wire it to the save logic, or
2. Preserve the existing `s3_folder` value from loaded settings on save (don't overwrite with hardcoded default)
