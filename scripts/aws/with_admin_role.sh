#!/usr/bin/env bash
#
# Run a command with admin-role credentials. Reuses cached STS creds from
# ~/.cache/imageuiapp-admin/creds.env if still valid; otherwise falls
# back to assume_admin.sh (interactive, or non-interactive if MFA_CODE
# is set in the environment).
#
# Usage:
#   bash scripts/aws/with_admin_role.sh aws sts get-caller-identity
#   MFA_CODE=123456 bash scripts/aws/with_admin_role.sh terraform plan
#
# Designed for the assume-aws-admin Claude Code skill: each AWS command
# issued by the skill goes through this wrapper, which silently reuses
# the live session and only asks for a fresh MFA code when the cached
# session has expired.

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <command> [args...]" >&2
  exit 2
fi

CACHE_FILE="${HOME}/.cache/imageuiapp-admin/creds.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSUME_SCRIPT="${SCRIPT_DIR}/assume_admin.sh"

_creds_valid() {
  [ -f "${CACHE_FILE}" ] || return 1
  # shellcheck disable=SC1090
  . "${CACHE_FILE}"
  [ -n "${AWS_SESSION_EXPIRATION:-}" ] || return 1
  # Convert ISO8601 to epoch and compare with now + 60 s buffer.
  local exp_epoch now_epoch
  exp_epoch="$(date -d "${AWS_SESSION_EXPIRATION}" +%s 2>/dev/null || echo 0)"
  now_epoch="$(date +%s)"
  [ "$((exp_epoch - now_epoch))" -gt 60 ]
}

if _creds_valid; then
  # _creds_valid already exported the cached vars via sourcing.
  exec "$@"
fi

# Either no cache, expired, or unparsable. Trigger assume.
echo "==> Cached admin-role session missing or near-expiry; assuming role..." >&2
# shellcheck disable=SC1090
. "${ASSUME_SCRIPT}"
exec "$@"
