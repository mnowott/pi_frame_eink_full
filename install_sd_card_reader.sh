#!/bin/bash
set -e

echo "=== ePaper SD card systemd mount installer ==="

# ----- Config -----
MOUNT_POINT="/mnt/epaper_sd"
SD_LABEL="EPAPER_SD"

# Determine the "real" user (not root when using sudo)
TARGET_USER=${SUDO_USER:-$(whoami)}
TARGET_UID=$(id -u "$TARGET_USER")
TARGET_GID=$(id -g "$TARGET_USER")

echo "Using user: $TARGET_USER (uid=$TARGET_UID, gid=$TARGET_GID)"
echo "Mount point: $MOUNT_POINT"
echo "Expected filesystem label: $SD_LABEL"
echo

echo "STEP 1: Detecting vfat *data* partition on /dev/sdX..."

CANDIDATE=""

# First pass:
#  - vfat
#  - /dev/sdXN (a partition, not the whole disk)
#  - label is NOT 'boot' or 'bootfs'
while read -r DEV FSTYPE LABEL; do
    # Skip non-vfat
    [ "$FSTYPE" != "vfat" ] && continue
    # Only partitions like /dev/sda1, /dev/sdb2, ...
    if [[ ! "$DEV" =~ ^/dev/sd[a-z][0-9]+$ ]]; then
        continue
    fi
    # Skip typical boot partitions if we can
    if [[ "$LABEL" == "boot" || "$LABEL" == "bootfs" ]]; then
        echo "  Skipping likely boot partition: $DEV (LABEL=$LABEL)"
        continue
    fi
    echo "  Candidate (non-boot) vfat partition: $DEV (LABEL=$LABEL)"
    CANDIDATE="$DEV"
done < <(lsblk -prno NAME,FSTYPE,LABEL /dev/sd?* 2>/dev/null || true)

# Second pass (fallback): if no non-boot vfat partition found, just pick
# any vfat partition on /dev/sdX (covers your fresh-stick case).
if [ -z "$CANDIDATE" ]; then
    echo "No non-boot vfat partition found, falling back to any vfat partition..."
    while read -r DEV FSTYPE LABEL; do
        [ "$FSTYPE" != "vfat" ] && continue
        if [[ ! "$DEV" =~ ^/dev/sd[a-z][0-9]+$ ]]; then
            continue
        fi
        echo "  Fallback candidate: $DEV (LABEL=$LABEL)"
        CANDIDATE="$DEV"
    done < <(lsblk -prno NAME,FSTYPE,LABEL /dev/sd?* 2>/dev/null || true)
fi

if [ -z "$CANDIDATE" ]; then
    echo "ERROR: Could not find a suitable vfat partition on /dev/sdX."
    echo "Tips:"
    echo "  - Make sure the USB SD reader is plugged in."
    echo "  - Run: lsblk -f  and check which /dev/sdXN is your SD card."
    echo "  - Then adapt this script if needed."
    exit 1
fi

echo "Detected data partition: $CANDIDATE"
echo

echo "STEP 2: Labelling $CANDIDATE as '$SD_LABEL'..."

# Read current label
CURRENT_LABEL=$(blkid -s LABEL -o value "$CANDIDATE" 2>/dev/null || true)

if [ "$CURRENT_LABEL" = "$SD_LABEL" ]; then
    echo "Partition already labelled '$SD_LABEL'."
else
    # Unmount first — fatlabel cannot operate on a mounted filesystem
    sudo umount "$CANDIDATE" 2>/dev/null || true
    if ! command -v fatlabel >/dev/null 2>&1; then
        echo "Installing dosfstools (provides fatlabel)..."
        sudo apt-get update -qq && sudo apt-get install -y dosfstools
    fi
    sudo fatlabel "$CANDIDATE" "$SD_LABEL"
    echo "Partition labelled '$SD_LABEL' (was: '${CURRENT_LABEL:-<none>}')."
fi
echo

echo "STEP 3: Preparing mount point directory..."
# Ensure the directory exists
sudo mkdir -p "$MOUNT_POINT"
# Make sure nothing is currently mounted there
sudo umount "$MOUNT_POINT" 2>/dev/null || true
# Try to chown the directory on the underlying FS (ok if it fails when vfat is mounted later)
if ! sudo chown "$TARGET_USER":"$TARGET_USER" "$MOUNT_POINT"; then
    echo "Warning: could not chown $MOUNT_POINT (this is safe to ignore if it is or will be vfat)."
fi

# Systemd mount units are named after the mount path:
# /mnt/epaper_sd -> mnt-epaper_sd.mount
MOUNT_UNIT_NAME="mnt-epaper_sd.mount"
MOUNT_UNIT_PATH="/etc/systemd/system/${MOUNT_UNIT_NAME}"

echo "STEP 4: Writing systemd mount unit: $MOUNT_UNIT_PATH"

sudo tee "$MOUNT_UNIT_PATH" > /dev/null <<EOF
[Unit]
Description=ePaper SD card mount
DefaultDependencies=no
After=local-fs-pre.target
Before=local-fs.target
Conflicts=umount.target

[Mount]
What=/dev/disk/by-label/$SD_LABEL
Where=$MOUNT_POINT
Type=vfat
Options=defaults,uid=$TARGET_UID,gid=$TARGET_GID,umask=0022,nofail,nosuid,noexec,nodev

[Install]
WantedBy=multi-user.target
EOF

echo "Systemd mount unit created."
echo

# ----- UDEV RULE to auto-start the mount when the device is plugged -----

UDEV_RULE_PATH="/etc/udev/rules.d/99-epaper-sd-mount.rules"

echo "STEP 5: Writing udev rule: $UDEV_RULE_PATH"

sudo tee "$UDEV_RULE_PATH" > /dev/null <<EOF
# Auto-start systemd mount for ePaper SD card when a device labelled $SD_LABEL appears.
# This is hardware-agnostic — any SD card with the right label will mount.
ACTION=="add", SUBSYSTEM=="block", ENV{ID_FS_LABEL}=="$SD_LABEL", ENV{SYSTEMD_WANTS}="$MOUNT_UNIT_NAME"
EOF

echo "Udev rule created."
echo

echo "STEP 6: Reloading systemd and udev, enabling and starting mount..."
sudo systemctl daemon-reload
sudo systemctl enable "$MOUNT_UNIT_NAME"
sudo systemctl start "$MOUNT_UNIT_NAME"

sudo udevadm control --reload-rules
sudo udevadm trigger

echo
echo "STEP 7: Verifying mount..."
if mountpoint -q "$MOUNT_POINT"; then
    echo "SUCCESS: $MOUNT_POINT is now mounted."
else
    echo "WARNING: $MOUNT_POINT is not reported as a mountpoint."
    echo "Check with: mount | grep $MOUNT_POINT"
fi

echo
echo "Done."

echo "Behavior summary:"
echo "  - On boot: systemd will mount any vfat device labelled '$SD_LABEL' at $MOUNT_POINT."
echo "  - If you unplug and later re-plug the SD card:"
echo "      * udev will notice the device with label '$SD_LABEL'"
echo "      * and ask systemd to start $MOUNT_UNIT_NAME again."
echo "  - To use a NEW data SD card, label it first:"
echo "      sudo fatlabel /dev/sdX1 $SD_LABEL"
echo
echo "To inspect status:"
echo "  systemctl status $MOUNT_UNIT_NAME"
echo
echo "To change user or mount point, re-run this script or edit:"
echo "  $MOUNT_UNIT_PATH and $UDEV_RULE_PATH"
