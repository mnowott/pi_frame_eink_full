# Fresh Pi Install Guide

Step-by-step instructions for setting up a new Raspberry Pi as an ePaper photo frame.

## Prerequisites

On your **laptop/desktop**:
- The `pi_project` repo cloned locally
- SSH client (`ssh`, `scp`)
- Wi-Fi credentials for the Pi's network

> **What OS are you running?**
>
> | OS | Notes |
> |----|-------|
> | **macOS / native Linux** | `.local` mDNS works out of the box — you can use hostnames like `pi-rostock.local` |
> | **WSL2 (Ubuntu on Windows)** | `.local` mDNS resolution does **not** work for SSH/scp. Use the Pi's **IP address** instead (find it on your router's admin page or via `ping <hostname>.local` — ping may resolve even when SSH can't). |
> | **Windows (PowerShell/CMD)** | `.local` mDNS usually works if Bonjour is installed (comes with iTunes). Otherwise use the IP address. |

On the **Raspberry Pi**:
- Raspberry Pi OS Lite flashed to the internal SD card
- SSH enabled (add empty `ssh` file to boot partition, or enable via `raspi-config`)
- Connected to the network (Ethernet or Wi-Fi configured during OS flash)

## 1. Pre-flight Checks

### What is the device name?

Pick a hostname for this Pi (e.g. `epaper-kitchen`, `epaper-living-room`). You'll set it in step 3.

### Is it on Wi-Fi or Ethernet?

If Wi-Fi: make sure the Pi is connected before proceeding. You can configure Wi-Fi during OS flashing with Raspberry Pi Imager, or via `raspi-config` after first boot.

### Is the eInk display connected?

The Waveshare ePaper HAT should be plugged into the GPIO header. SPI and I2C will be enabled by `setup.sh`.

### Is the USB SD card reader plugged in?

The USB SD card reader with a FAT32-formatted SD card should be plugged into a USB port. The install script will detect it automatically.

## 2. Connect via SSH

```bash
ssh pi@<pi-ip-address>
# Default password: raspberry (change it!)
```

