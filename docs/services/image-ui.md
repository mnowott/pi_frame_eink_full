# Image UI Service (ImageUiApp)

Last updated: 2026-03-07

## Overview

Streamlit web app for cropping and uploading images to S3. Runs on a laptop, EC2 instance, or Pi. Users upload photos, interactively crop them to 800x480, and save to S3 for distribution to all Pis.

## Source Files

| File | Role |
|------|------|
| `s3_image_croper_ui_app/ImageUiApp/imageuiapp/app.py` | Main Streamlit page: tab layout, internet check |
| `s3_image_croper_ui_app/ImageUiApp/imageuiapp/main.py` | CLI entry point (`poetry run imageuiapp`) |
| `s3_image_croper_ui_app/ImageUiApp/imageuiapp/tabs/info_tab.py` | Renders intro.md (German user guide) |
| `s3_image_croper_ui_app/ImageUiApp/imageuiapp/tabs/file_tab.py` | Image upload, crop UI, S3 upload/delete |
| `s3_image_croper_ui_app/ImageUiApp/imageuiapp/tabs/view_tab.py` | Browse and preview S3 images |
| `s3_image_croper_ui_app/ImageUiApp/imageuiapp/tabs/downloads_tab.py` | Download wifi.json template + batch ZIP from S3 |
| `s3_image_croper_ui_app/ImageUiApp/pyproject.toml` | Dependencies (Streamlit, Pillow, boto3, numpy) |

## Tabs

| Tab | Function |
|-----|----------|
| **Info** | Displays German-language user guide (intro.md) |
| **Manage** | Upload images (PNG/JPG), interactive crop with arrow controls, optional pre-downscale, save to S3, delete from S3 |
| **View** | Browse S3 images, click to preview full size |
| **Downloads** | Download `wifi.json` template for SD card; generate pre-signed ZIP URL of all S3 images (1h expiry) |

## Configuration

Via `.env` file at `ImageUiApp/.env` (or environment variables):

```
S3_BUCKET=your-s3-bucket-name
REGION=eu-central-1
```

Template: `ImageUiApp/.env.example`

AWS credentials come from environment (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) or IAM role on EC2.

## S3 Layout

```
s3://<bucket>/
├── images/          # Cropped photos (uploaded by this app)
│   ├── photo1.png
│   └── photo2.png
└── zips/            # Generated ZIP bundles (auto-created by downloads tab)
    └── images_.zip
```

## Deployment Options

### Local / Laptop

```bash
cd s3_image_croper_ui_app/ImageUiApp
poetry install
poetry run imageuiapp --port 8501
```

### EC2 (Amazon Linux)

```bash
# Full install
sudo bash s3_image_croper_ui_app/install_as_aws_linux.sh
# Creates imageuiapp.service on port 8051
```

### Pi (alongside SettingsApp)

```bash
bash s3_image_croper_ui_app/install_as.sh
# Installs both ImageUiApp and SettingsApp via Poetry
```

### With ALB + Entra ID (OIDC auth)

See `s3_image_croper_ui_app/ELB_AUTH.md` for full setup: ALB listener rules, Entra ID app registration, Route 53 DNS, ACM certificate.

## Debugging

```bash
# EC2
sudo systemctl status imageuiapp.service
journalctl -u imageuiapp.service -f

# Local
cd s3_image_croper_ui_app/ImageUiApp
poetry run imageuiapp --port 8501
```
