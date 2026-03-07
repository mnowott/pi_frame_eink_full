# SD Card Mount Service

Last updated: 2026-03-07

## Overview

Auto-mounts a USB SD card reader to `/mnt/epaper_sd` using a systemd mount unit and udev rule. The SD card serves as shared storage for synced images, local images, and settings.

## Source Files

| File | Role |
|------|------|
| `install_sd_card_reader.sh` | Installer: detects partition, creates mount unit + udev rule |

## Created Files

| File | Purpose |
|------|---------|
| `/etc/systemd/system/mnt-epaper_sd.mount` | Systemd mount unit |
| `/etc/udev/rules.d/99-epaper-sd-mount.rules` | Udev rule for hot-plug auto-mount |

## Mount Unit

```ini
[Mount]
What=/dev/disk/by-uuid/<UUID>
Where=/mnt/epaper_sd
Type=vfat
Options=defaults,uid=<user>,gid=<group>,umask=0022,nofail
```

The `nofail` option prevents boot failure if the SD card is missing.

## Detection Logic

The installer:
1. Scans `/dev/sd?*` for vfat partitions (via `lsblk -no FSTYPE`)
2. Skips partitions labeled "boot"
3. Picks the first matching partition
4. Reads its UUID via `lsblk -no UUID`
5. Creates mount unit and udev rule

## Installation

```bash
# Plug in USB SD card reader first
sudo bash install_sd_card_reader.sh
```

## Debugging

```bash
sudo systemctl status mnt-epaper_sd.mount
lsblk -f   # Check detected filesystems
ls /mnt/epaper_sd/
```
