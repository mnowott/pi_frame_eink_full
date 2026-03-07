# SettingsApp/app.py
import os
import json
from datetime import time
from pathlib import Path

import streamlit as st

# -------------------------------------------------------------------
# Paths: SD-card primary config + legacy home backup
# -------------------------------------------------------------------

# Fixed SD card mount path (managed by systemd mount unit)
SD_MOUNT_PATH = Path("/mnt/epaper_sd")

# New canonical settings location on the SD card
SD_CONFIG_DIR = SD_MOUNT_PATH / "epaper_settings"
SD_SETTINGS_PATH = SD_CONFIG_DIR / "settings.json"

# Legacy / backup location in the user's home dir
HOME_CONFIG_DIR = Path.home() / ".config" / "epaper_frame"
HOME_SETTINGS_PATH = HOME_CONFIG_DIR / "settings.json"

# Default settings
DEFAULT_SETTINGS = {
    "picture_mode": "local",          # local | online | both
    "change_interval_minutes": 15,    # integer minutes
    "stop_rotation_between": None,    # or {"evening": "HH:MM", "morning": "HH:MM"}
    "s3_folder": "s3_folder",
}


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def sd_mount_available() -> bool:
    """
    Check if the fixed SD mount path looks available.

    We treat it as available if:
      - the path exists, and
      - it's a mountpoint (best-effort check).
    """
    return SD_MOUNT_PATH.exists() and os.path.ismount(str(SD_MOUNT_PATH))


def get_primary_settings_path() -> Path:
    """
    Return the "active" settings path:
      - SD card path if the SD is mounted
      - otherwise the legacy home config path
    """
    if sd_mount_available():
        return SD_SETTINGS_PATH
    return HOME_SETTINGS_PATH


def load_settings() -> dict:
    """
    Load settings, preferring the SD card config if available.

    Fallback order:
      1) /mnt/epaper_sd/epaper_settings/settings.json   (persistent)
      2) ~/.config/epaper_frame/settings.json           (legacy / backup)
    """
    settings = DEFAULT_SETTINGS.copy()
    primary = get_primary_settings_path()

    # 1) Try the primary path first (SD or home, depending on mount)
    if primary.exists():
        try:
            with primary.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                settings.update(data)
            return settings
        except Exception as e:
            st.warning(f"Could not read settings file {primary}: {e}")

    # 2) If primary is SD and it's empty, check legacy home config,
    #    so older installs get migrated on next save.
    if primary == SD_SETTINGS_PATH and HOME_SETTINGS_PATH.exists():
        try:
            with HOME_SETTINGS_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                settings.update(data)
            st.info(
                f"Loaded legacy settings from {HOME_SETTINGS_PATH}. "
                "They will be written to the SD card next time you click 'Save'."
            )
        except Exception as e:
            st.warning(f"Could not read legacy home settings: {e}")

    return settings


