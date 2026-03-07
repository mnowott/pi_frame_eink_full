#!/bin/bash
set -e

echo "Enabling SPI interface..."
sudo sed -i 's/^dtparam=spi=.*/dtparam=spi=on/' /boot/config.txt
sudo sed -i 's/^#dtparam=spi=.*/dtparam=spi=on/' /boot/config.txt
sudo raspi-config nonint do_spi 0

echo "Enabling I2C interface..."
sudo sed -i 's/^dtparam=i2c_arm=.*/dtparam=i2c_arm=on/' /boot/config.txt
sudo sed -i 's/^#dtparam=i2c_arm=.*/dtparam=i2c_arm=on/' /boot/config.txt
sudo raspi-config nonint do_i2c 0

echo "Installing Python dependencies for ePaper display..."
# Update package index
sudo apt-get update

# Core Python + hardware + Pillow + fonts
sudo apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  python3-spidev \
  python3-gpiozero \
  python3-pil \
  fonts-dejavu-core

echo
echo "Creating / updating virtualenv for ePaper app..."

# Determine current user and home
CURRENT_USER=${SUDO_USER:-$(whoami)}
CURRENT_HOME=$(eval echo "~$CURRENT_USER")
VENV_DIR="${CURRENT_HOME}/epaper-venv"

# Create venv (with system site-packages so we can reuse spidev, gpiozero, etc.)
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv at: $VENV_DIR"
  sudo -u "$CURRENT_USER" python3 -m venv --system-site-packages "$VENV_DIR"
else
  echo "Virtualenv already exists at: $VENV_DIR"
fi

echo "Installing / upgrading Pillow in the virtualenv..."
sudo -u "$CURRENT_USER" "${VENV_DIR}/bin/pip" install --upgrade pip
sudo -u "$CURRENT_USER" "${VENV_DIR}/bin/pip" install --upgrade pillow

echo "Python dependencies installed (system + venv)."
echo

echo "Setting up python script epaper service..."
SERVICE_NAME="epaper.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

# Use the repo directory where setup.sh lives as WorkingDirectory
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

sudo tee "$SERVICE_PATH" > /dev/null <<EOF
[Unit]
Description=ePaper Display Service
After=network.target mnt-epaper_sd.mount
Wants=mnt-epaper_sd.mount

[Service]
ExecStart=${VENV_DIR}/bin/python ${REPO_DIR}/sd_monitor.py
WorkingDirectory=${REPO_DIR}
Restart=always
User=${CURRENT_USER}

[Install]
WantedBy=multi-user.target
EOF

echo "Creating default settings.json (if not present)..."
CONFIG_DIR="${CURRENT_HOME}/.config/epaper_settings"
CONFIG_PATH="${CONFIG_DIR}/settings.json"

sudo -u "$CURRENT_USER" mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_PATH" ]; then
    sudo -u "$CURRENT_USER" tee "$CONFIG_PATH" > /dev/null <<EOF
{
  "picture_mode": "both",
  "change_interval_minutes": 15,
  "stop_rotation_between": null,
  "s3_folder": "s3_folder"
}
EOF
    echo "Created default settings at $CONFIG_PATH"
else
    echo "settings.json already exists at $CONFIG_PATH, leaving it unchanged."
fi

echo "Enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo "Setup complete!"
read -p "Reboot required. Reboot now? (y/n): " REBOOT_CHOICE
if [[ "\$REBOOT_CHOICE" == "y" || "\$REBOOT_CHOICE" == "Y" ]]; then
    echo "Rebooting now..."
    sudo reboot
else
    echo "Reboot skipped. Please remember to reboot at a later time."
fi
