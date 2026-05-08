# SD Card Mount Service

Last updated: 2026-05-08

## Overview

Auto-mounts a USB SD card reader to `/mnt/epaper_sd` using a systemd mount unit and udev rule. The SD card serves as shared storage for synced images, local images, and settings.

The mount unit and udev rule key off the **filesystem label `EPAPER_SD`**, not the partition UUID. This makes the setup hardware-agnostic: any vfat partition labelled `EPAPER_SD` will auto-mount, so swapping the data SD card between identical Pis (or replacing a failed card) needs no reconfiguration.

## Source Files

| File | Role |
|------|------|
| `install_sd_card_reader.sh` | Installer: detects partition, labels it `EPAPER_SD`, creates mount unit + udev rule |

## Created Files

| File | Purpose |
|------|---------|
| `/etc/systemd/system/mnt-epaper_sd.mount` | Systemd mount unit |
| `/etc/udev/rules.d/99-epaper-sd-mount.rules` | Udev rule for hot-plug auto-mount |

## Mount Unit

```ini
[Mount]
What=/dev/disk/by-label/EPAPER_SD
Where=/mnt/epaper_sd
Type=vfat
Options=defaults,uid=<user>,gid=<group>,umask=0022,nofail,nosuid,noexec,nodev
```

The `nofail` option prevents boot failure if the SD card is missing.

## Udev Rule

```
ACTION=="add", SUBSYSTEM=="block", ENV{ID_FS_LABEL}=="EPAPER_SD", ENV{SYSTEMD_WANTS}="mnt-epaper_sd.mount"
```

## Detection Logic

The installer:
1. Scans `/dev/sd?*` for vfat partitions (via `lsblk -prno NAME,FSTYPE,LABEL`)
2. Skips partitions labelled `boot` or `bootfs`
3. Picks the first remaining vfat partition (falls back to any vfat partition if none qualify)
4. Re-labels it `EPAPER_SD` via `fatlabel` (installs `dosfstools` if missing)
5. Writes the mount unit and udev rule keyed on the label

## Installation

```bash
# Plug in USB SD card reader first
sudo bash install_sd_card_reader.sh
```

The script is idempotent — safe to re-run on a Pi that already has a (possibly broken) mount unit.

## Debugging

```bash
sudo systemctl status mnt-epaper_sd.mount
lsblk -f                 # Check detected filesystems and labels
sudo blkid /dev/sd?*     # Confirm the EPAPER_SD label
ls /mnt/epaper_sd/
mountpoint /mnt/epaper_sd
```

## Recovery — Existing Pi with Broken Mount

If a Pi was provisioned with an older version of `install_sd_card_reader.sh` that hardcoded a UUID (e.g. `What=/dev/disk/by-uuid/<UUID>` or the literal placeholder `1234-5678`), the mount unit will not match the data SD card and `/mnt/epaper_sd` stays empty. Symptoms: display frozen on the last image, `sd-s3-sync` runs but writes nothing, `systemctl status mnt-epaper_sd.mount` shows `inactive (dead)`.

### 1. Diagnose

```bash
# OverlayFS active? (empty output = no)
mount | grep overlay

# Mount unit state and target
systemctl status mnt-epaper_sd.mount --no-pager
grep 'What=' /etc/systemd/system/mnt-epaper_sd.mount

# Udev rule
cat /etc/udev/rules.d/99-epaper-sd-mount.rules

# Block devices and labels
lsblk -f
mountpoint /mnt/epaper_sd && echo MOUNTED || echo "NOT MOUNTED"
```

Healthy state: mount unit `What=/dev/disk/by-label/EPAPER_SD`, udev rule keys on `ID_FS_LABEL=="EPAPER_SD"`, the data SD card has label `EPAPER_SD`, and `/mnt/epaper_sd` reports `MOUNTED`.

### 2. Disable OverlayFS (if active)

OverlayFS makes `/etc` writes ephemeral. Disable before applying changes so they survive reboot.

```bash
sudo raspi-config nonint disable_overlayfs
sudo reboot
```

Reconnect after reboot.

### 3. Re-run the installer

The installer is idempotent and switches to label-based mounting:

```bash
cd ~/pi_project
sudo bash install_sd_card_reader.sh
```

It will:
- detect the data SD partition,
- label it `EPAPER_SD` (no-op if already labelled),
- rewrite the mount unit and udev rule keyed on the label,
- reload systemd/udev and start the mount.

### 4. Verify

```bash
systemctl status mnt-epaper_sd.mount --no-pager
mountpoint /mnt/epaper_sd
ls /mnt/epaper_sd/
grep 'What=' /etc/systemd/system/mnt-epaper_sd.mount
```

### 5. Re-enable OverlayFS

```bash
sudo raspi-config nonint enable_overlayfs
sudo reboot
```

Changes persist because OverlayFS was off when the new files were written to the lower (real) root filesystem.
