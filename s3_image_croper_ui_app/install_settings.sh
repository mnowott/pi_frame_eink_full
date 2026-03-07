#!/usr/bin/env bash
set -euo pipefail

echo "========================================"
echo "▶ Installing base system packages"
echo "========================================"

sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  curl \
  awscli \
  python3-poetry

echo
echo "========================================"
echo "▶ Ensuring Poetry is available"
echo "========================================"

if ! command -v poetry >/dev/null 2>&1; then
  echo "ERROR: 'poetry' command not found even after installing python3-poetry."
  echo "       Please check your PATH or Debian/RPi repository status."
  exit 1
fi

echo "Poetry detected: $(poetry --version)"

echo
echo "========================================"
echo "▶ Installing SettingsApp with Poetry"
echo "========================================"

# Where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Go to SettingsApp directory (must exist)
cd "$SCRIPT_DIR/SettingsApp"

# Install dependencies into Poetry-managed venv
poetry install

echo "SettingsApp dependencies installed via Poetry."

echo
echo "========================================"
echo "▶ Creating systemd service for SettingsApp"
echo "========================================"

SERVICE_NAME="settingsapp.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
CURRENT_USER=${SUDO_USER:-$(whoami)}
CURRENT_HOME=$(eval echo "~$CURRENT_USER")

sudo tee "$SERVICE_PATH" > /dev/null <<EOF
[Unit]
Description=ePaper Settings Web App (Streamlit)
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR/SettingsApp

# Allow binding to port 80 without running as root
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE

# Run the app via Poetry
ExecStart=/bin/bash -lc 'poetry run settingsapp --port 80 --address 0.0.0.0'
Restart=always
RestartSec=5

# --- Sandboxing ---
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictNamespaces=true
LockPersonality=true
RestrictRealtime=true
RestrictSUIDSGID=true
PrivateDevices=true

# SD card and settings config read/write
ReadWritePaths=/mnt/epaper_sd
ReadWritePaths=$CURRENT_HOME/.config/epaper_settings

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd and enabling service..."
sudo systemctl daemon-reload

# In case the service was masked from a previous install / experiment
sudo systemctl unmask "$SERVICE_NAME" || true

sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"


echo
echo "====================================================================="
echo "SettingsApp installation complete."
echo "The settings UI should now be reachable at: http://<your-pi-ip>/"
echo "You can check the service status with:"
echo "  sudo systemctl status settingsapp.service"
echo "Logs via:"
echo "  journalctl -u settingsapp.service -n 100 -f"
echo "====================================================================="