def save_settings(settings: dict):
    """
    Save settings, preferring the SD card, and keeping a home backup.

    - If SD is mounted:
        - Write to /mnt/epaper_sd/epaper_settings/settings.json
        - Also write a backup to ~/.config/epaper_frame/settings.json
    - If SD is NOT mounted:
        - Only write to ~/.config/epaper_frame/settings.json
          (on overlayfs this may not survive a reboot)
    """
    # 1) SD card: primary, persistent storage
    if sd_mount_available():
        try:
            SD_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with SD_SETTINGS_PATH.open("w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            st.success(f"Settings saved to SD card at {SD_SETTINGS_PATH}")
        except Exception as e:
            st.error(f"Failed to save settings to SD card {SD_SETTINGS_PATH}: {e}")
    else:
        st.warning(
            "SD card is not mounted; settings will only be written to "
            f"{HOME_SETTINGS_PATH}. On a read-only root with overlay, "
            "this may not survive a reboot."
        )

    # 2) Home backup (even if SD is there, this is harmless)
    try:
        HOME_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with HOME_SETTINGS_PATH.open("w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        st.warning(
            f"Additionally failed to save backup settings at {HOME_SETTINGS_PATH}: {e}"
        )


def parse_time_str(value: str | None, fallback: time) -> time:
    if not value:
        return fallback
    try:
        hour, minute = map(int, value.split(":"))
        return time(hour=hour, minute=minute)
    except Exception:
        return fallback


# -------------------------------------------------------------------
# Streamlit UI
# -------------------------------------------------------------------

def main():
    st.title("ePaper Frame Settings")

    settings = load_settings()
    active_path = get_primary_settings_path()

    st.write(f"Active settings file: `{active_path}`")
    st.write(f"SD settings path: `{SD_SETTINGS_PATH}`")
    st.write(f"Home backup path: `{HOME_SETTINGS_PATH}`")

    # SD mount status info
    if sd_mount_available():
        st.success(f"SD card mount detected at `{SD_MOUNT_PATH}`.")
    else:
        st.warning(
            f"SD card mount `{SD_MOUNT_PATH}` not found or not mounted.\n\n"
            "Make sure the USB SD reader is plugged in and the mount service is installed."
        )

    picture_modes = ["local", "online", "both"]
    current_mode = settings.get("picture_mode", DEFAULT_SETTINGS["picture_mode"])
    try:
        mode_index = picture_modes.index(current_mode)
    except ValueError:
        mode_index = 0

    stop_between = settings.get("stop_rotation_between")

    # Defaults for time inputs
    default_evening = parse_time_str(
        stop_between.get("evening") if stop_between else None,
        fallback=time(22, 0),
    )
    default_morning = parse_time_str(
        stop_between.get("morning") if stop_between else None,
        fallback=time(6, 0),
    )

    with st.form("settings_form"):
        picture_mode = st.selectbox(
            "Picture mode",
            picture_modes,
            index=mode_index,
            format_func=lambda x: x.capitalize(),
            help=(
                "local: all images on the SD card except the 'online' folder\n"
                "online: only images inside the 'online' folder on the SD card\n"
                "both: all images on the SD card"
            ),
        )

        change_interval_minutes = st.number_input(
            "Picture change interval (minutes)",
            min_value=1,
            max_value=24 * 60,
            value=int(settings.get("change_interval_minutes", 15)),
            step=1,
        )

        # For now always keep default folder name for "online" images
        # s3_folder = st.text_input(
        #     "Online folder on SD card",
        #     value=settings.get("s3_folder", DEFAULT_SETTINGS["s3_folder"]),
        #     help="Folder name under the SD card root that contains 'online' images (e.g. 's3_folder').",
        # )

        enable_quiet_hours = st.checkbox(
            "Stop rotation between evening and morning",
            value=stop_between is not None,
        )

        evening_time = None
        morning_time = None

        if enable_quiet_hours:
            evening_time = st.time_input(
                "Evening time (stop rotation after)",
                value=default_evening,
            )
            morning_time = st.time_input(
                "Morning time (resume rotation at)",
                value=default_morning,
            )

        submitted = st.form_submit_button("Save")

    if submitted:
        new_settings = {
            "picture_mode": picture_mode,
            "change_interval_minutes": int(change_interval_minutes),
            "stop_rotation_between": None,
            "s3_folder": "s3_folder",  # always keep default for now
        }

        if enable_quiet_hours and evening_time and morning_time:
            new_settings["stop_rotation_between"] = {
                "evening": evening_time.strftime("%H:%M"),
                "morning": morning_time.strftime("%H:%M"),
            }

        # 1) Save settings (SD + home backup)
        save_settings(new_settings)

        # 2) Write refresh_time.txt to the SD root (as before)
        interval_seconds = int(change_interval_minutes) * 60
        refresh_file = SD_MOUNT_PATH / "refresh_time.txt"

        if sd_mount_available():
            try:
                with refresh_file.open("w", encoding="utf-8") as f:
                    f.write(str(interval_seconds))
                st.success(
                    f"refresh_time.txt written to {refresh_file} "
                    f"with value {interval_seconds} seconds."
                )
            except Exception as e:
                st.error(
                    f"Failed to write refresh_time.txt to {SD_MOUNT_PATH}: {e}"
                )
        else:
            st.info(
                f"Skipping creation of refresh_time.txt because `{SD_MOUNT_PATH}` "
                "is not available as a mount."
            )


if __name__ == "__main__":
    main()
