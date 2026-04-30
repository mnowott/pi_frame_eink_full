# scripts/aws/

Helpers for AWS-side operations.

| Script | Purpose | How to invoke |
|--------|---------|---------------|
| `backup_s3.sh` | Snapshot the family-photos S3 bucket to a local directory. Run before any risky infra change. | `bash scripts/aws/backup_s3.sh` |
| `assume_admin.sh` | Assume the `imageuiapp-admin` role via STS (MFA default, SSO fallback), export short-lived creds, cache them at `~/.cache/imageuiapp-admin/creds.env`. | **`source scripts/aws/assume_admin.sh`** (must be sourced). Non-interactive: `MFA_CODE=123456 source scripts/aws/assume_admin.sh`. |
| `with_admin_role.sh` | Run a single command under admin-role STS creds. Reuses the cache from `assume_admin.sh`; falls back to the assume flow if the cache is missing or near-expiry. | `bash scripts/aws/with_admin_role.sh <cmd> [args...]`. Non-interactive: `MFA_CODE=123456 bash scripts/aws/with_admin_role.sh <cmd>`. |

## Why these scripts

* `backup_s3.sh` — defence-in-depth: even though the Terraform `aws_s3_bucket`
  resource has `lifecycle.prevent_destroy = true`, having a local snapshot
  before any IaC change is cheap insurance for ~30 MB of family photos.
* `assume_admin.sh` — gets you out of the long-lived `AWS_ACCESS_KEY_ID` /
  `AWS_SECRET_ACCESS_KEY` habit. After deploying the
  `infrastructure/cloudformation/admin-role/` stack, daily IaC runs use
  short-lived STS credentials (default 1 h) issued only after MFA or SSO
  browser confirmation.

## .env keys consumed

```
S3_BUCKET=...                     # backup_s3.sh
AWS_DEFAULT_REGION=...            # both
AWS_ADMIN_ROLE_ARN=arn:aws:iam::<acct>:role/imageuiapp-admin   # assume_admin.sh

# Default auth path: MFA. Set AWS_MFA_SERIAL.
AWS_MFA_SERIAL=arn:aws:iam::<acct>:mfa/<device-name>

# Fallback only (used only if AWS_MFA_SERIAL is unset).
# AWS_SSO_PROFILE=<aws-cli-profile-name>
```
