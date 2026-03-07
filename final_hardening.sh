#!/usr/bin/env bash
set -euo pipefail

echo "======================================================="
echo " ePaper Frame – Final Hardening Script"
echo " (watchdog, journald limits, OverlayFS read-only root)"
echo "======================================================="
echo
echo "NOTE: Run this AFTER all other install scripts are done."
echo "      Changes are system-wide and require a reboot."
echo

# Figure out which user we should add the shell notice for
TARGET_USER=${SUDO_USER:-$USER}
TARGET_HOME=$(eval echo "~$TARGET_USER")
BASHRC="${TARGET_HOME}/.bashrc"

echo "Target user for shell notice : ${TARGET_USER}"
echo "Target home directory        : ${TARGET_HOME}"
echo

# ---------------------------------------------------------
# 1) Hardware watchdog
# ---------------------------------------------------------
echo "----------------------------------------"
echo "▶ Enabling hardware watchdog"
echo "----------------------------------------"

# Choose correct boot config path (Raspberry Pi OS variants)
BOOT_CONFIG="/boot/config.txt"
if [ -f /boot/firmware/config.txt ]; then
  BOOT_CONFIG="/boot/firmware/config.txt"
fi

echo "Using boot config: ${BOOT_CONFIG}"

# Make sure dtparam=watchdog=on is present
if ! grep -q '^dtparam=watchdog=on' "$BOOT_CONFIG"; then
  echo "Adding dtparam=watchdog=on to ${BOOT_CONFIG}"
  echo "dtparam=watchdog=on" | sudo tee -a "$BOOT_CONFIG" >/dev/null
else
  echo "dtparam=watchdog=on already set."
fi

echo
echo "Installing watchdog package..."
sudo apt-get update
sudo apt-get install -y watchdog

WATCHDOG_CONF="/etc/watchdog.conf"

echo "Tweaking ${WATCHDOG_CONF}..."
# Use /dev/watchdog device
sudo sed -i 's|^#\?watchdog-device .*|watchdog-device = /dev/watchdog|' "$WATCHDOG_CONF" || true
# Make sure we have at least one simple check
sudo sed -i 's|^#\?max-load-1 .*|max-load-1 = 24|' "$WATCHDOG_CONF" || true
# Shorter timeout (15s) which works reliably on RPi
sudo sed -i 's|^#\?watchdog-timeout .*|watchdog-timeout = 15|' "$WATCHDOG_CONF" || true

echo "Enabling and starting watchdog.service..."
sudo systemctl enable watchdog.service
sudo systemctl restart watchdog.service || true

echo "Watchdog configured."
echo

# ---------------------------------------------------------
# 2) Journald: keep logs in RAM with conservative limits
# ---------------------------------------------------------
echo "----------------------------------------"
echo "▶ Configuring systemd-journald limits"
echo "----------------------------------------"

sudo mkdir -p /etc/systemd/journald.conf.d

sudo tee /etc/systemd/journald.conf.d/99-epaper-frame.conf >/dev/null <<'EOF'
[Journal]
# Keep logs in RAM (volatile) – with OverlayFS root, this avoids wearing the SD card
Storage=volatile

# Hard caps so logs cannot grow unbounded in RAM
RuntimeMaxUse=50M
RuntimeMaxFileSize=10M

# Optional retention cap (not strictly needed with volatile storage, but harmless)
MaxRetentionSec=3day

# Disable separate persistent quota (we don't keep persistent journals)
SystemMaxUse=0
EOF

echo "Restarting systemd-journald..."
sudo systemctl restart systemd-journald.service || true
echo "Journald log limits configured."
echo

# ---------------------------------------------------------
# 3) Enable OverlayFS read-only root via raspi-config
# ---------------------------------------------------------
echo "----------------------------------------"
echo "▶ Enabling OverlayFS read-only root"
echo "----------------------------------------"

if ! command -v raspi-config >/dev/null 2>&1; then
  echo "raspi-config not found – installing..."
  sudo apt-get install -y raspi-config
fi

if command -v raspi-config >/dev/null 2>&1; then
  echo "Calling: sudo raspi-config nonint enable_overlayfs"
  if sudo raspi-config nonint enable_overlayfs; then
    echo "OverlayFS has been configured."
    echo "It will take effect after the next reboot."
  else
    echo "WARNING: raspi-config nonint enable_overlayfs failed." >&2
  fi
else
  echo "ERROR: raspi-config still not available; cannot enable OverlayFS automatically." >&2
fi

echo

# ---------------------------------------------------------
# 4) Add login notice to the target user's ~/.bashrc
# ---------------------------------------------------------
echo "----------------------------------------"
echo "▶ Adding overlay warning to ${BASHRC}"
echo "----------------------------------------"

add_notice_snippet() {
  cat <<'EOF'
# >>> epaper-frame overlay notice >>>
# The ePaper frame setup has enabled an OverlayFS read-only root filesystem.
# Any changes you make to / (including apt upgrades, config files, etc.)
# will NOT survive a reboot.
#
# For maintenance you can temporarily disable the overlay like this:
#   sudo raspi-config nonint disable_overlayfs
#   sudo reboot
#
# After you are done, re-enable the overlay with:
#   sudo raspi-config nonint enable_overlayfs
#   sudo reboot
#
# This message is shown once per shell session.
if [ -z "${EPAPER_OVERLAYFS_NOTICE_SHOWN:-}" ]; then
  export EPAPER_OVERLAYFS_NOTICE_SHOWN=1
  echo
  echo "[epaper-frame] Root filesystem is running with OverlayFS (read-only base)."
  echo "  To temporarily make the real SD root writable for maintenance:"
  echo "    sudo raspi-config nonint disable_overlayfs && sudo reboot"
  echo "  After maintenance, re-enable it:"
  echo "    sudo raspi-config nonint enable_overlayfs && sudo reboot"
  echo
fi
# <<< epaper-frame overlay notice <<<
EOF
}

if [ -f "$BASHRC" ]; then
  if grep -q 'epaper-frame overlay notice' "$BASHRC"; then
    echo "Notice already present in ${BASHRC} – leaving it as is."
  else
    echo "Appending overlay notice to ${BASHRC} for user ${TARGET_USER}."
    if [ "$EUID" -eq 0 ]; then
      # Script is running as root (e.g. via sudo) – preserve ownership
      sudo -u "$TARGET_USER" bash -c "add_notice_snippet >> '$BASHRC'" add_notice_snippet="$(declare -f add_notice_snippet)"
    else
      # Running as normal user – can write directly
      add_notice_snippet >> "$BASHRC"
    fi
  fi
else
  echo "WARNING: ${BASHRC} does not exist – skipping login notice."
fi

echo
echo "======================================================="
echo " Hardening completed."
echo
echo " * Hardware watchdog enabled (dtparam=watchdog=on, watchdog.service)."
echo " * systemd-journald logs kept in RAM with size limits."
echo " * OverlayFS read-only root configured via raspi-config."
echo " * A notice has been added to ${BASHRC} explaining how to"
echo "   temporarily disable/enable OverlayFS for maintenance."
echo
echo "IMPORTANT: Reboot now so OverlayFS and watchdog changes take effect:"
echo "  sudo reboot"
echo "======================================================="
