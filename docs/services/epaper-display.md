# ePaper Display Service

Last updated: 2026-05-08

## Overview

The display stack runs as `epaper.service` and manages the full image pipeline: monitor SD card for changes, process images, and rotate them on the Waveshare ePaper display.

## Source Files

| File | Role |
|------|------|
| `eInkFrameWithStreamlitMananger/sd_monitor.py` | Entry point. Watches SD card, enforces quiet hours, manages frame_manager subprocess |
| `eInkFrameWithStreamlitMananger/frame_manager.py` | Selects image source based on `picture_mode`, runs converter, starts display loop |
| `eInkFrameWithStreamlitMananger/display_manager.py` | Controls ePaper hardware. Rotates images, shows status cards and fallback messages |
| `eInkFrameWithStreamlitMananger/image_converter.py` | Resizes/crops/enhances images to 800x480 for display |
| `eInkFrameWithStreamlitMananger/pollock_text.py` | Generates Pollock-style status cards with settings summary + internet status |
| `eInkFrameWithStreamlitMananger/lib/waveshare_epd/` | Hardware drivers for Waveshare panels (SPI/GPIO) |

## Systemd Unit

```ini
# epaper.service
[Unit]
After=network.target mnt-epaper_sd.mount

[Service]
User=<install-user>
ExecStart=<venv>/bin/python sd_monitor.py
# WorkingDirectory must be writable — lgpio creates a notification pipe (.lgd-nfy*)
WorkingDirectory=/tmp
Restart=always

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
DeviceAllow=/dev/spidev0.0 rw
DeviceAllow=/dev/spidev0.1 rw
DeviceAllow=/dev/gpiomem rw
DeviceAllow=/dev/gpiochip0 rw
DeviceAllow=/dev/gpiochip4 rw
SupplementaryGroups=spi i2c gpio
ReadWritePaths=/mnt/epaper_sd

[Install]
WantedBy=multi-user.target
```

Created by: `eInkFrameWithStreamlitMananger/setup.sh`

## Process Hierarchy

```
systemd
 └── sd_monitor.py (long-running)
      └── frame_manager.py (subprocess, restarted on SD changes)
           ├── image_converter.py (runs once per restart)
           └── display_manager.py (infinite rotation loop)
```

## Configuration

Reads `settings.json` from (priority order):
1. `/mnt/epaper_sd/epaper_settings/settings.json`
2. `/etc/epaper_settings/settings.json`
3. `~/.config/epaper_settings/settings.json`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `picture_mode` | string | `"both"` | `"local"` = SD only, `"online"` = S3 folder only, `"both"` = all |
| `change_interval_minutes` | int | 15 | Minutes between image rotations |
| `stop_rotation_between` | object/null | null | Quiet hours: `{"evening": "HH:MM", "morning": "HH:MM"}` |
| `s3_folder` | string | `"s3_folder"` | Subfolder name for S3-synced images on SD |

Fallback: `refresh_time.txt` on SD root (seconds, used if `change_interval_minutes` not in settings).

## Behavior

- **Polling:** sd_monitor checks SD every 30 seconds (mtime + file count of directory tree, excluding `_epaper_pic`)
- **Quiet hours:** During quiet hours, display sleeps; rotation resumes after morning time
- **Boot sequence:** start.jpg (30s) → pollock status card (60s) → image rotation
- **No images:** Shows pollock status card or `messages/no_valid_images.jpg`
- **Image processing:** EXIF auto-rotate → aspect-ratio resize → center crop to 800x480 → enhance color/contrast 1.5x
- **Cache:** Processed images stored in `/mnt/epaper_sd/_epaper_pic/`; cleared and rebuilt on each frame_manager restart
- **Corrupt-image self-heal:** If `image_converter` cannot decode a file, it logs and skips it. Files inside the S3 subtree (`<sd>/<s3_folder>/`) are also deleted, so the next `sd-s3-sync` tick (≤15 min) re-downloads a fresh copy from S3. Files outside the S3 subtree (e.g. dropped manually onto the SD root) are kept as-is — re-download cannot help them.

## Installation

```bash
# Manual step (not in install_all_pi.sh)
cd eInkFrameWithStreamlitMananger
bash setup.sh
# Requires reboot after
```

Setup enables SPI/I2C via raspi-config, installs system packages (`python3-spidev`, `python3-gpiozero`, `python3-pil`), creates venv at `~/epaper-venv`, and writes `epaper.service`.

## Debugging

```bash
sudo systemctl status epaper.service
journalctl -u epaper.service -f

# Manual run
cd eInkFrameWithStreamlitMananger
~/epaper-venv/bin/python sd_monitor.py
```

## Tests

```bash
cd eInkFrameWithStreamlitMananger
poetry run pytest
```

Tests cover S3Manager only (via moto mocked S3). Display logic is hardware-dependent and untested.
