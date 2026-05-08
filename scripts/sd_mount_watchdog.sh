#!/bin/bash
# SD-card mount watchdog. Runs as root via sd-mount-watchdog.timer.
#
# Behaviour:
#   1. If /mnt/epaper_sd is mounted -> exit 0 (healthy).
#   2. If no vfat data partition is present on /dev/sdX -> log + exit 0
#      (no SD reader plugged in, nothing we can do).
#   3. Try systemctl restart mnt-epaper_sd.mount. If that mounts -> done.
#   4. Otherwise re-run install_sd_card_reader.sh to repair the unit and
#      udev rule, then restart the mount.
#
# The installer is idempotent. The timer interval is the rate-limit:
# at most one repair attempt per tick.

set -u

MOUNT_POINT="/mnt/epaper_sd"
MOUNT_UNIT="mnt-epaper_sd.mount"
INSTALLER_DEFAULT="/home/pi/pi_project/install_sd_card_reader.sh"
INSTALLER="${SD_INSTALLER:-$INSTALLER_DEFAULT}"

log() { echo "[sd_mount_watchdog] $*"; }

if mountpoint -q "$MOUNT_POINT"; then
    log "OK: $MOUNT_POINT already mounted."
    exit 0
fi

# Detect a candidate data partition: vfat on /dev/sdXN, label not boot/bootfs.
DEV=""
while read -r PART FSTYPE LABEL; do
    [ "$FSTYPE" != "vfat" ] && continue
    [[ ! "$PART" =~ ^/dev/sd[a-z][0-9]+$ ]] && continue
    [[ "$LABEL" == "boot" || "$LABEL" == "bootfs" ]] && continue
    DEV="$PART"; break
done < <(lsblk -prno NAME,FSTYPE,LABEL /dev/sd?* 2>/dev/null || true)

# Fallback: any vfat /dev/sdXN, in case label was stripped.
if [ -z "$DEV" ]; then
    while read -r PART FSTYPE _LABEL; do
        [ "$FSTYPE" != "vfat" ] && continue
        [[ ! "$PART" =~ ^/dev/sd[a-z][0-9]+$ ]] && continue
        DEV="$PART"; break
    done < <(lsblk -prno NAME,FSTYPE,LABEL /dev/sd?* 2>/dev/null || true)
fi

if [ -z "$DEV" ]; then
    log "No vfat data partition on /dev/sdX. SD reader not plugged in?"
    exit 0
fi

CURRENT_LABEL=$(blkid -s LABEL -o value "$DEV" 2>/dev/null || echo "<none>")
log "$MOUNT_POINT not mounted. Candidate: $DEV (label=$CURRENT_LABEL)."

# Cheap path: kick the existing mount unit.
systemctl daemon-reload >/dev/null 2>&1 || true
systemctl restart "$MOUNT_UNIT" 2>&1 | sed 's/^/[sd_mount_watchdog]   /' || true
sleep 2
if mountpoint -q "$MOUNT_POINT"; then
    log "Recovered: '$MOUNT_UNIT' restart succeeded."
    exit 0
fi

# Expensive path: re-run installer to repair the unit + udev rule.
CURRENT_WHAT=$(grep -E '^What=' /etc/systemd/system/"$MOUNT_UNIT" 2>/dev/null | head -1 || true)
log "Restart did not mount. Mount unit currently: ${CURRENT_WHAT:-<unit missing>}"

if [ ! -x "$INSTALLER" ]; then
    log "FAIL: installer not executable at $INSTALLER. Cannot self-repair."
    exit 1
fi

log "Running installer for full repair: $INSTALLER"
bash "$INSTALLER" 2>&1 | sed 's/^/[sd_mount_watchdog]   /'

if mountpoint -q "$MOUNT_POINT"; then
    log "Recovered after installer."
    exit 0
fi

log "FAIL: $MOUNT_POINT still not mounted after repair attempt."
exit 1
