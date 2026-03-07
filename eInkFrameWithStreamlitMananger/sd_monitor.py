#!/usr/bin/env python3
import os
import sys
import time
import threading
import subprocess
import signal
from datetime import datetime, time as dtime

from settings_loader import (
    load_settings as _load_settings,
    get_refresh_time,
    DEFAULT_SETTINGS,
    SETTINGS_LOCATIONS,
)

# Fixed SD card mount path (from the systemd mount/udev setup)
SD_PATH = "/mnt/epaper_sd"
# Subdirectory on the SD card that holds processed 800x480 images
# (must match PROCESSED_DIR_NAME in frame_manager.py)
PROCESSED_DIR_NAME = "_epaper_pic"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PROCESSING_SCRIPT = os.path.join(SCRIPT_DIR, "frame_manager.py")
_process_lock = threading.Lock()
process = None  # Holds the subprocess running frame_manager.py
sd_was_removed = False  # Track if SD card was removed


def load_settings():
    return _load_settings(caller="sd_monitor")


# ---------------------------------------------------------
# Quiet hours handling
# ---------------------------------------------------------


def parse_hhmm(value: str) -> dtime | None:
    try:
        parts = value.split(":")
        h = int(parts[0])
        m = int(parts[1])
        return dtime(hour=h, minute=m)
    except Exception:
        return None


def parse_stop_rotation_between(cfg) -> tuple[dtime, dtime] | None:
    """Return (evening_time, morning_time) or None."""
    if not cfg or not isinstance(cfg, dict):
        return None

    evening_str = cfg.get("evening")
    morning_str = cfg.get("morning")
    if not evening_str or not morning_str:
        return None

    evening = parse_hhmm(evening_str)
    morning = parse_hhmm(morning_str)
    if not evening or not morning:
        return None

    return (evening, morning)


def in_quiet_hours(now: datetime, evening: dtime, morning: dtime) -> bool:
    """
    Returns True if current time is within the "stop_rotation_between" interval.

    If evening < morning:
        - Quiet between same-day times, e.g. 20:00 -> 23:00
    If evening > morning (typical overnight):
        - Quiet between evening and next day's morning, e.g. 22:00 -> 07:00
    """
    current = now.time()

    if evening < morning:
        # same-day window
        return evening <= current < morning
    else:
        # crosses midnight
        return current >= evening or current < morning


# ---------------------------------------------------------
# Process handling
# ---------------------------------------------------------


def start_frame_manager(sd_path, settings):
    """Start the image processing script as a separate process."""
    global process
    with _process_lock:
        if process is not None and process.poll() is None:
            print("[sd_monitor] Stopping existing frame_manager process...")
            process.send_signal(signal.SIGTERM)
            process.wait()
            print("[sd_monitor] Existing frame_manager process stopped.")

        refresh_time_sec = get_refresh_time(sd_path, settings=settings)

        print(
            f"[sd_monitor] Starting frame_manager with path {sd_path} and refresh_time_sec={refresh_time_sec}..."
        )
        process = subprocess.Popen(
            ["python3", IMAGE_PROCESSING_SCRIPT, sd_path, str(refresh_time_sec)],
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
        )
        print("[sd_monitor] frame_manager started.")


def stop_frame_manager(reason: str = ""):
    """Stop the running frame_manager process, if any."""
    global process
    with _process_lock:
        if process is not None and process.poll() is None:
            msg = (
                f"[sd_monitor] Stopping frame_manager process. Reason: {reason}"
                if reason
                else "[sd_monitor] Stopping frame_manager process."
            )
            print(msg)
            try:
                process.send_signal(signal.SIGTERM)
                process.wait()
            except Exception as e:
                print(f"[sd_monitor] Error stopping frame_manager: {e}")
        process = None


# ---------------------------------------------------------
# SD content change detection
# ---------------------------------------------------------


def compute_tree_stats(root: str) -> tuple[float, int]:
    """
    Walk the directory tree under 'root' and return:
      (latest_mtime, file_count)

    - latest_mtime: latest modification time (float, 0.0 if none)
    - file_count:   number of files under root

    IMPORTANT: the processed images cache directory (PROCESSED_DIR_NAME)
    is ignored so that internal conversions do not trigger restarts.
    """
    latest = 0.0
    count = 0
    root = os.path.abspath(root)

    processed_root = os.path.abspath(os.path.join(root, PROCESSED_DIR_NAME))

    for dirpath, dirs, filenames in os.walk(root):
        dirpath_abs = os.path.abspath(dirpath)

        # Skip the processed-image cache subtree (_epaper_pic)
        if dirpath_abs == processed_root or dirpath_abs.startswith(
            processed_root + os.sep
        ):
            dirs[:] = []  # don't descend further
            continue

        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            count += 1
            if st.st_mtime > latest:
                latest = st.st_mtime

    return latest, count


# ---------------------------------------------------------
# SD monitoring loop
# ---------------------------------------------------------


