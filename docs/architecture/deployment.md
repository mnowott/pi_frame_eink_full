# Deployment

Last updated: 2026-03-07

## Target Hardware

| Target | Role | OS |
|--------|------|----|
| Raspberry Pi Zero W / Zero 2W / 3 / 4 | Display + sync + settings UI | Raspberry Pi OS (Debian) |
| Waveshare 7.3" 7-color ePaper (EPD7in3F) | Primary display panel | — |
| Waveshare 7.3" E-ink (EPD7in3E) | Alternative display | — |
| Waveshare 5.65" (EPD5in65F) | Alternative display | — |
| USB SD card reader | Removable config + image storage | — |
| AWS EC2 (Amazon Linux 2/2023) | ImageUiApp hosting (optional) | Amazon Linux |

**Hardware interfaces required:** SPI (display data), I2C (display control), GPIO (display pins)

## Cloud Services

| Service | Purpose |
|---------|---------|
| S3 (`rasp-pi-family-s3`, `eu-central-1`) | Image storage and distribution |
| EC2 | Optional: host ImageUiApp for remote access |
| ALB + Entra ID OIDC | Optional: authenticated access to ImageUiApp |
| Route 53 | Optional: DNS for `app.nowottnm.de` |
| ACM | Optional: TLS certificate for `*.nowottnm.de` |

## Pi Installation Order

`install_all_pi.sh` runs steps 1-4 automatically. Steps 5-6 are manual.

| Step | Script | What It Does | Reboot? |
|------|--------|-------------|---------|
| 1 | `install_env.sh` | Exports AWS env vars to `~/.bashrc` | No |
| 2 | `install_sd_card_reader.sh` | Creates systemd mount unit + udev rule for SD at `/mnt/epaper_sd` | No |
| 3 | `pi-s3-sync/install.sh` | Installs awscli, NetworkManager, polkit rule; creates `sd-s3-sync.timer` (15 min) | No |
| 4 | `s3_image_croper_ui_app/install_settings.sh` | Installs Poetry + SettingsApp; creates `settingsapp.service` on port 80 | No |
| 5 | `eInkFrameWithStreamlitMananger/setup.sh` | **Manual run required.** Enables SPI/I2C, installs display deps, creates `epaper.service` | **Yes** |
| 6 | `final_hardening.sh` | **Must be last. Run separately.** Enables watchdog, volatile journald, OverlayFS read-only root | **Yes (irreversible without re-flash)** |

### Why Step 5 Is Manual

The eInk setup script enables SPI/I2C hardware interfaces and prompts for reboot. It's commented out in `install_all_pi.sh` to ensure the user verifies steps 1-4 succeeded before proceeding.

### Why Step 6 Is Separate

`final_hardening.sh` enables OverlayFS, which makes the root filesystem read-only. After this:
- Package installs and config changes are lost on reboot
- To make persistent changes: disable OverlayFS via `sudo raspi-config nonint disable_overlayfs`, reboot, make changes, re-enable, reboot
- The SD card at `/mnt/epaper_sd` remains writable (it's a separate mount)

## EC2 Installation (ImageUiApp)

| Script | Target OS | What It Creates |
|--------|-----------|----------------|
| `s3_image_croper_ui_app/install_as_aws_linux.sh` | Amazon Linux | Poetry env + `imageuiapp.service` on port 8051 |
| `s3_image_croper_ui_app/install_as.sh` | Raspberry Pi | Poetry env for both ImageUiApp + SettingsApp (no systemd) |

Optional: configure ALB + Entra ID OIDC per `s3_image_croper_ui_app/ELB_AUTH.md`.

## Systemd Services (Pi)

| Service | Type | User | Trigger | Depends On |
|---------|------|------|---------|------------|
| `mnt-epaper_sd.mount` | mount | root | Boot + udev hotplug | — |
| `sd-s3-sync.timer` | timer | — | Boot (2 min delay) + every 15 min | network-online.target |
| `sd-s3-sync.service` | oneshot | pi | Timer only | network-online.target |
| `epaper.service` | simple | current user | Boot | network.target, mnt-epaper_sd.mount |
| `settingsapp.service` | simple | current user | Boot | network.target |
| `watchdog.service` | (system) | root | Boot | (hardening only) |

## Network Requirements

- **Wi-Fi:** Managed by NetworkManager/nmcli. Credentials in `wifi.json` on SD card.
- **Internet:** Required for S3 sync. Display works offline with cached images.
- **Port 80:** SettingsApp binds to port 80 (via `CAP_NET_BIND_SERVICE`).
- **Port 8051:** ImageUiApp on EC2 (behind ALB if using OIDC auth).
