# s3_image_croper_ui_app

Two Streamlit web applications for the ePaper photo frame system.

## Apps

| App | Purpose | Runs On |
|-----|---------|---------|
| [ImageUiApp](ImageUiApp/) | Crop images to 800x480, upload to S3 | EC2 / laptop |
| [SettingsApp](SettingsApp/) | Configure display mode, interval, quiet hours | Raspberry Pi |

## Deployment

- **ImageUiApp** runs on EC2 or locally. See [ImageUiApp/README.md](ImageUiApp/README.md).
- **SettingsApp** runs on each Pi as a systemd service on port 80. See [SettingsApp/README.md](SettingsApp/README.md).

## Installation

### ImageUiApp — local laptop (no auth)

```bash
cd ImageUiApp
cp .env.example .env  # fill in AWS credentials
poetry install
poetry run imageuiapp --port 8501
```

Default bind is `127.0.0.1`. Pass `--address 0.0.0.0` to expose on the LAN.

### ImageUiApp — EC2 (Caddy + Streamlit native OIDC against Entra ID)

```bash
sudo bash s3_image_croper_ui_app/install_as_aws_linux_caddy.sh
```

This installs Caddy v2 + Poetry + ImageUiApp and creates two systemd
units:

* `caddy.service` on 80/443 with automatic Let's Encrypt
* `imageuiapp.service` on `127.0.0.1:8051` (sandboxed)

OIDC config goes into `/etc/imageuiapp/secrets.toml` (mode 640,
root:ec2-user). See `EC2_DIRECT_AUTH.md` for the full runbook (DNS,
Entra App Registration, secrets layout, cutover plan, cost analysis).
The matching Terraform module that provisions the EC2 itself lives at
`infrastructure/terraform/imageuiapp/`.

### SettingsApp (Pi)

```bash
cd ..  # repo root
./s3_image_croper_ui_app/install_settings.sh
```

This creates `settingsapp.service` on port 80.

## Shared Configuration

Both apps use `.env` files for AWS configuration:

```
AWS_DEFAULT_REGION=eu-central-1
S3_BUCKET=your-bucket-name

# Required only on the EC2 host running install_as_aws_linux_caddy.sh:
APP_DOMAIN=app.your-domain.example
ADMIN_EMAIL=you@your-domain.example
```

On EC2 the instance IAM role (provisioned by Terraform as
`imageuiapp-ec2`) supplies S3 credentials via IMDS; no
`AWS_ACCESS_KEY_ID` / `SECRET` is needed in `.env`. Local laptops still
use static keys in `.env` or `~/.aws/credentials`.
