#!/usr/bin/env python3
"""
sync_s3_from_sd.py

Behavior:
1. Scan all mounted filesystems for wifi.json at their root.
2. If found:
   - Use that filesystem as base_path.
3. If NOT found:
   - If running via sudo:
       use the original user's home (~$SUDO_USER) as base_path.
     Else:
       use the current user's home (~).
4. Read AWS credentials + bucket + optional Wi-Fi config from wifi.json
   (with fallback to environment variables).
5. If wifi_name + wifi_password present:
   - Check current Wi-Fi connection via nmcli.
   - If not connected to that SSID, try to connect.
6. Create base_path/s3_folder (if needed).
7. Sync S3 bucket *into* that folder using awscli **with --delete** so
   deletions in S3 are reflected locally.

Intended for Raspberry Pi OS Lite on a Pi Zero 2W.
"""

import json
import os
import shutil
import subprocess
import sys
from typing import Optional

WIFI_JSON_NAME = "wifi.json"
TARGET_FOLDER_NAME = "s3_folder"


def debug(msg: str) -> None:
    """Simple stderr logger."""
    print(f"[sync_s3_from_sd] {msg}", file=sys.stderr)


def find_mount_with_wifi() -> Optional[str]:
    """
    Scan /proc/mounts for a mount point that has wifi.json at its root.
    Returns the mount point path, or None if not found.
    """
    mount_points = []

    try:
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mount_points.append(parts[1])
    except Exception as e:
        debug(f"Error reading /proc/mounts: {e}")
        return None

    for mnt in mount_points:
        wifi_path = os.path.join(mnt, WIFI_JSON_NAME)
        if os.path.isfile(wifi_path):
            debug(f"Found {WIFI_JSON_NAME} on mount: {mnt}")
            return mnt

    return None


def determine_base_path() -> str:
    """
    Decide where to look for wifi.json if no external mount is found:
    - If SUDO_USER is set, use that user's home (~$SUDO_USER).
    - Else use the current user's home (~).
    """
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        home = os.path.expanduser(f"~{sudo_user}")
        debug(
            f"No mounted filesystem containing {WIFI_JSON_NAME} found; "
            f"falling back to SUDO_USER home: {home}"
        )
    else:
        home = os.path.expanduser("~")
        debug(
            f"No mounted filesystem containing {WIFI_JSON_NAME} found; "
            f"falling back to HOME: {home}"
        )
    return home