def monitor_sd_card():
    """Continuously monitor the SD card at /mnt/epaper_sd and restart frame_manager on insert/remove, quiet hours, or SD content changes."""
    global sd_was_removed
    sd_inserted = False

    settings = load_settings()
    quiet_cfg = parse_stop_rotation_between(settings.get("stop_rotation_between"))
    was_in_quiet = False

    if quiet_cfg:
        print(
            f"[sd_monitor] Quiet hours configured: {settings.get('stop_rotation_between')} (parsed={quiet_cfg})"
        )
    else:
        print("[sd_monitor] No quiet hours configured.")

    # For content-change detection
    last_tree_mtime: float | None = None
    last_tree_count: int | None = None
    last_tree_check = 0.0
    MTIME_CHECK_INTERVAL = 30  # seconds between full SD scans

    while True:
        try:
            # RELOAD SETTINGS EACH LOOP
            settings = load_settings()
            quiet_cfg = parse_stop_rotation_between(
                settings.get("stop_rotation_between")
            )

            now = datetime.now()
            in_quiet = False
            if quiet_cfg:
                in_quiet = in_quiet_hours(now, quiet_cfg[0], quiet_cfg[1])

            # Card is considered present if /mnt/epaper_sd is a mounted FS and accessible
            sd_mounted = os.path.ismount(SD_PATH) and os.access(
                SD_PATH, os.R_OK | os.X_OK
            )

            if sd_mounted:
                sd_path = SD_PATH

                if in_quiet:
                    # SD is present but within quiet hours -> stop rotation
                    if process is not None and process.poll() is None:
                        stop_frame_manager(reason="entering quiet hours")
                    sd_inserted = True
                    sd_was_removed = False
                    was_in_quiet = True

                else:
                    # Not in quiet hours, SD present
                    need_start = False

                    if not sd_inserted:
                        print(
                            "[sd_monitor] SD card detected. Starting frame_manager..."
                        )
                        need_start = True
                    elif sd_was_removed:
                        print(
                            "[sd_monitor] SD card reinserted. Restarting frame_manager..."
                        )
                        need_start = True
                    elif process is None or process.poll() is not None:
                        print("[sd_monitor] frame_manager not running, starting...")
                        need_start = True
                    elif was_in_quiet:
                        print(
                            "[sd_monitor] Quiet hours ended, restarting frame_manager..."
                        )
                        need_start = True

                    if need_start:
                        start_frame_manager(sd_path, settings)
                        sd_inserted = True
                        sd_was_removed = False
                        was_in_quiet = False
                        # Establish a baseline stats snapshot
                        try:
                            last_tree_mtime, last_tree_count = compute_tree_stats(
                                sd_path
                            )
                            last_tree_check = time.time()
                            print(
                                f"[sd_monitor] Initial SD content baseline: "
                                f"mtime={last_tree_mtime}, count={last_tree_count}"
                            )
                        except Exception as e:
                            print(f"[sd_monitor] Error computing initial SD stats: {e}")
                            last_tree_mtime = None
                            last_tree_count = None
                    else:
                        # No structural reason to restart; check SD content periodically
                        now_ts = time.time()
                        if (now_ts - last_tree_check) >= MTIME_CHECK_INTERVAL:
                            last_tree_check = now_ts
                            try:
                                current_mtime, current_count = compute_tree_stats(
                                    sd_path
                                )
                                if last_tree_mtime is None or last_tree_count is None:
                                    last_tree_mtime = current_mtime
                                    last_tree_count = current_count
                                    print(
                                        f"[sd_monitor] Set SD content baseline: "
                                        f"mtime={last_tree_mtime}, count={last_tree_count}"
                                    )
                                elif (
                                    current_mtime != last_tree_mtime
                                    or current_count != last_tree_count
                                ):
                                    print(
                                        "[sd_monitor] Detected change on SD card "
                                        f"(mtime/count: {last_tree_mtime}->{current_mtime}, "
                                        f"{last_tree_count}->{current_count}), "
                                        "restarting frame_manager..."
                                    )
                                    last_tree_mtime = current_mtime
                                    last_tree_count = current_count
                                    start_frame_manager(sd_path, settings)
                            except Exception as e:
                                print(
                                    f"[sd_monitor] Error computing SD content stats: {e}"
                                )

            else:
                # No SD card mounted at /mnt/epaper_sd
                if sd_inserted:
                    print("[sd_monitor] SD card removed.")
                    sd_inserted = False
                    sd_was_removed = True
                    was_in_quiet = False
                    last_tree_mtime = None
                    last_tree_count = None
                    last_tree_check = 0.0
                    stop_frame_manager(reason="SD card removed")

        except Exception as e:
            print(f"[sd_monitor] Error monitoring SD card: {e}")

        time.sleep(2)  # Check every 2 seconds


def cleanup_stale_mounts():
    """
    Ensure the mount directory exists. The actual mounting is handled by systemd.
    """
    try:
        if not os.path.exists(SD_PATH):
            os.makedirs(SD_PATH, exist_ok=True)
            print(f"[sd_monitor] Created mount directory: {SD_PATH}")
    except Exception as e:
        print(f"[sd_monitor] Error ensuring mount directory {SD_PATH}: {e}")


if __name__ == "__main__":
    cleanup_stale_mounts()
    monitor_sd_card()
