# System Hardening

Last updated: 2026-03-07

## Overview

Production hardening for Raspberry Pi: hardware watchdog, volatile journald (RAM-only logs), and OverlayFS read-only root filesystem. **Must be the last installation step. Irreversible without OS re-flash (OverlayFS can be toggled via raspi-config).**

## Source Files

| File | Role |
|------|------|
| `final_hardening.sh` | All-in-one hardening script |

## What It Does

### 1. Hardware Watchdog

- Adds `dtparam=watchdog=on` to `/boot/config.txt` (or `/boot/firmware/config.txt`)
- Installs and enables `watchdog` service
- Config: `/etc/watchdog.conf` with timeout=15s, max-load-1=24
- If the system hangs, the hardware watchdog reboots it automatically

### 2. Volatile Journald

- Creates `/etc/systemd/journald.conf.d/99-epaper-frame.conf`
- `Storage=volatile` — logs stored in RAM only, never written to SD/disk
- `RuntimeMaxUse=50M`, `RuntimeMaxFileSize=10M`, `MaxRetentionSec=3day`
- Reduces SD card wear from constant log writes

### 3. Firewall (ufw)

- Installs and enables `ufw`
- Default deny incoming, allow outgoing
- SSH rate-limited (`ufw limit 22/tcp`) — always allowed first for safety
- Port 80 allowed from all RFC1918 ranges (192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12)

### 4. SSH Hardening

- Creates `/etc/ssh/sshd_config.d/99-epaper.conf`
- Disables root login, empty passwords, X11 forwarding, TCP forwarding
- MaxAuthTries=3, keepalive timeout 10 min
- **Password auth intentionally left enabled** — must be manually disabled after key auth is confirmed

### 5. Kernel Parameters

- Creates `/etc/sysctl.d/99-epaper.conf`
- Disables SysRq, source routing, IP redirects
- Enables syncookies, martian logging, reverse-path filtering
- Disables IPv6

### 6. Peripheral Disablement

- Bluetooth: `dtoverlay=disable-bt` in boot config
- HDMI CEC: `hdmi_ignore_cec_init=1` in boot config

### 7. Swap Disabled

- `dphys-swapfile uninstall` — reduces SD card wear

### 8. OverlayFS Read-Only Root

- `sudo raspi-config nonint enable_overlayfs`
- Root filesystem becomes read-only; changes are written to a RAM overlay and lost on reboot
- The SD card mount at `/mnt/epaper_sd` is unaffected (separate mount point)
- Adds a bash login notice explaining the behavior

## Installation

```bash
# ONLY after all other steps are verified working
sudo bash final_hardening.sh
sudo reboot
```

## Maintenance Mode

To make persistent changes after hardening:

```bash
sudo raspi-config nonint disable_overlayfs
sudo reboot
# ... make changes ...
sudo raspi-config nonint enable_overlayfs
sudo reboot
```

## Debugging

```bash
# Check watchdog
sudo systemctl status watchdog.service
cat /etc/watchdog.conf

# Check journald
journalctl --disk-usage
cat /etc/systemd/journald.conf.d/99-epaper-frame.conf

# Check firewall
sudo ufw status verbose

# Check SSH config
cat /etc/ssh/sshd_config.d/99-epaper.conf

# Check sysctl
sysctl -a 2>/dev/null | grep -E 'sysrq|syncookies|rp_filter'

# Check overlay status
mount | grep overlay
```
