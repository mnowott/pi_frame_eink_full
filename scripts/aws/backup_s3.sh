#!/usr/bin/env bash
#
# Snapshot the family-photos S3 bucket to a local directory.
# Always run this before any infrastructure change that could risk the
# bucket (Terraform import/destroy, lifecycle changes, etc.).
#
# Reads S3_BUCKET and AWS_DEFAULT_REGION from <repo-root>/.env.
#
# Usage:
#   bash scripts/aws/backup_s3.sh [destination_dir]
#
# Default destination: $HOME/aws_backups/<bucket>-<timestamp>/

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

if [ ! -f "${ENV_FILE}" ]; then
  echo "ERROR: .env not found at ${ENV_FILE}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

if [ -z "${S3_BUCKET:-}" ]; then
  echo "ERROR: S3_BUCKET not set in .env" >&2
  exit 1
fi

DEFAULT_DEST="${HOME}/aws_backups/${S3_BUCKET}-$(date +%Y%m%d_%H%M%S)"
DEST="${1:-$DEFAULT_DEST}"

mkdir -p "${DEST}"

echo "==> Backing up s3://${S3_BUCKET} to ${DEST}"
aws s3 sync \
  "s3://${S3_BUCKET}" \
  "${DEST}" \
  ${AWS_DEFAULT_REGION:+--region "${AWS_DEFAULT_REGION}"}

echo
echo "==> Backup complete:"
du -sh "${DEST}"
echo "==> Object count: $(find "${DEST}" -type f | wc -l)"
echo "==> Path: ${DEST}"
