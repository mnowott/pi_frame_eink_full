# S3 Sync Service

Last updated: 2026-03-07

## Overview

Periodically syncs images from an S3 bucket to the local SD card. Optionally manages Wi-Fi connection via NetworkManager before syncing.

## Source Files

| File | Role |
|------|------|
| `pi-s3-sync/scripts/sync_s3_from_sd.py` | Main sync logic: find config, connect Wi-Fi, run `aws s3 sync` |
| `pi-s3-sync/systemd/sd-s3-sync.service` | Systemd oneshot service unit |
| `pi-s3-sync/systemd/sd-s3-sync.timer` | Systemd timer (every 15 min) |
| `pi-s3-sync/install.sh` | Installer: awscli, NetworkManager, polkit, systemd units |

## Systemd Units

```ini
# sd-s3-sync.timer
[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true
Unit=sd-s3-sync.service
```

```ini
# sd-s3-sync.service
[Unit]
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=pi
ExecStart=/usr/local/bin/sync_s3_from_sd.py
Environment="AWS_KEY_ID=..."
Environment="AWS_SECRET_ACCESS_KEY=..."
Environment="REGION=eu-central-1"
Environment="S3_BUCKET=your-s3-bucket-name"
```

## Sync Logic

1. **Find config:** Scans `/proc/mounts` for any filesystem containing `wifi.json` at root. Falls back to home directory.
2. **Load credentials:** From `wifi.json` keys (`aws_access_key_id`, `aws_secret_access_key`, `s3_bucket`, `aws_region`), falling back to environment variables.
3. **Connect Wi-Fi (optional):** If `wifi_name` + `wifi_password` in config, uses `nmcli` to check/establish connection.
4. **Sync:** `aws s3 sync s3://<bucket> <base_path>/s3_folder --only-show-errors --delete --exclude *.zip`

The `--delete` flag propagates deletions from S3 to local. The `--exclude *.zip` skips pre-signed download bundles.

## Configuration: wifi.json

Located on SD card root or in home directory. Gitignored.

```json
{
  "aws_access_key_id": "AKIA...",
  "aws_secret_access_key": "...",
  "s3_bucket": "your-s3-bucket-name",
  "aws_region": "eu-central-1",
  "wifi_name": "MySSID",
  "wifi_password": "MyPassword"
}
```

The script accepts many key name variants for flexibility (e.g., `aws_access_key_id`, `access_key_id`, `aws_key_id`).

## Installation

```bash
cd pi-s3-sync
sudo bash install.sh
```

Installs: awscli, python3, git, network-manager. Creates polkit rule for nmcli access. Copies sync script to `/usr/local/bin/`. Enables timer.

## Debugging

```bash
sudo systemctl status sd-s3-sync.timer
sudo systemctl list-timers sd-s3-sync.timer
journalctl -u sd-s3-sync.service -f

# Manual run
sudo /usr/local/bin/sync_s3_from_sd.py
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Config file not found |
| 2 | Config load failed |
| 3 | Target folder creation failed |
