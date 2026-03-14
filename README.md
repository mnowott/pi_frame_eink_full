```
    ┌─────────────────────────────────┐
    │  ┌───────────────────────────┐  │
    │  │                           │  │
    │  │    ePaper Family Frame    │  │
    │  │                           │  │
    │  │   ┌───┐  ┌───┐  ┌───┐     │  │
    │  │   │:=)│  │:=)│  │:=)│     │  │
    │  │   └───┘  └───┘  └───┘     │  │
    │  │                           │  │
    │  └───────────────────────────┘  │
    │          ▓▓▓▓▓▓▓▓▓▓▓            │
    └─────────────────────────────────┘
```

# ePaper Family Frame

A complete system for turning a **Raspberry Pi** and a **Waveshare 7-color ePaper display** into a beautiful family photo frame — with cloud sync, a web cropping tool, and a settings UI.

Upload photos from any browser, crop them to fit, sync between frames via S3, and watch them rotate on the display. No terminal needed after setup.

> Built on top of [eInkFrame](https://github.com/EnriqueNeyra/eInkFrame) by Enrique Neyra, which provided the original display driver concept and Waveshare ePaper integration. This project extends the original with cloud sync, web management UIs, automated installation, and production hardening.

## Features

- **Web image cropper** — upload photos, interactively crop to 800x480, save to S3
- **Automatic sync** — S3 images sync to the Pi every 15 minutes via systemd timer
- **Smart display** — quiet hours, configurable rotation interval, multiple picture modes
- **Web settings UI** — change settings from any browser on the local network
- **Hardened** — firewall, systemd sandboxing, read-only root filesystem (OverlayFS)
- **SD-card config** — swap frames between Pis by moving the SD card

## Architecture

```
Browser                              Raspberry Pi
  │                                    │
  ├─► ImageUiApp (Streamlit)           │
  │     crop to 800x480 → S3           │
  │                                    │
  ▼                                    ▼
S3 Bucket  ──── every 15 min ────►  /mnt/epaper_sd/s3_folder/
                                       │
                                       ├─► sd_monitor.py
                                       │     watches SD, enforces quiet hours
                                       │     └─► frame_manager.py
                                       │           └─► display_manager.py → ePaper
                                       │
                                       └─► SettingsApp (Streamlit, port 80)
                                             http://<pi-hostname>/
```

## Hardware

| Component | Details |
|-----------|---------|
| **Pi** | Zero W, Zero 2W, Pi 3, or Pi 4 |
| **Display** | Waveshare 7.3" 7-color ePaper (800x480) — `epd7in3f` primary, also supports `epd7in3e`, `epd5in65f` |
| **SD card reader** | USB card reader with FAT32-formatted SD card |
| **Cloud** | AWS S3 bucket (see below) |

## AWS Setup

You need an S3 bucket and an IAM user with access to it.

1. **Create an S3 bucket** (e.g. `my-epaper-photos`) in your preferred region
2. **Create an IAM user** with programmatic access (access key + secret key)
3. **Attach a policy** granting the user S3 access to your bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::my-epaper-photos",
        "arn:aws:s3:::my-epaper-photos/*"
      ]
    }
  ]
}
```

4. **Store the credentials** — you'll need them in two places:
   - **Pi:** in `.env` (used by `install_env.sh`) or directly in `wifi.json` on the SD card
   - **ImageUiApp:** in `s3_image_croper_ui_app/ImageUiApp/.env`

## Modules

| Module | Path | What it does |
|--------|------|-------------|
| **eInkFrame** | `eInkFrameWithStreamlitMananger/` | Display driver — monitors SD, processes images, drives ePaper via SPI |
| **pi-s3-sync** | `pi-s3-sync/` | Syncs S3 bucket to SD card, manages Wi-Fi via NetworkManager |
| **ImageUiApp** | `s3_image_croper_ui_app/ImageUiApp/` | Web app for cropping and uploading images to S3 |
| **SettingsApp** | `s3_image_croper_ui_app/SettingsApp/` | Web settings UI running on each Pi |

All modules use **Poetry** for dependency management and have lint, typecheck (mypy), format (ruff), and test (pytest) targets via `make check`.

## Quick Start

### 1. Set up the ImageUiApp (on your laptop or EC2)

```bash
cd s3_image_croper_ui_app/ImageUiApp
cp .env.example .env   # fill in your S3 bucket and region
poetry install
poetry run imageuiapp --port 8501
```

Open `http://localhost:8501`, upload photos, crop them, and save to S3.

