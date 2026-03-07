# SettingsApp

Streamlit web UI for configuring the ePaper display, running on each Raspberry Pi on port 80.

## Features

- **Picture mode**: local (SD only), online (S3 folder only), both
- **Change interval**: minutes between image rotations (1-1440)
- **Quiet hours**: stop rotation between configurable evening/morning times
- **SD card detection**: shows mount status, warns if SD is unavailable

## Prerequisites

- Python 3.11+
- Poetry
- SD card mounted at `/mnt/epaper_sd` (via systemd mount unit)

## Installation (on Pi)

```bash
# From the repo root:
./s3_image_croper_ui_app/install_settings.sh
```

This installs Poetry dependencies and creates `settingsapp.service` on port 80.

## Running Manually

```bash
poetry install
poetry run settingsapp --port 80 --address 0.0.0.0
```

Requires `CAP_NET_BIND_SERVICE` to bind port 80 without root (handled by the systemd unit).

## Settings Storage

Settings are saved to two locations:

1. **SD card** (primary): `/mnt/epaper_sd/epaper_settings/settings.json`
2. **Home backup**: `~/.config/epaper_settings/settings.json`

Also writes `/mnt/epaper_sd/refresh_time.txt` for backward compatibility with older `sd_monitor` versions.

## Debugging

```bash
sudo systemctl status settingsapp
journalctl -u settingsapp -f
```

## Testing

```bash
poetry run pytest -q --tb=short
```
