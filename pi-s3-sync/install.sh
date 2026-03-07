#!/usr/bin/env bash
set -e

# Use the directory where this script lives as the repo dir
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Using repo at: ${REPO_DIR}"

echo "### 1. Update packages"
sudo apt update

echo "### 2. Install awscli, Python, git and NetworkManager (for nmcli)"
sudo apt install -y awscli python3 git network-manager

echo "### 2a. Enable NetworkManager service (for nmcli)"
# This will start NetworkManager if available. On some systems it may already be active.
if sudo systemctl enable --now NetworkManager 2>/dev/null; then
  echo "NetworkManager service is enabled and (should be) running."
else
  echo "Warning: Could not enable/start NetworkManager service automatically."
fi

echo "### 2b. Check NetworkManager status"
if systemctl is-active --quiet NetworkManager; then
  echo "NetworkManager is active."
else
  echo "NOTE: NetworkManager is installed but not active."
fi

echo "### 2c. Reminder about making NetworkManager the default (if needed)"
echo "If nmcli says 'device not managed' for wlan0, you likely still use dhcpcd."
echo "To switch to NetworkManager as the default on Raspberry Pi OS:"
echo "  1) Run:  sudo raspi-config"
echo "  2) Go to:  'Advanced Options' -> 'Network Config'"
echo "  3) Select: 'NetworkManager'"
echo "  4) Reboot:  sudo reboot"
echo "Do this ONLY when you have local access (HDMI/keyboard) in case networking breaks."

echo "### 2d. Ensure user 'pi' is in group 'netdev' (for nmcli via polkit)"
if id -nG pi | grep -qw netdev; then
  echo "User 'pi' already in 'netdev' group."
else
  echo "Adding 'pi' to 'netdev' group..."
  sudo usermod -aG netdev pi
  echo "User 'pi' added to 'netdev'."
  echo "Note: You may need to log out / reboot or restart services for group changes to fully apply."
fi

echo "### 2e. Installing polkit rule to allow 'netdev' users to control NetworkManager"
sudo mkdir -p /etc/polkit-1/rules.d
sudo tee /etc/polkit-1/rules.d/10-nmcli-netdev.rules >/dev/null <<'EOF'
polkit.addRule(function(action, subject) {
    if (action.id.indexOf("org.freedesktop.NetworkManager.") == 0 &&
        subject.isInGroup("netdev")) {
        return polkit.Result.YES;
    }
});
EOF
echo "Polkit rule installed at /etc/polkit-1/rules.d/10-nmcli-netdev.rules"

echo "### 3. Using existing repo at ${REPO_DIR}"
cd "${REPO_DIR}"

echo '### 4. Install the sync script into /usr/local/bin'
sudo cp scripts/sync_s3_from_sd.py /usr/local/bin/sync_s3_from_sd.py
sudo chmod +x /usr/local/bin/sync_s3_from_sd.py

echo "### 5. Create environment file for S3 sync service"
sudo mkdir -p /etc/epaper-settings
if [ ! -f /etc/epaper-settings/s3-sync.env ]; then
  # Populate from current environment or prompt user to edit
  sudo tee /etc/epaper-settings/s3-sync.env >/dev/null <<ENVEOF
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-CHANGE_ME}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-CHANGE_ME}
AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-${REGION:-eu-central-1}}
S3_BUCKET=${S3_BUCKET:-CHANGE_ME}
ENVEOF
  sudo chmod 600 /etc/epaper-settings/s3-sync.env
  sudo chown root:root /etc/epaper-settings/s3-sync.env
  echo "Created /etc/epaper-settings/s3-sync.env (chmod 600)"
  if grep -q 'CHANGE_ME' /etc/epaper-settings/s3-sync.env; then
    echo "WARNING: /etc/epaper-settings/s3-sync.env contains placeholder values."
    echo "         Edit it with: sudo nano /etc/epaper-settings/s3-sync.env"
  fi
else
  echo "/etc/epaper-settings/s3-sync.env already exists, not overwriting."
fi

echo "### 6. Install systemd service + timer"
sudo cp systemd/sd-s3-sync.service /etc/systemd/system/sd-s3-sync.service
sudo cp systemd/sd-s3-sync.timer   /etc/systemd/system/sd-s3-sync.timer

echo "### 7. Reload systemd, enable and start timer"
sudo systemctl daemon-reload
sudo systemctl enable --now sd-s3-sync.timer

echo "Installation complete. #####"
echo "Installed sync_s3_from_sd.py to /usr/local/bin/"
echo "Systemd service: sd-s3-sync.service"
echo "Systemd timer:   sd-s3-sync.timer (runs every 15 minutes)"
echo "You can run a manual sync using: sudo /usr/local/bin/sync_s3_from_sd.py"
echo "Check timer status with: sudo systemctl status sd-s3-sync.timer"
echo "Check last runs with:    journalctl -u sd-s3-sync.service -n 50 --no-pager"
echo
echo "If Wi-Fi control via nmcli fails with 'device not managed',"
echo "run raspi-config as described above to switch to NetworkManager."
echo
echo "If you run the service as User=pi, the polkit rule + netdev group membership"
echo "should allow it to control Wi-Fi via nmcli without 'Not authorized' errors."
