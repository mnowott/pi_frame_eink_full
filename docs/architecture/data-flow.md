# Data Flow

Last updated: 2026-03-07

## Image Pipeline (end-to-end)

```
1. UPLOAD          User uploads images via ImageUiApp (browser)
                   ├── Optional pre-downscale (max_dim setting)
                   ├── Interactive crop to 800x480
                   ├── Save as PNG
                   └── PUT to S3: s3://<bucket>/images/<filename>.png

2. SYNC            pi-s3-sync (runs every 15 min via systemd timer)
                   ├── Optionally connect Wi-Fi via nmcli (wifi.json)
                   ├── aws s3 sync s3://<bucket> /mnt/epaper_sd/s3_folder/
                   │   --delete --exclude *.zip
                   └── New/changed images land on SD card

3. DETECT          sd_monitor.py (runs continuously as systemd service)
                   ├── Polls /mnt/epaper_sd every 30 seconds
                   ├── Tracks directory mtime + file count
                   ├── Checks quiet hours (stop_rotation_between)
                   └── On change: restarts frame_manager.py subprocess

4. PROCESS         frame_manager.py (spawned by sd_monitor)
                   ├── Loads settings.json (picture_mode determines source)
                   │   ├── "online" → only s3_folder/
                   │   ├── "local"  → SD minus s3_folder (filtered copy)
                   │   └── "both"   → entire SD
                   ├── Runs image_converter.py on source → _epaper_pic/
                   │   ├── EXIF auto-rotate
                   │   ├── Aspect-ratio resize to fit 800x480
                   │   ├── Center crop to exact 800x480
                   │   └── Enhance color (1.5x) + contrast (1.5x)
                   └── Starts display rotation loop

5. DISPLAY         display_manager.py
                   ├── Boot sequence: start.jpg (30s) → pollock status (60s)
                   ├── Main loop: pick random image, display, sleep refresh_time
                   ├── Re-reads image list each cycle (picks up new files)
                   └── Fallback: pollock status card or no_valid_images.jpg
```

## Configuration Flow

```
SettingsApp (browser on http://<pi-ip>/)
  │
  ├── Reads settings.json from SD (primary) or ~/.config/epaper_frame/ (fallback)
  ├── User edits: picture_mode, change_interval_minutes, quiet hours, s3_folder
  ├── Saves settings.json back to SD + home
  └── Writes refresh_time.txt to SD (backward compat)
        │
        ▼
sd_monitor.py detects mtime change on next 30s poll
  │
  └── Restarts frame_manager.py with new settings
```

## Settings Load Priority

All display-stack modules use the same priority chain:

1. `/mnt/epaper_sd/epaper_settings/settings.json` (SD card — preferred)
2. `/etc/epaper_frame/settings.json`
3. `~/.config/epaper_frame/settings.json`
4. Local `settings.json` in script directory

## Credential Flow

Currently credentials are resolved from multiple sources (see [T-001](../tickets/T-001-credential-cleanup.md)):

| Component | Primary Source | Fallback |
|-----------|---------------|----------|
| pi-s3-sync | wifi.json on SD card | Environment vars (from systemd unit) |
| eInkFrame | .env file | Environment vars (from ~/.bashrc) |
| ImageUiApp | .env file | Environment vars |
| SettingsApp | (no AWS access needed) | — |

## SD Card Layout

```
/mnt/epaper_sd/
├── epaper_settings/
│   └── settings.json       # Display configuration
├── s3_folder/              # Synced from S3 (name configurable)
│   ├── images/
│   │   ├── photo1.png
│   │   └── photo2.png
│   └── ...
├── _epaper_pic/            # Processed image cache (auto-generated)
│   ├── photo1.png          # 800x480, enhanced
│   └── photo2.png
├── refresh_time.txt        # Legacy: refresh interval in seconds
├── wifi.json               # Optional: AWS creds + Wi-Fi config
└── (user local images)     # Any .jpg/.png/.bmp placed directly
```
