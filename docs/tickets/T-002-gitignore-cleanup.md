# T-002: Add root .gitignore, remove tracked secrets

Status: Closed
Last updated: 2026-03-07

## Problem

No root `.gitignore` exists. Multiple secret files are tracked in git:
- `.env` files with real AWS credentials
- `.pem` SSH private key files
- `.pytest_cache` directories

## Affected Files

| File | Issue |
|------|-------|
| `eInkFrameWithStreamlitMananger/.env` | Tracked, contains AWS credentials |
| `s3_image_croper_ui_app/ImageUiApp/.env` | Tracked, contains AWS credentials |
| `s3_image_croper_ui_app/ec2.pem` | Tracked SSH private key |
| `s3_image_croper_ui_app/ec-pi-streamlit.pem` | Tracked SSH private key |
| `eInkFrameWithStreamlitMananger/.pytest_cache/` | Tracked cache directory |

## Plan

1. Create root `.gitignore`:
   ```
   .env
   *.pem
   *.key
   wifi.json
   __pycache__/
   .pytest_cache/
   *.pyc
   ALL_SCRIPTS.txt
   ```
2. Remove tracked secrets from git index: `git rm --cached` for each file
3. Verify existing per-module `.gitignore` files don't conflict
4. Remove secrets from git history (coordinate with [T-001](T-001-credential-cleanup.md))

## Acceptance Criteria

- Root `.gitignore` covers all secret/generated file patterns
- No `.env`, `.pem`, or `wifi.json` files in `git ls-files` output
- `.env.example` files remain tracked as templates
