# T-010: Fresh Pi install guide

Status: Open
Last updated: 2026-03-07

## Problem

There is no single document that guides a user through setting up a brand-new Raspberry Pi for the ePaper frame system. Installation steps are spread across multiple READMEs and install scripts. A new user (or the same user setting up a second Pi) needs a clear, step-by-step runbook.

## Requirements

Create `docs/pi-install-guide.md` covering:

1. **Device naming** — ask the user for a hostname (e.g. `epaper-kitchen`)
2. **Connectivity check** — is the Pi on Wi-Fi or Ethernet?
3. **Hardware check** — is the eInk display connected? Is the USB SD card reader plugged in?
4. **SSH copy** — copy the repo via `scp` (not `git clone`, since the Pi may not have git and credentials shouldn't be on it)
5. **Installation steps** — run each install script in order, with verification commands after each
6. **Monitoring / success checks** — how to verify each service is running

## Proposed Flow

```
1. Flash Raspberry Pi OS Lite → boot → enable SSH
2. ssh pi@<ip>
3. Set hostname:  sudo hostnamectl set-hostname <name>
4. From laptop:   scp -r pi_project/ pi@<ip>:~/pi_project/
5. On Pi:
   a. SD card reader:    sudo bash install_sd_card_reader.sh
   b. eInk display:      cd eInkFrameWithStreamlitMananger && sudo bash setup.sh
   c. S3 sync:           cd pi-s3-sync && sudo bash install.sh
   d. Settings UI:       sudo bash s3_image_croper_ui_app/install_settings.sh
   e. Final hardening:   sudo bash final_hardening.sh
   f. Reboot
6. Verify:
   - systemctl status epaper.service
   - systemctl status settingsapp.service
   - systemctl list-timers sd-s3-sync.timer
   - curl http://localhost/
```

## Acceptance Criteria

- `docs/pi-install-guide.md` exists with full step-by-step instructions
- README.md references the guide
- Guide includes pre-flight checks (hostname, Wi-Fi, hardware)
- Guide includes post-install verification for every service
- Guide uses `scp` for deployment (not `git clone`)
