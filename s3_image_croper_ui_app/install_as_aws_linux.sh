#!/usr/bin/env bash
set -euo pipefail

APP_USER="ec2-user"
HOME_DIR="/home/${APP_USER}"

########################################
# 0) Environment variables in .bashrc
########################################

if ! grep -q 'S3_BUCKET=' "${HOME_DIR}/.bashrc"; then
  echo 'export S3_BUCKET="your-s3-bucket-name"' >> "${HOME_DIR}/.bashrc"
fi

if ! grep -q 'AWS_REGION=' "${HOME_DIR}/.bashrc"; then
  echo 'export AWS_REGION="eu-central-1"' >> "${HOME_DIR}/.bashrc"
fi

########################################
# 1) System packages (Amazon Linux)
########################################

# Amazon Linux 2023 → dnf, AL2 → yum
if command -v dnf >/dev/null 2>&1; then
  PKG_MGR=dnf
elif command -v yum >/dev/null 2>&1; then
  PKG_MGR=yum
else
  echo "Neither dnf nor yum found. Are you sure this is Amazon Linux?"
  exit 1
fi

echo "==> Updating system packages..."
sudo "$PKG_MGR" -y update

echo "==> Installing Python, pip, awscli..."
sudo "$PKG_MGR" -y install python3 python3-pip awscli

# Install Python 3.11 (required by Poetry project)
echo "==> Installing Python 3.11..."
if "$PKG_MGR" list python3.11 >/dev/null 2>&1; then
  sudo "$PKG_MGR" -y install python3.11
else
  echo "ERROR: python3.11 package not found in repos. You need Python >=3.11 for this project."
  exit 1
fi

########################################
# 2) Install Poetry for ec2-user (if not already)
########################################

if ! sudo -u "${APP_USER}" bash -lc 'command -v poetry >/dev/null 2>&1'; then
  echo "==> Installing Poetry..."
  sudo -u "${APP_USER}" bash -lc 'curl -sSL https://install.python-poetry.org | python3 -'
else
  echo "==> Poetry already installed, skipping."
fi

# Ensure Poetry is on PATH for ec2-user
if ! grep -q '.local/bin' "${HOME_DIR}/.bashrc"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${HOME_DIR}/.bashrc"
fi

# For this script run, make sure PATH is updated
export PATH="${HOME_DIR}/.local/bin:${PATH}"

echo "==> Poetry version (as ec2-user):"
sudo -u "${APP_USER}" bash -lc 'poetry --version || echo "Poetry not in PATH yet"'

########################################
# 3) Use Python 3.11 for the Poetry envs
########################################

# Figure out where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGE_APP_DIR="${SCRIPT_DIR}/ImageUiApp"
SETTINGS_APP_DIR="${SCRIPT_DIR}/SettingsApp"

if [ -d "${IMAGE_APP_DIR}" ]; then
  echo "==> Configuring Poetry env for ImageUiApp with Python 3.11..."
  sudo -u "${APP_USER}" bash -lc "
    cd '${IMAGE_APP_DIR}' \
    && poetry env use /usr/bin/python3.11 \
    && poetry install
  "
else
  echo "WARNING: ${IMAGE_APP_DIR} not found, skipping ImageUiApp install."
fi

if [ -d "${SETTINGS_APP_DIR}" ]; then
  echo "==> Configuring Poetry env for SettingsApp with Python 3.11..."
  sudo -u "${APP_USER}" bash -lc "
    cd '${SETTINGS_APP_DIR}' \
    && poetry env use /usr/bin/python3.11 \
    && poetry install
  "
else
  echo "NOTE: ${SETTINGS_APP_DIR} not found, skipping SettingsApp."
fi

########################################
# 4) Create systemd service for ImageUiApp
########################################

if [ -d "${IMAGE_APP_DIR}" ]; then
  echo "==> Creating systemd service for ImageUiApp..."

  SERVICE_FILE="/etc/systemd/system/imageuiapp.service"

  sudo tee "${SERVICE_FILE}" >/dev/null << EOF
[Unit]
Description=ImageUiApp (Poetry CLI)
After=network.target

[Service]
User=${APP_USER}
WorkingDirectory=${IMAGE_APP_DIR}
# Load env like PATH, S3_BUCKET, AWS_REGION via a login shell
ExecStart=/bin/bash -lc 'cd "${IMAGE_APP_DIR}" && poetry run imageuiapp --port 8051'
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

  echo "==> Reloading systemd and enabling service..."
  sudo systemctl daemon-reload
  sudo systemctl enable imageuiapp
  sudo systemctl start imageuiapp

  echo "==> Service status (short):"
  sudo systemctl --no-pager --full status imageuiapp || true
else
  echo "Skipping systemd service creation: ${IMAGE_APP_DIR} not found."
fi

########################################
# 5) Final info
########################################

cat << 'EOM'

==============================================
Installation done.

To apply environment changes in interactive shells:
  source ~/.bashrc

To check the ImageUiApp service:
  sudo systemctl status imageuiapp

To stop/start/restart:
  sudo systemctl stop imageuiapp
  sudo systemctl start imageuiapp
  sudo systemctl restart imageuiapp

Logs (last 50 lines):
  journalctl -u imageuiapp -n 50

==============================================
EOM
