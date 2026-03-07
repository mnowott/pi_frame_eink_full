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

# Determine the real user (not root when run via sudo)
CURRENT_USER=${SUDO_USER:-$(whoami)}
CURRENT_HOME=$(eval echo "~$CURRENT_USER")

# Regenerate lock file if pyproject.toml changed (e.g. different Python version on Pi)
echo "Regenerating poetry.lock (in case pyproject.toml drifted)..."
poetry lock

# poetry lock runs as root, which creates cache files owned by root.
# Fix ownership so the real user can write to the cache during install.
if [ -d "$CURRENT_HOME/.cache/pypoetry" ]; then
  chown -R "$CURRENT_USER:$CURRENT_USER" "$CURRENT_HOME/.cache/pypoetry"
fi

# Pi Zero 2W often lacks IPv6 connectivity, but Poetry's HTTP client tries
# IPv6 first and hangs until timeout. Temporarily disable IPv6 to force IPv4.
IPV6_WAS_DISABLED=$(sysctl -n net.ipv6.conf.all.disable_ipv6 2>/dev/null || echo 0)
if [ "$IPV6_WAS_DISABLED" = "0" ]; then
  echo "Temporarily disabling IPv6 (Poetry workaround for Pi Zero Wi-Fi)..."
  sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null
  sysctl -w net.ipv6.conf.default.disable_ipv6=1 >/dev/null
fi

# Install dependencies as the real user (not root) so the venv
# lands in ~pi/.cache/pypoetry/virtualenvs, not /root/.cache.
# Retry up to 5 times — Pi Zero Wi-Fi often times out on large downloads.
echo "Installing SettingsApp (retrying on network timeouts)..."
for attempt in 1 2 3 4 5; do
  echo "  Attempt $attempt..."
  if sudo -u "$CURRENT_USER" \
    POETRY_HTTP_TIMEOUT=600 \
    poetry install --no-interaction 2>&1; then
    echo "SettingsApp dependencies installed via Poetry."
    break
  fi
  if [ "$attempt" -eq 5 ]; then
    echo "ERROR: Poetry install failed after 5 attempts."
    # Re-enable IPv6 before exiting
    if [ "$IPV6_WAS_DISABLED" = "0" ]; then
      sysctl -w net.ipv6.conf.all.disable_ipv6=0 >/dev/null
      sysctl -w net.ipv6.conf.default.disable_ipv6=0 >/dev/null
    fi
    exit 1
  fi
  sleep 5
done

# Re-enable IPv6 if we disabled it
if [ "$IPV6_WAS_DISABLED" = "0" ]; then
  echo "Re-enabling IPv6..."
  sysctl -w net.ipv6.conf.all.disable_ipv6=0 >/dev/null
  sysctl -w net.ipv6.conf.default.disable_ipv6=0 >/dev/null
fi

echo
echo "========================================"
echo "▶ Creating systemd service for SettingsApp"
echo "========================================"

SERVICE_NAME="settingsapp.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

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

# SD card, settings config, and Poetry cache read/write
ReadWritePaths=/mnt/epaper_sd
ReadWritePaths=$CURRENT_HOME/.config/epaper_settings
ReadWritePaths=$CURRENT_HOME/.cache

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
