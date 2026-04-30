#!/usr/bin/env bash
#
# Assume the imageuiapp-admin role created by the CloudFormation stack
# under infrastructure/cloudformation/admin-role/, then export short-lived
# credentials into the current shell.
#
# !!! THIS SCRIPT MUST BE SOURCED, NOT EXECUTED !!!
#
#     source scripts/aws/assume_admin.sh
#
# Two flows are supported, auto-detected from .env. MFA is the default;
# SSO is used only if AWS_MFA_SERIAL is unset and AWS_SSO_PROFILE is set.
#
#   1. MFA (default). Set in .env:
#        AWS_MFA_SERIAL=arn:aws:iam::<acct>:mfa/<device-name>
#      The script prompts for the current 6-digit TOTP code from your
#      authenticator app and calls aws sts assume-role with that code.
#
#   2. SSO (fallback). Set in .env when you do NOT have AWS_MFA_SERIAL:
#        AWS_SSO_PROFILE=<aws cli profile configured for SSO>
#      The script runs `aws sso login --profile $AWS_SSO_PROFILE`, which
#      opens a browser. After you confirm, it does `aws sts assume-role`
#      using that profile as the source.
#
# In both cases, .env must also contain:
#   AWS_ADMIN_ROLE_ARN   ARN of the imageuiapp-admin role (CFN output)
#   AWS_DEFAULT_REGION   region for STS calls
#
# After sourcing, the env vars AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
# AWS_SESSION_TOKEN, and AWS_SESSION_EXPIRATION are exported for the
# duration of the role session (default 1 h, max what the role allows).

# Detect sourcing.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  echo "ERROR: this script must be SOURCED, not executed." >&2
  echo "       Run: source $(basename "$0")" >&2
  exit 1
fi

# Note: do NOT use `set -e` in a sourced script — it would kill the user's
# shell on any failure. Handle errors with explicit returns.

_assume_admin_fail() {
  echo "ERROR: $*" >&2
  return 1
}

_assume_admin_main() {
  local repo_root env_file
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"
  env_file="${repo_root}/.env"

  if [ ! -f "${env_file}" ]; then
    _assume_admin_fail ".env not found at ${env_file}"
    return $?
  fi

  set -a
  # shellcheck disable=SC1090
  source "${env_file}"
  set +a

  if [ -z "${AWS_ADMIN_ROLE_ARN:-}" ]; then
    _assume_admin_fail "AWS_ADMIN_ROLE_ARN not set in .env"
    return $?
  fi

  local region="${AWS_DEFAULT_REGION:-eu-central-1}"
  local session_name="imageuiapp-admin-$(date +%Y%m%dT%H%M%S)"
  local creds_json

  # Clear any previously-assumed creds so the source-call is unambiguous.
  unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SESSION_EXPIRATION

  if [ -n "${AWS_MFA_SERIAL:-}" ]; then
    echo "==> MFA path (default). Device: ${AWS_MFA_SERIAL}"
    local mfa_code
    read -r -p "Enter 6-digit MFA code: " mfa_code
    if ! [[ "${mfa_code}" =~ ^[0-9]{6}$ ]]; then
      _assume_admin_fail "MFA code must be exactly 6 digits"
      return $?
    fi
    creds_json="$(aws sts assume-role \
      --role-arn "${AWS_ADMIN_ROLE_ARN}" \
      --role-session-name "${session_name}" \
      --serial-number "${AWS_MFA_SERIAL}" \
      --token-code "${mfa_code}" \
      --region "${region}" \
      --output json 2>&1)"
  elif [ -n "${AWS_SSO_PROFILE:-}" ]; then
    echo "==> SSO fallback. Profile: ${AWS_SSO_PROFILE}"
    echo "==> Running 'aws sso login' (browser will open)..."
    if ! aws sso login --profile "${AWS_SSO_PROFILE}"; then
      _assume_admin_fail "aws sso login failed"
      return $?
    fi
    creds_json="$(aws sts assume-role \
      --profile "${AWS_SSO_PROFILE}" \
      --role-arn "${AWS_ADMIN_ROLE_ARN}" \
      --role-session-name "${session_name}" \
      --region "${region}" \
      --output json 2>&1)"
  else
    _assume_admin_fail "Neither AWS_MFA_SERIAL nor AWS_SSO_PROFILE is set in .env. Set AWS_MFA_SERIAL (default path)."
    return $?
  fi

  if ! echo "${creds_json}" | grep -q '"AccessKeyId"'; then
    echo "ERROR: assume-role failed:" >&2
    echo "${creds_json}" >&2
    return 1
  fi

  AWS_ACCESS_KEY_ID="$(echo "${creds_json}" | jq -r '.Credentials.AccessKeyId')"
  AWS_SECRET_ACCESS_KEY="$(echo "${creds_json}" | jq -r '.Credentials.SecretAccessKey')"
  AWS_SESSION_TOKEN="$(echo "${creds_json}" | jq -r '.Credentials.SessionToken')"
  AWS_SESSION_EXPIRATION="$(echo "${creds_json}" | jq -r '.Credentials.Expiration')"
  export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SESSION_EXPIRATION
  export AWS_DEFAULT_REGION="${region}"

  echo
  echo "==> Assumed role: ${AWS_ADMIN_ROLE_ARN}"
  echo "==> Session name: ${session_name}"
  echo "==> Expires:      ${AWS_SESSION_EXPIRATION}"
  echo "==> Verify:       aws sts get-caller-identity"
}

_assume_admin_main "$@"
unset -f _assume_admin_main _assume_admin_fail
