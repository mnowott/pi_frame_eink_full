# Settings UI Service

Last updated: 2026-03-07

## Overview

Streamlit web app running on port 80 of each Pi. Allows configuring the ePaper display (picture mode, rotation interval, quiet hours) without SSH access. Accessible at `http://<pi-hostname>/`.

## Source Files

| File | Role |
|------|------|
| `s3_image_croper_ui_app/SettingsApp/settingsapp/app.py` | Streamlit UI: load/save settings.json, form inputs |
| `s3_image_croper_ui_app/SettingsApp/settingsapp/main.py` | CLI entry point (`poetry run settingsapp --port 80`) |
| `s3_image_croper_ui_app/SettingsApp/pyproject.toml` | Dependencies (Streamlit, Pillow, boto3, pyhere) |
| `s3_image_croper_ui_app/install_settings.sh` | Installer: Poetry + systemd service |

## Systemd Unit

```ini
# settingsapp.service
[Service]
User=<install-user>
ExecStart=/bin/bash -lc 'poetry run settingsapp --port 80 --address 0.0.0.0'
WorkingDirectory=<repo>/s3_image_croper_ui_app/SettingsApp
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=5

# Sandboxing
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictNamespaces=true
LockPersonality=true
RestrictRealtime=true
RestrictSUIDSGID=true
PrivateDevices=true
ReadWritePaths=/mnt/epaper_sd
ReadWritePaths=~/.config/epaper_settings
ReadWritePaths=~/.cache
```

Uses `CAP_NET_BIND_SERVICE` to bind port 80 without root.

> **Note:** `ReadWritePaths=~/.cache` is required because Poetry creates its virtualenv in `~/.cache/pypoetry/virtualenvs/`, and `ProtectHome=read-only` would block it. The install script runs `poetry install` as the real user (not root) to ensure the venv is in the correct home directory.

## Behavior

- **Load settings:** Reads from SD card `/mnt/epaper_sd/epaper_settings/settings.json` (primary), falls back to `~/.config/epaper_settings/settings.json`
- **Save settings:** Writes to both SD and home config. Also writes `/mnt/epaper_sd/refresh_time.txt` for backward compatibility.
- **SD detection:** Uses `os.path.ismount("/mnt/epaper_sd")` to check if SD is available. Shows warning if not mounted.

## Form Fields

| Field | Type | Range | Default |
|-------|------|-------|---------|
| Picture mode | selectbox | local, online, both | both |
| Change interval (min) | number | 1-1440 | 15 |
| S3 folder name | text | — | s3_folder |
| Enable quiet hours | checkbox | — | off |
| Evening time | time | HH:MM | 22:00 |
| Morning time | time | HH:MM | 06:00 |

Note: S3 folder name input is currently commented out in the code; it always writes `"s3_folder"`.

## Installation

```bash
cd s3_image_croper_ui_app
sudo bash install_settings.sh
```

## Debugging

```bash
sudo systemctl status settingsapp.service
journalctl -u settingsapp.service -f

# Manual run
cd s3_image_croper_ui_app/SettingsApp
poetry run settingsapp --port 8080
```