def _first_nonempty(*values) -> Optional[str]:
    """Return the first non-empty string in values, or None."""
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def load_config(wifi_path: str) -> dict:
    """
    Load wifi.json and normalize keys.

    AWS credentials & bucket are taken from wifi.json if present, falling
    back to environment variables if needed. This makes the script work
    both when run in an interactive shell and under systemd.
    """
    debug(f"Loading config from {wifi_path}")
    with open(wifi_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # AWS access key
    key_id = _first_nonempty(
        raw.get("aws_access_key_id"),
        raw.get("aws_key_id"),
        raw.get("aws_key"),
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_KEY_ID"),
    )

    # AWS secret key
    secret = _first_nonempty(
        raw.get("aws_secret_access_key"),
        raw.get("aws_secret"),
        raw.get("secret_access_key"),
        os.getenv("AWS_SECRET_ACCESS_KEY"),
        os.getenv("AWS_SECRET"),
    )

    # S3 bucket name
    bucket = _first_nonempty(
        raw.get("s3_bucket"),
        raw.get("bucket"),
        raw.get("s3_bucket_name"),
        os.getenv("S3_BUCKET"),
        os.getenv("AWS_S3_BUCKET"),
    )

    # Region (default to eu-central-1 if nothing else is set)
    region = _first_nonempty(
        raw.get("aws_region"),
        raw.get("region"),
        os.getenv("AWS_REGION"),
        os.getenv("AWS_DEFAULT_REGION"),
        "eu-central-1",
    )

    missing = []
    if not key_id:
        missing.append("aws_access_key_id / aws_key_id")
    if not secret:
        missing.append("aws_secret_access_key / aws_secret")
    if not bucket:
        missing.append("s3_bucket / bucket")

    if missing:
        raise ValueError(
            "Missing AWS config values in wifi.json or environment: " + ", ".join(missing)
        )

    # Optional Wi-Fi settings
    wifi_name = raw.get("wifi_name")
    wifi_password = raw.get("wifi_password")

    return {
        "aws_access_key_id": key_id,
        "aws_secret_access_key": secret,
        "s3_bucket": bucket,
        "aws_region": region,
        "wifi_name": wifi_name,
        "wifi_password": wifi_password,
    }


def ensure_wifi_connection(cfg: dict) -> int:
    """
    If wifi_name and wifi_password are provided in cfg, ensure we're connected
    to that SSID using nmcli. If already connected, do nothing.

    Returns 0 on success (or if Wi-Fi step is skipped),
    non-zero if nmcli connect fails.
    """
    ssid = cfg.get("wifi_name")
    password = cfg.get("wifi_password")

    if not ssid or not password:
        debug("wifi_name or wifi_password not set; skipping Wi-Fi configuration.")
        return 0

    # Check if nmcli is available
    if shutil.which("nmcli") is None:
        debug(
            "nmcli not found; cannot manage Wi-Fi from script. "
            "Install NetworkManager or configure Wi-Fi manually."
        )
        return 0  # Don't hard-fail S3 sync just because nmcli is missing

    # Check current Wi-Fi connections
    try:
        debug("Checking current Wi-Fi connection via nmcli...")
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
            capture_output=True,
            text=True,
            check=False,
        )
        debug(f"nmcli (check) exit code: {result.returncode}")
        if result.stdout.strip():
            debug(f"nmcli (check) stdout:\n{result.stdout.strip()}")
        if result.stderr.strip():
            debug(f"nmcli (check) stderr:\n{result.stderr.strip()}")
    except Exception as e:
        debug(f"Failed to run nmcli to check Wi-Fi: {e}")
        return 0  # don't block sync

    if result.returncode == 0:
        for line in result.stdout.splitlines():
            # Format: yes:<SSID> or no:<SSID>
            parts = line.split(":", 1)
            if len(parts) == 2:
                active, current_ssid = parts
                if active == "yes" and current_ssid == ssid:
                    debug(f"Already connected to Wi-Fi SSID '{ssid}'.")
                    return 0

    debug(f"Not connected to Wi-Fi SSID '{ssid}', attempting to connect via nmcli...")

    # Try to avoid stale scan results: rescan first
    try:
        debug("Running: nmcli dev wifi rescan")
        rescan = subprocess.run(
            ["nmcli", "dev", "wifi", "rescan"],
            capture_output=True,
            text=True,
            check=False,
        )
        debug(f"'nmcli dev wifi rescan' exit code: {rescan.returncode}")
        if rescan.stdout.strip():
            debug(f"'nmcli dev wifi rescan' stdout:\n{rescan.stdout.strip()}")
        if rescan.stderr.strip():
            debug(f"'nmcli dev wifi rescan' stderr:\n{rescan.stderr.strip()}")
    except Exception as e:
        debug(f"Failed to run 'nmcli dev wifi rescan': {e}")

    # Optional: list visible SSIDs after rescan for debugging
    try:
        debug("Listing visible Wi-Fi networks after rescan...")
        scan = subprocess.run(
            ["nmcli", "-t", "-f", "SSID", "dev", "wifi"],
            capture_output=True,
            text=True,
            check=False,
        )
        if scan.returncode == 0 and scan.stdout.strip():
            ssids = [line.strip() for line in scan.stdout.splitlines() if line.strip()]
            debug("Visible SSIDs:\n  " + "\n  ".join(ssids))
        else:
            debug(
                f"Could not list visible SSIDs; exit code {scan.returncode}, "
                f"stderr: {scan.stderr.strip()}"
            )
    except Exception as e:
        debug(f"Failed to list SSIDs after rescan: {e}")

    # Now try to connect
    try:
        connect_cmd = [
            "nmcli",
            "dev",
            "wifi",
            "connect",
            ssid,
            "password",
            password,
        ]
        safe_cmd = connect_cmd[:-1] + ["***"]
        debug(f"Running: {' '.join(safe_cmd)}")
        connect_result = subprocess.run(
            connect_cmd,
            text=True,
            capture_output=True,
        )
        debug(f"nmcli (connect) exit code: {connect_result.returncode}")
        if connect_result.stdout.strip():
            debug(f"nmcli (connect) stdout:\n{connect_result.stdout.strip()}")
        if connect_result.stderr.strip():
            debug(f"nmcli (connect) stderr:\n{connect_result.stderr.strip()}")
    except Exception as e:
        debug(f"Failed to run nmcli to connect to Wi-Fi: {e}")
        return 1

    if connect_result.returncode != 0:
        debug(
            f"nmcli failed to connect to Wi-Fi SSID '{ssid}' "
            f"with exit code {connect_result.returncode}"
        )
        return connect_result.returncode

    debug(f"Successfully triggered connection to Wi-Fi SSID '{ssid}'.")
    return 0


