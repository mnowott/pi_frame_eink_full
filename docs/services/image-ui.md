# Image UI Service (ImageUiApp)

Last updated: 2026-04-30

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

## Systemd Units (EC2)

### `imageuiapp.service` (bound to localhost, behind Caddy)

```ini
# imageuiapp.service
[Service]
User=ec2-user
WorkingDirectory=<repo>/s3_image_croper_ui_app/ImageUiApp
ExecStart=/bin/bash -lc 'poetry run imageuiapp --address 127.0.0.1 --port 8051'
Restart=always
RestartSec=5

# Sandboxing
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictNamespaces=true
LockPersonality=true
RestrictRealtime=true
RestrictSUIDSGID=true
PrivateDevices=true
```

### `caddy.service` (TLS + reverse proxy)

Static Caddy v2 binary at `/usr/local/bin/caddy`, runs as the `caddy` system
user, reads `/etc/caddy/Caddyfile`. The Caddyfile reverse-proxies
`https://${APP_DOMAIN}/` to `127.0.0.1:8051` and obtains a Let's Encrypt
certificate automatically via HTTP-01 (port 80 must be reachable).

## Authentication

Microsoft Entra ID OIDC, validated **inside Streamlit** via its native
`[auth]` block (Streamlit >= 1.42). The previous ALB-based OIDC has been
removed. The app gates every page in `app.py`:

```python
def _require_login() -> None:
    user = getattr(st, "user", None)
    if user is None or getattr(user, "is_logged_in", None) is None:
        return  # Auth not configured; safe for local dev.
    if not user.is_logged_in:
        st.button("Log in with Microsoft", on_click=st.login)
        st.stop()
```

The OIDC client config lives in `/etc/imageuiapp/secrets.toml` (mode 640,
root:ec2-user). The repo working directory contains a symlink at
`s3_image_croper_ui_app/ImageUiApp/.streamlit/secrets.toml` -> that file.
Only `secrets.toml.example` (placeholders) is committed to git.

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

### EC2 (Amazon Linux 2023)

```bash
# Full install: Caddy + Streamlit native OIDC + Entra ID
sudo bash s3_image_croper_ui_app/install_as_aws_linux_caddy.sh
# Creates caddy.service (80/443) and imageuiapp.service (127.0.0.1:8051)
```

### Pi (alongside SettingsApp)

```bash
bash s3_image_croper_ui_app/install_as.sh
# Installs both ImageUiApp and SettingsApp via Poetry
```

### With Caddy + Entra ID (OIDC auth, no ALB)

See `s3_image_croper_ui_app/EC2_DIRECT_AUTH.md` for the full runbook:
DNS A record to Elastic IP, Caddy auto Let's Encrypt, Entra ID App
Registration, Streamlit native `[auth]` block, secrets file layout, and the
big-bang cutover steps from the previous ALB-based setup.

## Debugging

```bash
# EC2
sudo systemctl status imageuiapp.service
journalctl -u imageuiapp.service -f

# Local
cd s3_image_croper_ui_app/ImageUiApp
poetry run imageuiapp --port 8501
```
