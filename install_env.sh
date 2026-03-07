#!/usr/bin/env bash

BASHRC="$HOME/.bashrc"

add_export() {
  local line="$1"
  # Add line only if it's not already present
  if ! grep -qxF "$line" "$BASHRC" 2>/dev/null; then
    echo "$line" >> "$BASHRC"
    echo "Added: $line"
  else
    echo "Already present: $line"
  fi
}

# Load values from .env file in the same directory as this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env file not found at ${ENV_FILE}"
  echo "Copy .env.example to .env and fill in your credentials:"
  echo "  cp ${SCRIPT_DIR}/.env.example ${SCRIPT_DIR}/.env"
  exit 1
fi

# Source .env file to get values
set -a
source "$ENV_FILE"
set +a

# Validate required variables
for var in AWS_DEFAULT_REGION S3_BUCKET AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
  if [ -z "${!var:-}" ]; then
    echo "ERROR: ${var} is not set in ${ENV_FILE}"
    exit 1
  fi
done

add_export "export AWS_DEFAULT_REGION=\"$AWS_DEFAULT_REGION\""
add_export "export S3_BUCKET=\"$S3_BUCKET\""
add_export "export AWS_ACCESS_KEY_ID=\"$AWS_ACCESS_KEY_ID\""
add_export "export AWS_SECRET_ACCESS_KEY=\"$AWS_SECRET_ACCESS_KEY\""

echo
echo "Done. Reload your shell with:"
echo "  source \"$BASHRC\""