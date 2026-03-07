# Pi Monitoring & Health Check Guide

How to verify your ePaper frame Pi is healthy, diagnose issues, and maintain the system.

## Quick Health Check (one-liner)

```bash
echo "=== Services ===" && \
systemctl is-active epaper.service settingsapp.service sd-s3-sync.timer watchdog.service mnt-epaper_sd.mount && \
echo "=== SD card ===" && \
mountpoint -q /mnt/epaper_sd && echo "SD: mounted" || echo "SD: NOT mounted" && \
echo "=== Firewall ===" && \
sudo ufw status | head -5 && \
echo "=== Disk ===" && \
df -h / /mnt/epaper_sd 2>/dev/null && \
echo "=== Memory ===" && \
free -h | head -2 && \
echo "=== Uptime ===" && \
uptime
```

## Service-by-Service Checks

### 1. ePaper Display (`epaper.service`)

```bash
# Status
sudo systemctl status epaper.service

# Recent logs (last 50 lines)
journalctl -u epaper.service -n 50 --no-pager

# Is it rotating images?
# Look for "Displaying image:" or "Starting frame_manager" in logs
journalctl -u epaper.service --since "1 hour ago" | grep -i "display\|image\|frame_manager"
```

**Common issues:**
- `sd_monitor` running but no images → check SD card has images, check `picture_mode` in settings
- `frame_manager` keeps restarting → SPI not enabled (`sudo raspi-config` → Interfaces → SPI)
- Display shows nothing → check HAT ribbon cable, verify `epd7in3f` driver matches your display

### 2. Settings UI (`settingsapp.service`)

```bash
# Status
sudo systemctl status settingsapp.service

# Is the web UI reachable?
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost/

# Recent logs
journalctl -u settingsapp.service -n 30 --no-pager
```

**Common issues:**
- Port 80 not reachable → check `CAP_NET_BIND_SERVICE` in service unit, check firewall (`sudo ufw status`)
- Settings not saving → check SD card is mounted and writable: `touch /mnt/epaper_sd/test && rm /mnt/epaper_sd/test`

### 3. S3 Sync (`sd-s3-sync.timer` / `sd-s3-sync.service`)

```bash
# Timer status and next run time
sudo systemctl list-timers sd-s3-sync.timer

# Last sync result
journalctl -u sd-s3-sync.service -n 30 --no-pager

# Trigger a manual sync
sudo systemctl start sd-s3-sync.service
journalctl -u sd-s3-sync.service -n 30 --no-pager
```

**Common issues:**
- `wifi.json not found` → ensure `wifi.json` exists on SD card root or in home directory
- AWS credential errors → check `/etc/epaper-settings/s3-sync.env` or `wifi.json` keys
- Wi-Fi connection failures → check `nmcli dev wifi list`, ensure NetworkManager is active

### 4. SD Card Mount (`mnt-epaper_sd.mount`)

```bash
# Mount status
sudo systemctl status mnt-epaper_sd.mount
mountpoint /mnt/epaper_sd

# What's on the SD?
ls -la /mnt/epaper_sd/

# Check mount options (should include nosuid,noexec,nodev)
mount | grep epaper_sd

# Disk usage
df -h /mnt/epaper_sd
```

**Common issues:**
- Not mounted → USB card reader unplugged or UUID changed. Run `lsblk -f` to check.
- Read-only → vfat filesystem error. Unmount and run `fsck.vfat /dev/sdX1`.

### 5. Watchdog

```bash
sudo systemctl status watchdog.service
cat /etc/watchdog.conf | grep -v '^#' | grep -v '^$'
```

### 6. Firewall

```bash
sudo ufw status verbose
```

Expected rules:
- `22/tcp LIMIT` — SSH
- `80` from `192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12` — SettingsApp

## System Health

### Memory and CPU

```bash
free -h
top -bn1 | head -20
```

Pi Zero W/2W has only 512MB RAM. If memory is tight, check if any service is leaking.

### Disk / SD Card Wear

```bash
# Root filesystem (should be OverlayFS if hardened)
df -h /
mount | grep overlay

# SD card
df -h /mnt/epaper_sd
```

### Temperature

```bash
vcgencmd measure_temp
# Should be below 70°C. Above 80°C = throttling.
```

### Network

```bash
# Current Wi-Fi connection
nmcli dev wifi | head -5

# IP address
hostname -I

# DNS resolution
ping -c 1 s3.eu-central-1.amazonaws.com
```

## Log Analysis

### All ePaper-related logs

```bash
journalctl -u epaper.service -u settingsapp.service -u sd-s3-sync.service --since "today" --no-pager
```

### Errors only

```bash
journalctl -u epaper.service -u settingsapp.service -u sd-s3-sync.service -p err --since "today" --no-pager
```

### Boot log (last boot)

```bash
journalctl -b -0 --no-pager | head -100
```

## Settings Verification

```bash
# Current settings on SD
cat /mnt/epaper_sd/epaper_settings/settings.json 2>/dev/null || echo "No settings on SD"

# Fallback settings
cat ~/.config/epaper_settings/settings.json 2>/dev/null || echo "No fallback settings"

# Refresh time file
cat /mnt/epaper_sd/refresh_time.txt 2>/dev/null || echo "No refresh_time.txt"
```

## Maintenance (with OverlayFS)

If the system has OverlayFS enabled, root is read-only. To make persistent changes:

```bash
# 1. Disable overlay
sudo raspi-config nonint disable_overlayfs
sudo reboot

# 2. Make changes (apt upgrade, config edits, etc.)
sudo apt update && sudo apt upgrade -y

# 3. Re-enable overlay
sudo raspi-config nonint enable_overlayfs
sudo reboot
```

The SD card at `/mnt/epaper_sd` is always writable regardless of OverlayFS state.

## SSH Key Setup (recommended post-install)

```bash
# From your laptop:
ssh-copy-id pi@<pi-ip>

# Verify key login works:
ssh pi@<pi-ip>

# Then disable password auth on the Pi:
echo "PasswordAuthentication no" | sudo tee -a /etc/ssh/sshd_config.d/99-epaper.conf
sudo systemctl reload sshd
```