def sync_bucket_to_folder(cfg: dict, target_folder: str) -> int:
    """
    Run `aws s3 sync s3://bucket target_folder` with credentials
    taken from cfg via environment variables, **including --delete**
    so deletions on S3 propagate to the SD card.
    """
    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = cfg["aws_access_key_id"]
    env["AWS_SECRET_ACCESS_KEY"] = cfg["aws_secret_access_key"]
    env["AWS_DEFAULT_REGION"] = cfg["aws_region"]

    bucket = cfg["s3_bucket"]
    s3_url = f"s3://{bucket}"

    cmd = [
        "aws",
        "s3",
        "sync",
        s3_url,
        target_folder,
        "--only-show-errors",
        "--delete",          # respect deletions from S3
        "--exclude", "*.zip" # ignore any .zip object
    ]

    debug(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env)
    return result.returncode


def main() -> int:
    # 1. Try to find an external mounted drive with wifi.json
    mount_point = find_mount_with_wifi()

    if mount_point:
        base_path = mount_point
        debug(f"Using external mount as base path: {base_path}")
    else:
        # 2. Fallback: use home (taking sudo into account)
        base_path = determine_base_path()

    wifi_path = os.path.join(base_path, WIFI_JSON_NAME)
    if not os.path.isfile(wifi_path):
        debug(
            f"{WIFI_JSON_NAME} not found at {wifi_path}. "
            "Cannot proceed without config."
        )
        return 1

    try:
        cfg = load_config(wifi_path)
    except Exception as e:
        debug(f"Failed to load config from {wifi_path}: {e}")
        return 2

    # 3. Ensure Wi-Fi connection (if wifi_name + password present)
    wifi_rc = ensure_wifi_connection(cfg)
    if wifi_rc != 0:
        debug(
            f"Wi-Fi configuration reported non-zero exit code {wifi_rc}. "
            "Continuing to S3 sync anyway."
        )

    # 4. Prepare target folder and sync S3
    target_folder = os.path.join(base_path, TARGET_FOLDER_NAME)
    try:
        os.makedirs(target_folder, exist_ok=True)
        debug(f"Target folder is: {target_folder}")
    except Exception as e:
        debug(f"Failed to create target folder {target_folder}: {e}")
        return 3

    rc = sync_bucket_to_folder(cfg, target_folder)
    if rc != 0:
        debug(f"aws s3 sync failed with exit code {rc}")
    else:
        debug("Sync completed successfully.")

    return rc


if __name__ == "__main__":
    sys.exit(main())
