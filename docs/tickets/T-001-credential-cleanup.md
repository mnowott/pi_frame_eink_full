# T-001: Remove hardcoded credentials, migrate to .env pattern

Status: Closed
Last updated: 2026-03-07

## Problem

AWS credentials and Wi-Fi passwords are hardcoded in multiple scripts and tracked in git. This is a security risk — anyone with repo access has full AWS credentials.

## Affected Files

| File | Contains |
|------|----------|
| `install_env.sh` | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY in plaintext |
| `s3_image_croper_ui_app/install_env.sh` | Same credentials |
| `pi-s3-sync/systemd/sd-s3-sync.service` | Credentials in `Environment=` directives |
| `eInkFrameWithStreamlitMananger/.env` | AWS credentials (tracked in git) |
| `s3_image_croper_ui_app/ImageUiApp/.env` | AWS credentials (tracked in git) |
| `pi-s3-sync/wifi.json` | AWS credentials + Wi-Fi password (already gitignored) |

## Plan

1. Create a root `.env.example` with placeholder values for all required vars
2. Modify `install_env.sh` to read from `.env` file instead of hardcoding values, or prompt interactively
3. Modify `pi-s3-sync/systemd/sd-s3-sync.service` template to use `EnvironmentFile=` pointing to `.env`
4. Ensure all `.env` files are gitignored (see [T-002](T-002-gitignore-cleanup.md))
5. Remove credentials from git history (done — history truncated via orphan branch)
6. Revoke and rotate the previously exposed AWS access keys

## Acceptance Criteria

- No AWS credentials or passwords in any tracked file
- All credential sources use `.env` files or `wifi.json` (both gitignored)
- Systemd services use `EnvironmentFile=` instead of inline `Environment=`
- `.env.example` templates exist for all modules that need credentials