> **WSL2 users:** Use the IP address, not `<hostname>.local`. See [Prerequisites](#prerequisites).

## 3. Set Hostname

```bash
sudo hostnamectl set-hostname <your-device-name>
# Example: sudo hostnamectl set-hostname epaper-kitchen
```

## 4. Copy the Repo (from laptop)

Do NOT use `git clone` (avoids needing git/credentials on the Pi). Use `rsync` to copy — it's resumable, incremental, and skips unnecessary files:

```bash
# From your laptop (recommended):
rsync -avz --exclude '.git' --exclude '__pycache__' --exclude '.mypy_cache' \
  pi_project/ pi@<pi-ip>:~/pi_project/
```

If `rsync` isn't available, `scp` works too (but re-copies everything on retries):
```bash
scp -r pi_project/ pi@<pi-ip>:~/pi_project/
```

> **WSL2 users:** Use the IP address, not `<hostname>.local`. See [Prerequisites](#prerequisites).

Then on the Pi:
```bash
cd ~/pi_project
```

## 5. Install Components

Run each step in order. After each, check the verification command before proceeding.

### 5a. SD Card Reader Mount

```bash
sudo bash install_sd_card_reader.sh
```

**Verify:**
```bash
systemctl status mnt-epaper_sd.mount
mountpoint /mnt/epaper_sd && echo "OK: SD mounted"
ls /mnt/epaper_sd/
```

### 5b. eInk Display Service

```bash
cd eInkFrameWithStreamlitMananger
sudo bash setup.sh
# Script will ask to reboot — say YES
```

After reboot, reconnect via SSH and verify:
```bash
sudo systemctl status epaper.service
journalctl -u epaper.service -n 20 --no-pager
```

You should see `sd_monitor` running and checking for images.

### 5c. S3 Sync Service

```bash
cd ~/pi_project/pi-s3-sync
sudo bash install.sh
```

**Verify:**
```bash
sudo systemctl list-timers sd-s3-sync.timer
sudo systemctl status sd-s3-sync.timer
```

The timer should be active and scheduled. The first sync will run 2 minutes after boot.

**Note:** You need a `wifi.json` on the SD card with AWS credentials and (optionally) Wi-Fi config. See `pi-s3-sync/README.md`.

### 5d. Settings UI (Web App)

```bash
cd ~/pi_project
sudo bash s3_image_croper_ui_app/install_settings.sh
```

**Verify:**
```bash
sudo systemctl status settingsapp.service
curl -s -o /dev/null -w "%{http_code}" http://localhost/
# Should print: 200
```

Open `http://<pi-ip>/` in a browser — you should see the settings page.

### 5e. Final Hardening (LAST STEP)

**Important:** Only run this after ALL other steps are verified working. OverlayFS makes the root filesystem read-only — changes won't persist after reboot.

```bash
cd ~/pi_project
sudo bash final_hardening.sh
sudo reboot
```

## 6. Post-Install Verification

After the final reboot, SSH back in and run all checks:

```bash
# eInk display service
sudo systemctl status epaper.service

# Settings web UI
sudo systemctl status settingsapp.service
curl -s -o /dev/null -w "%{http_code}" http://localhost/

# S3 sync timer
sudo systemctl list-timers sd-s3-sync.timer

# SD card mount
mountpoint /mnt/epaper_sd && echo "SD: OK" || echo "SD: NOT MOUNTED"

# Firewall
sudo ufw status

# Watchdog
sudo systemctl status watchdog.service

# OverlayFS
mount | grep overlay
```

All services should be `active (running)` or `active (waiting)`.

## Troubleshooting

### Service won't start

```bash
# Check logs for a specific service
journalctl -u <service-name> -n 50 --no-pager

# Restart a service
sudo systemctl restart <service-name>
```

### Need to make changes after hardening

OverlayFS makes root read-only. To make persistent changes:

```bash
sudo raspi-config nonint disable_overlayfs
sudo reboot
# ... make changes ...
sudo raspi-config nonint enable_overlayfs
sudo reboot
```

### SSH key setup (recommended)

From your laptop, copy your SSH key to the Pi:

```bash
ssh-copy-id pi@<pi-ip>
```

Then verify key login works:
```bash
ssh pi@<pi-ip>
```

After confirming, disable password auth on the Pi:
```bash
echo "PasswordAuthentication no" | sudo tee -a /etc/ssh/sshd_config.d/99-epaper.conf
sudo systemctl reload sshd
```

### Poetry install fails with "All attempts to connect to pypi.org failed"

On Pi Zero 2W, Poetry's HTTP client tries IPv6 addresses first. If the Pi lacks IPv6 connectivity, every request hangs until timeout — even though IPv4 works fine. The install script handles this automatically by temporarily disabling IPv6 during Poetry install.

If running manually, disable IPv6 first:
```bash
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1
# ... run poetry install ...
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=0
sudo sysctl -w net.ipv6.conf.default.disable_ipv6=0
```

### Poetry install fails with "Permission denied" on cache

If `poetry lock` ran as root (via `sudo bash install_settings.sh`), the cache at `~/.cache/pypoetry/` is owned by root. Fix with:
```bash
sudo chown -R pi:pi ~/.cache/pypoetry
```
The install script handles this automatically.

### SD card not detected

```bash
lsblk -f    # Check if the USB reader shows up
sudo systemctl restart mnt-epaper_sd.mount
```

If no `/dev/sdX` appears, try a different USB port or card reader.

## Moving an OS SD Card to Another Pi

The OS SD card (the card the Pi boots from) can be moved to another identical Raspberry Pi, but certain configuration is tied to the original hardware. This section documents what breaks and how to fix it locally via SSH or keyboard/screen.

### Pre-requisites

- SSH access to the Pi, **or** a keyboard + HDMI/screen connected directly
- If OverlayFS is enabled (it is after `final_hardening.sh`), you must disable it first — all changes to the root filesystem are lost on reboot otherwise
- DO NOT FORGET TO ENABLE THE OVERLAY AGAIN AFTER (Step 4)

### Step 0: Disable OverlayFS (if enabled)

```bash
# Check if OverlayFS is active
mount | grep overlay

# If yes, disable it and reboot
sudo raspi-config nonint disable_overlayfs
sudo reboot
```

After reboot, reconnect. The root filesystem is now writable.

### Step 1: Fix the data SD card mount (most common issue)

**Cause:** The systemd mount unit and udev rule reference the old data SD card by UUID. Every physical SD card has a unique UUID, so a different data SD card won't mount — even if it's the same model and size.

**Diagnosis:**
```bash
# Check if the mount unit is failing
sudo systemctl status mnt-epaper_sd.mount

# See what UUID it expects
grep 'What=' /etc/systemd/system/mnt-epaper_sd.mount
# Output: What=/dev/disk/by-uuid/XXXX-XXXX   <-- old UUID

# See what UUID the current data SD card actually has
lsblk -f /dev/sd?*
# Look for the vfat partition — its UUID will be different
```

**Fix — Option A: Re-label and switch to label-based mount (recommended)**

This makes the mount hardware-agnostic going forward. Any SD card labelled `EPAPER_SD` will auto-mount. The script auto-detects the SD card partition — just copy-paste the whole block:

```bash
# Auto-detect the data SD card, re-label it, and switch to label-based mounting.
# Copy-paste this entire block — no manual edits needed.
set -e
SD_LABEL="EPAPER_SD"
MY_UID=$(id -u)
MY_GID=$(id -g)

# Find the first non-boot vfat partition on /dev/sdX
DEV=""
for d in $(lsblk -prno NAME,FSTYPE /dev/sd?* 2>/dev/null | awk '$2=="vfat"{print $1}'); do
  LABEL=$(blkid -s LABEL -o value "$d" 2>/dev/null || true)
  [[ "$LABEL" == "boot" || "$LABEL" == "bootfs" ]] && continue
  DEV="$d"; break
done

if [ -z "$DEV" ]; then
  echo "ERROR: No suitable vfat partition found on /dev/sdX."
  echo "Run 'lsblk -f' and check which device is your data SD card."
  exit 1
fi
echo "Detected data SD partition: $DEV"

# Unmount if mounted, install fatlabel if missing, label the partition
sudo umount "$DEV" 2>/dev/null || true
command -v fatlabel >/dev/null || sudo apt-get install -y dosfstools
sudo fatlabel "$DEV" "$SD_LABEL"
echo "Labelled $DEV as $SD_LABEL"

# Write label-based systemd mount unit
sudo tee /etc/systemd/system/mnt-epaper_sd.mount > /dev/null <<EOF
[Unit]
Description=ePaper SD card mount
DefaultDependencies=no
After=local-fs-pre.target
Before=local-fs.target
Conflicts=umount.target

[Mount]
What=/dev/disk/by-label/$SD_LABEL
Where=/mnt/epaper_sd
Type=vfat
Options=defaults,uid=$MY_UID,gid=$MY_GID,umask=0022,nofail,nosuid,noexec,nodev

[Install]
WantedBy=multi-user.target
EOF

# Write label-based udev rule
sudo tee /etc/udev/rules.d/99-epaper-sd-mount.rules > /dev/null <<EOF
ACTION=="add", SUBSYSTEM=="block", ENV{ID_FS_LABEL}=="$SD_LABEL", ENV{SYSTEMD_WANTS}="mnt-epaper_sd.mount"
EOF

# Reload and test
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
sudo systemctl restart mnt-epaper_sd.mount
mountpoint /mnt/epaper_sd && echo "OK: mounted at /mnt/epaper_sd" || echo "FAIL: not mounted"
```

**Fix — Option B: Update UUID only (quick, but still hardware-specific)**

This also auto-detects the partition — no need to know the device name:

```bash
# Auto-detect the data SD card and update the mount unit/udev rule with its UUID.
set -e
DEV=""
for d in $(lsblk -prno NAME,FSTYPE /dev/sd?* 2>/dev/null | awk '$2=="vfat"{print $1}'); do
  LABEL=$(blkid -s LABEL -o value "$d" 2>/dev/null || true)
  [[ "$LABEL" == "boot" || "$LABEL" == "bootfs" ]] && continue
  DEV="$d"; break
done
[ -z "$DEV" ] && echo "ERROR: No data SD card found. Run 'lsblk -f' to check." && exit 1

NEW_UUID=$(sudo blkid -s UUID -o value "$DEV")
echo "Detected $DEV with UUID: $NEW_UUID"

# Replace UUID in mount unit and udev rule
sudo sed -i "s|What=/dev/disk/by-uuid/.*|What=/dev/disk/by-uuid/$NEW_UUID|" \
  /etc/systemd/system/mnt-epaper_sd.mount
sudo sed -i "s|ID_FS_UUID==\"[^\"]*\"|ID_FS_UUID==\"$NEW_UUID\"|" \
  /etc/udev/rules.d/99-epaper-sd-mount.rules

# Reload and test
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
sudo systemctl restart mnt-epaper_sd.mount
mountpoint /mnt/epaper_sd && echo "OK: mounted" || echo "FAIL: not mounted"
```

### Step 2: Fix username mismatches (if applicable)

If the new Pi has a different username than the one used during install (e.g. the original was `pi` but the new Pi uses `admin`), services will fail with "User does not exist".

**Diagnosis:**
```bash
# Check which user the services expect
grep '^User=' /etc/systemd/system/epaper.service
grep '^User=' /etc/systemd/system/sd-s3-sync.service
grep '^User=' /etc/systemd/system/settingsapp.service
```

**Fix:**
```bash
# Replace the old username with the current one in all service files
OLD_USER="pi"          # <-- the user from the original Pi
NEW_USER="$(whoami)"   # <-- the current user

sudo sed -i "s/User=$OLD_USER/User=$NEW_USER/g; s/Group=$OLD_USER/Group=$NEW_USER/g" \
  /etc/systemd/system/epaper.service \
  /etc/systemd/system/sd-s3-sync.service \
  /etc/systemd/system/settingsapp.service

# Also fix home directory paths in the service files
OLD_HOME="/home/$OLD_USER"
NEW_HOME="/home/$NEW_USER"

sudo sed -i "s|$OLD_HOME|$NEW_HOME|g" \
  /etc/systemd/system/epaper.service \
  /etc/systemd/system/settingsapp.service

sudo systemctl daemon-reload
sudo systemctl restart epaper.service settingsapp.service
```

### Step 3: Set the hostname

```bash
sudo hostnamectl set-hostname <your-new-device-name>
```

The ePaper status screen shows `http://<hostname>/` — this updates it on next display refresh.

### Step 4: Re-enable OverlayFS

After confirming everything works:

```bash
# Verify all services
sudo systemctl status epaper.service settingsapp.service
sudo systemctl list-timers sd-s3-sync.timer
mountpoint /mnt/epaper_sd && echo "SD: OK"

# Re-enable read-only root
sudo raspi-config nonint enable_overlayfs
sudo reboot
```
