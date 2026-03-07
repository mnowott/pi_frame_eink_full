# ImageUiApp

Streamlit web app for cropping images to 800x480 and uploading them to S3 for display on ePaper frames.

## Features

- **File tab**: Upload images, interactively crop to 800x480, save to S3
- **View tab**: Browse and preview images already in S3
- **Downloads tab**: Download all S3 images as a ZIP, download `wifi.json` template
- **Info tab**: Usage instructions (German)

## Prerequisites

- Python 3.11+
- Poetry
- AWS S3 bucket with write access

## Setup

```bash
cp .env.example .env   # fill in your credentials
poetry install
```

## Running

```bash
poetry run imageuiapp --port 8501 --address 0.0.0.0
```

Or directly:

```bash
poetry run streamlit run imageuiapp/app.py
```

## Configuration

`.env` file (not committed):

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=eu-central-1
S3_BUCKET=your-bucket-name
```

## Cropping Behavior

1. Upload PNG/JPG images via the sidebar
2. Optional pre-downscale (preserves aspect ratio, never below 800x480)
3. Move crop window with directional buttons or center
4. Save crops as PNG to S3 under the `images/` prefix

## Testing

```bash
poetry run pytest -q --tb=short
```
