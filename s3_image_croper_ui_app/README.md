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

### ImageUiApp (EC2/laptop)

```bash
cd ImageUiApp
cp .env.example .env  # fill in AWS credentials
poetry install
poetry run imageuiapp --port 8501
```

### SettingsApp (Pi)

```bash
cd ..  # repo root
./s3_image_croper_ui_app/install_settings.sh
```

This creates `settingsapp.service` on port 80.

## Shared Configuration

Both apps use `.env` files for AWS credentials:

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=eu-central-1
S3_BUCKET=your-bucket-name
```
