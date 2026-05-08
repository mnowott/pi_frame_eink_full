"""Shared settings loader for all eInkFrame display-stack modules."""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_SETTINGS = {
    "picture_mode": "local",  # local | online | both
    "change_interval_minutes": 15,  # integer minutes
    "stop_rotation_between": None,  # or {"evening": "HH:MM", "morning": "HH:MM"}
    "s3_folder": "s3_folder",  # folder name on SD card for "online" images
}

SETTINGS_LOCATIONS = [
    "/mnt/epaper_sd/epaper_settings/settings.json",
    "/etc/epaper_settings/settings.json",
    os.path.expanduser("~/.config/epaper_settings/settings.json"),
    os.path.join(SCRIPT_DIR, "settings.json"),
]

# Cache key of the last load that emitted a log line. sd_monitor.py calls
# load_settings() every 2 seconds, so unconditional logging produced ~30
# identical lines per buffer flush in the journal. We only log when the
# resolved path or its mtime changes (i.e. settings were edited).
_last_logged_key: tuple | None = None


def load_settings(caller: str = "settings_loader") -> dict:
    """Load settings.json from the first found location, merging into defaults."""
    global _last_logged_key
    settings = DEFAULT_SETTINGS.copy()
    for path in SETTINGS_LOCATIONS:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for key in DEFAULT_SETTINGS:
                        if key in data:
                            settings[key] = data[key]
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    mtime = 0.0
                log_key = (caller, path, mtime)
                if log_key != _last_logged_key:
                    print(f"[{caller}] Loaded settings from {path}", flush=True)
                    _last_logged_key = log_key
                break
            except Exception as e:
                print(f"[{caller}] Error reading settings from {path}: {e}", flush=True)
    return settings


def get_refresh_time(
    sd_path: str, settings: dict | None = None, filename: str = "refresh_time.txt"
) -> int:
    """Determine refresh time in seconds from settings, SD file, or default (600)."""
    if settings is None:
        settings = DEFAULT_SETTINGS

    change_interval = settings.get("change_interval_minutes")
    try:
        if change_interval is not None:
            minutes = int(change_interval)  # type: ignore[arg-type]
            if minutes > 0:
                return minutes * 60
    except Exception as e:
        print(f"[settings_loader] Invalid change_interval_minutes: {e}")

    file_path = os.path.join(sd_path, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                number = f.read().strip()
                if number.isdigit():
                    return int(number)
                else:
                    print(
                        f"[settings_loader] Invalid number in {filename}, defaulting to 600"
                    )
                    return 600
        except Exception as e:
            print(f"[settings_loader] Error reading {filename}: {e}")
            return 600
    else:
        print(f"[settings_loader] {filename} not found, defaulting to 600")
        return 600
