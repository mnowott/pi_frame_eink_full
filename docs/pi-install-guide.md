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

### SD card not detected

```bash
lsblk -f    # Check if the USB reader shows up
sudo systemctl restart mnt-epaper_sd.mount
```

If no `/dev/sdX` appears, try a different USB port or card reader.
