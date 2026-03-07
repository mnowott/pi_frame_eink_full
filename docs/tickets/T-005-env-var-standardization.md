# T-005: Standardize AWS environment variable names

Status: Closed
Last updated: 2026-03-07

## Problem

AWS credential env var names differ across modules:

| Location | Access Key Var | Secret Key Var | Region Var | Bucket Var |
|----------|---------------|----------------|-----------|------------|
| `install_env.sh` | `AWS_ACCESS_KEY_ID` + `AWS_KEY_ID` | `AWS_SECRET_ACCESS_KEY` | `REGION` | `S3_BUCKET` |
| `sd-s3-sync.service` | `AWS_KEY_ID` | `AWS_SECRET_ACCESS_KEY` | `REGION` | `S3_BUCKET` |
| `sync_s3_from_sd.py` | Accepts many variants | Accepts many variants | `AWS_REGION` / `AWS_DEFAULT_REGION` | `S3_BUCKET` |
| ImageUiApp `.env` | `AWS_ACCESS_KEY_ID` | `AWS_SECRET_ACCESS_KEY` | `REGION` | `S3_BUCKET` |

The non-standard `AWS_KEY_ID` and `REGION` (without `AWS_` prefix) cause confusion. The `sync_s3_from_sd.py` script works around this by accepting many variants, but the root cause should be fixed.

## Plan

1. Standardize on AWS SDK-compatible names everywhere:
   - `AWS_ACCESS_KEY_ID` (standard, recognized by boto3 and awscli)
   - `AWS_SECRET_ACCESS_KEY` (standard)
   - `AWS_DEFAULT_REGION` (standard for awscli) or `AWS_REGION` (standard for boto3)
   - `S3_BUCKET` (custom, keep as-is)
2. Update `install_env.sh`: remove `AWS_KEY_ID` duplicate
3. Update `sd-s3-sync.service` template: use standard names
4. Update `.env.example` files

## Acceptance Criteria

- All env vars use AWS SDK-standard names
- No duplicate/alias env vars (e.g., both `AWS_KEY_ID` and `AWS_ACCESS_KEY_ID`)
- `sync_s3_from_sd.py` fallback logic can be simplified after standardization
