# System Overview

Last updated: 2026-04-30

## What This System Does

Family photo frame system. Users crop images in a web app, images sync to AWS S3, Raspberry Pis pull from S3 to local SD cards, and a Waveshare 7-color ePaper display rotates through the images. Each Pi runs a local web settings UI for configuration without SSH.

## Component Map

```
┌──────────────────────────────────────────────────────────────────┐
│ EXTERNAL (EC2 / Laptop)                                          │
│                                                                  │
│  ImageUiApp (Streamlit)                                          │
│  - Upload images                                                 │
│  - Crop to 800x480                                               │
│  - Push to S3                                                    │
└──────────────┬───────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────┐
│ AWS S3  (your-s3-bucket-name, eu-central-1)                        │
│  /images/*   — cropped photos                                    │
│  /zips/*     — pre-signed download bundles                       │
└──────────────┬───────────────────────────────────────────────────┘
               │  aws s3 sync --delete (every 15 min)
               ▼
┌──────────────────────────────────────────────────────────────────┐
│ RASPBERRY PI                                                     │
│                                                                  │
│  ┌─────────────────────┐    ┌──────────────────────────────┐    │
│  │ pi-s3-sync          │    │ SettingsApp (Streamlit :80)  │    │
│  │ systemd timer       │    │ systemd service              │    │
│  │ - wifi management   │    │ - edit settings.json on SD   │    │
│  │ - S3 → SD sync      │    │ - write refresh_time.txt     │    │
│  └────────┬────────────┘    └──────────────────────────────┘    │
│           │                                                      │
│           ▼                                                      │
│  /mnt/epaper_sd/                                                 │
│  ├── s3_folder/          (synced from S3)                        │
│  ├── local images        (user-provided on SD)                   │
│  ├── epaper_settings/                                            │
│  │   └── settings.json                                           │
│  ├── _epaper_pic/        (processed image cache)                 │
│  └── refresh_time.txt    (legacy interval override)              │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ eInkFrame (systemd service)                              │    │
│  │                                                          │    │
│  │  sd_monitor.py  — watches SD, enforces quiet hours       │    │
│  │       │                                                  │    │
│  │       ▼                                                  │    │
│  │  frame_manager.py — selects source, runs pipeline        │    │
│  │       │                                                  │    │
│  │       ├─► image_converter.py — resize/crop/enhance       │    │
│  │       │       → writes to _epaper_pic/                   │    │
│  │       │                                                  │    │
│  │       └─► display_manager.py — rotate images on ePaper   │    │
│  │               │                                          │    │
│  │               ├─► pollock_text.py (status cards)         │    │
│  │               └─► waveshare drivers (SPI/GPIO)           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                        │                                         │
│                        ▼                                         │
│              Waveshare 7.3" 7-color ePaper (800x480)             │
└──────────────────────────────────────────────────────────────────┘
```

## Repository Structure

```
pi_project/
├── install_all_pi.sh              # Master Pi installer (orchestrates steps 1-5)
├── install_env.sh                 # Step 1: AWS env vars → ~/.bashrc
├── install_sd_card_reader.sh      # Step 2: systemd mount + udev for SD
├── final_hardening.sh             # Step 6: watchdog + overlayfs (run last, separate)
│
├── eInkFrameWithStreamlitMananger/  # ePaper display stack
│   ├── sd_monitor.py              # Entry point (systemd runs this)
│   ├── frame_manager.py           # Image pipeline orchestrator
│   ├── display_manager.py         # ePaper hardware control
│   ├── image_converter.py         # Image resize/crop/enhance
│   ├── pollock_text.py            # Status card generator
│   ├── setup.sh                   # Step 5: SPI/I2C + epaper.service
│   ├── lib/waveshare_epd/         # Waveshare hardware drivers
│   ├── messages/                  # Fallback display images
│   └── tests/                     # S3Manager tests (pytest + moto)
│
├── pi-s3-sync/                    # S3-to-SD sync service
│   ├── scripts/sync_s3_from_sd.py # Sync logic + wifi management
│   ├── install.sh                 # Step 3: awscli + systemd timer
│   └── systemd/                   # Service + timer unit files
│
├── s3_image_croper_ui_app/        # Web UIs
│   ├── ImageUiApp/                # Image cropper + S3 upload (Streamlit)
│   ├── SettingsApp/               # Pi settings editor (Streamlit)
│   ├── install_as.sh              # Install on Pi
│   ├── install_as_aws_linux_caddy.sh  # Install on EC2 (Caddy + Streamlit native OIDC)
│   ├── install_settings.sh        # Step 4: SettingsApp systemd service
│   └── EC2_DIRECT_AUTH.md         # Caddy + Entra ID OIDC runbook (no ALB)
│
├── infrastructure/                # IaC for the EC2 host
│   ├── terraform/imageuiapp/      # EC2 + IAM + EIP + S3 import
│   └── cloudformation/admin-role/ # Bootstrap admin user + role
│
├── scripts/                       # Helpers (AWS assume-role, S3 backup, Claude skill)
│
└── docs/                          # Project documentation
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ (apps), Python 3.13+ (display stack) |
| Package manager | Poetry (all modules) |
| Web framework | Streamlit 1.52-2.0 (ImageUiApp, SettingsApp) |
| Image processing | Pillow 12.x |
| Cloud SDK | boto3 1.35-1.42, awscli |
| Display hardware | Waveshare ePaper drivers (SPI via spidev, GPIO via gpiozero) |
| OS services | systemd (services, timers, mount units), udev rules |
| Networking | NetworkManager / nmcli (Wi-Fi on Pi) |
| Cloud | AWS S3, EC2, Route 53, Entra ID OIDC (validated in-app via Streamlit native auth) |
| Edge / TLS | Caddy v2 on EC2 (auto Let's Encrypt; no ALB, no ACM) |
| IaC | Terraform (provider AWS ~>5.0); CloudFormation for the bootstrap admin role |
| Testing | pytest 8.0, moto 5.1 (mocked S3) |