### 2. Set up a Raspberry Pi

See the full step-by-step guide: **[docs/pi-install-guide.md](docs/pi-install-guide.md)**

Short version:

```bash
# From your laptop — copy the repo to the Pi
scp -r pi_project/ pi@<pi-ip>:~/pi_project/

# On the Pi — run install scripts in order
sudo bash install_sd_card_reader.sh
cd eInkFrameWithStreamlitMananger && sudo bash setup.sh  # reboot after
cd ~/pi_project/pi-s3-sync && sudo bash install.sh
sudo bash ~/pi_project/s3_image_croper_ui_app/install_settings.sh
sudo bash ~/pi_project/final_hardening.sh  # last step, enables read-only root
sudo reboot
```

### 3. Prepare the SD card

Create a `wifi.json` on the SD card root (see `wifi.json.example` in `pi-s3-sync/`):

```json
{
  "aws_access_key_id": "AKIA...",
  "aws_secret_access_key": "...",
  "s3_bucket": "your-bucket-name",
  "aws_region": "eu-central-1",
  "wifi_name": "YourSSID",
  "wifi_password": "YourPassword"
}
```

Insert the SD card → the Pi syncs images and starts displaying them.

## Settings

Access the settings UI at `http://<pi-ip>/` from any browser on the same network.

| Setting | Default | Description |
|---------|---------|-------------|
| Picture mode | `both` | `local` (SD only), `online` (S3 only), or `both` |
| Change interval | 15 min | How often the display rotates to a new image |
| Quiet hours | off | Stop rotation between evening and morning times |
| S3 folder | `s3_folder` | Subfolder name for synced images |

Settings are stored in `settings.json` on the SD card at `/mnt/epaper_sd/epaper_settings/`.

## Development

```bash
# Run all checks (lint, typecheck, format, test)
make check

# Auto-format all code
make format

# Run tests with coverage
make coverage

# Run checks for a single module
cd eInkFrameWithStreamlitMananger && make check
```

## Documentation

Full docs live in [`docs/`](docs/index.md):

- [Pi Install Guide](docs/pi-install-guide.md) — step-by-step setup for a new Pi
- [Monitoring Guide](docs/pi-monitoring-guide.md) — health checks, debugging, maintenance
- [Architecture](docs/architecture/index.md) — system overview, data flow, deployment
- [Services](docs/services/index.md) — systemd units, config, per-service docs
- [Hardening Summary](docs/architecture/hardening-summary.md) — security measures applied

## Security

- **No secrets in git.** Credentials live in `.env` files (gitignored) or `wifi.json` on the SD card.
- **Firewall** (ufw) — SSH rate-limited, port 80 LAN-only, all other incoming denied.
- **Systemd sandboxing** — all services run with `ProtectSystem=strict`, `PrivateTmp`, restricted namespaces.
- **Read-only root** — OverlayFS prevents persistent changes (protects against SD card wear and tampering).
- **SSH hardened** — root login disabled, MaxAuthTries=3 (password auth disabled after key setup).

## Credits

The display driver code and original concept for using Waveshare ePaper panels as photo frames is based on [eInkFrame](https://github.com/EnriqueNeyra/eInkFrame) by Enrique Neyra. This project extends the original with cloud sync, web management UIs, automated installation, and production hardening.

The Waveshare ePaper drivers in `eInkFrameWithStreamlitMananger/lib/waveshare_epd/` are vendor-provided by [Waveshare](https://www.waveshare.com/).

## License

This project is licensed under the [MIT License](LICENSE).
