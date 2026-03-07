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
# 3) Firewall (ufw)
# ---------------------------------------------------------
echo "----------------------------------------"
echo "▶ Configuring firewall (ufw)"
echo "----------------------------------------"

sudo apt-get install -y ufw

# SAFETY: always allow SSH FIRST, before enabling the firewall
sudo ufw limit 22/tcp comment "SSH rate-limited"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.0.0/16 to any port 80 comment "SettingsApp LAN only"
sudo ufw allow from 10.0.0.0/8 to any port 80 comment "SettingsApp LAN only (10.x)"
sudo ufw allow from 172.16.0.0/12 to any port 80 comment "SettingsApp LAN only (172.x)"
sudo ufw --force enable

echo "Firewall configured. SSH always allowed."
echo

# ---------------------------------------------------------
# 4) SSH hardening
# ---------------------------------------------------------
echo "----------------------------------------"
echo "▶ Hardening SSH configuration"
echo "----------------------------------------"

SSH_CONF="/etc/ssh/sshd_config.d/99-epaper.conf"

sudo tee "$SSH_CONF" >/dev/null <<'EOF'
# ePaper frame SSH hardening
# Applied by final_hardening.sh

PermitRootLogin no
PubkeyAuthentication yes
PermitEmptyPasswords no
X11Forwarding no
AllowTcpForwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2

# NOTE: PasswordAuthentication is intentionally left ENABLED here.
# Disabling it before setting up key-based auth would lock you out!
#
# After confirming SSH key auth works, you can manually disable it:
#   echo "PasswordAuthentication no" | sudo tee -a /etc/ssh/sshd_config.d/99-epaper.conf
#   sudo systemctl reload sshd
EOF

echo "Reloading sshd..."
sudo systemctl reload sshd || sudo systemctl reload ssh || true
echo "SSH hardened (password auth still enabled for safety)."
echo

# ---------------------------------------------------------
# 5) Kernel parameters (sysctl)
# ---------------------------------------------------------
echo "----------------------------------------"
echo "▶ Applying kernel hardening parameters"
echo "----------------------------------------"

SYSCTL_CONF="/etc/sysctl.d/99-epaper.conf"

sudo tee "$SYSCTL_CONF" >/dev/null <<'EOF'
# ePaper frame kernel hardening
kernel.sysrq = 0
kernel.dmesg_restrict = 1
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv6.conf.all.disable_ipv6 = 1
EOF

sudo sysctl --system >/dev/null 2>&1 || true
echo "Kernel parameters applied."
echo

# ---------------------------------------------------------
# 6) Disable unused peripherals
# ---------------------------------------------------------
echo "----------------------------------------"
echo "▶ Disabling unused peripherals"
echo "----------------------------------------"

# Disable Bluetooth
if ! grep -q '^dtoverlay=disable-bt' "$BOOT_CONFIG"; then
  echo "dtoverlay=disable-bt" | sudo tee -a "$BOOT_CONFIG" >/dev/null
  echo "Bluetooth disabled (takes effect after reboot)."
else
  echo "Bluetooth already disabled."
fi

# Disable HDMI CEC
if ! grep -q '^hdmi_ignore_cec_init=1' "$BOOT_CONFIG"; then
  echo "hdmi_ignore_cec_init=1" | sudo tee -a "$BOOT_CONFIG" >/dev/null
  echo "HDMI CEC disabled."
else
  echo "HDMI CEC already disabled."
fi

echo

# ---------------------------------------------------------
# 7) Disable swap
# ---------------------------------------------------------
echo "----------------------------------------"
echo "▶ Disabling swap"
echo "----------------------------------------"

if command -v dphys-swapfile >/dev/null 2>&1; then
  sudo dphys-swapfile swapoff || true
  sudo dphys-swapfile uninstall || true
  sudo update-rc.d dphys-swapfile remove 2>/dev/null || true
  echo "Swap disabled."
else
  echo "dphys-swapfile not found — swap may already be disabled."
fi

echo

# ---------------------------------------------------------
# 8) Enable OverlayFS read-only root via raspi-config
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
# 9) Add login notice to the target user's ~/.bashrc
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
echo " * Firewall enabled (SSH always allowed, port 80 LAN only)."
echo " * SSH hardened (root login off, but password auth still enabled)."
echo " * Kernel parameters hardened (sysctl)."
echo " * Bluetooth and HDMI CEC disabled."
echo " * Swap disabled."
echo " * OverlayFS read-only root configured via raspi-config."
echo " * A notice has been added to ${BASHRC} explaining how to"
echo "   temporarily disable/enable OverlayFS for maintenance."
echo
echo "MANUAL STEP (after confirming SSH key auth works):"
echo "  echo 'PasswordAuthentication no' | sudo tee -a /etc/ssh/sshd_config.d/99-epaper.conf"
echo "  sudo systemctl reload sshd"
echo
echo "IMPORTANT: Reboot now so OverlayFS and watchdog changes take effect:"
echo "  sudo reboot"
echo "======================================================="
