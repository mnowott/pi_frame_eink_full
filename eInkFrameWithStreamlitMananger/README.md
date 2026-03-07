Here’s a full, updated README you can drop into the repo (e.g. as `README.md`) that already includes the **Option 1** behavior (SD content change detection + restart):

````markdown
# Raspberry Pi ePaper Frame – Display Manager

This project turns a Raspberry Pi and a Waveshare 7.3" e-paper panel into a “digital picture frame” that:

- Rotates through images stored on an SD card
- Resizes and enhances them for the panel
- Supports **local / online / both** picture modes
- Supports **quiet hours** where rotation is paused
- Shows a **Pollock-style status card** when there are no valid images or for diagnostics
- Automatically detects **changes on the SD card** and refreshes images accordingly

The core scripts live under:

```text
/home/nowottnm/repo/eInkFrameWithStreamlitMananger
````

---

## 1. Architecture Overview

At a high level:

1. **System boot**

   * `setup.sh` installs a `systemd` service `epaper.service`.
   * This service runs `sd_monitor.py`.

2. **SD card monitoring (`sd_monitor.py`)**

   * Watches `/mnt/epaper_sd` for an inserted / mounted SD card.
   * Reads configuration from `settings.json` (global or per-user).
   * Enforces *quiet hours* (optional).
   * Starts / stops `frame_manager.py` as needed.
   * Periodically scans the SD card for **content changes** and restarts `frame_manager.py` if something changed (Option 1).

3. **Frame & image management (`frame_manager.py`)**

   * Decides **which part of the SD card** is used based on `picture_mode` and `s3_folder`:

     * `both`  → all images under the SD root
     * `online` → only `<SD root>/<s3_folder>`
     * `local` → everything under SD root **except** the `s3_folder` subtree (via a filtered copy)
   * Clears and recreates a local working directory `./pic/`.
   * Uses `ImageConverter` to copy + convert all images from the SD selection into `./pic/`.
   * Instantiates `DisplayManager` to actually talk to the panel and rotate images from `./pic/`.

4. **Display handling (`display_manager.py`)**

   * Initializes the Waveshare driver (`lib/waveshare_epd/epd7in3f.py`).
   * Shows a boot image (`messages/start.jpg`) followed by the default settings pollock status.
   * Rotates random images from `./pic/` every N seconds (refresh_time).
   * If `./pic/` is empty, shows a Pollock-style status card (if `pollock_text` is available) or a fallback image.

5. **Pollock status generator (`pollock_text.py`)**

   * Produces a time-of-day dependent Pollock-style background.
   * Renders a centered white text card with:

     * Internet status
     * Current settings (mode, interval, etc.)
     * How to reach the web UI (hostname-based URL).

---

## 2. Directory Layout

Key files and folders:

```text
.
├── display_manager.py          # High-level display loop
├── frame_manager.py            # SD → filtered source → ./pic + DisplayManager
├── image_converter.py          # Resize/crop/enhance images for panel
├── pollock_text.py             # Pollock-style status card generator
├── sd_monitor.py               # Systemd-driven monitor for SD card & changes
├── setup.sh                    # One-time setup script for systemd & SPI/I2C
├── pyproject.toml              # Poetry configuration (for S3 manager utilities)
├── messages/                   # (Expected) static message images, e.g. start.jpg
├── pic/                        # Working directory: converted display-ready images
├── sd_filtered/                # Working dir for "local-only" content when using picture_mode=local
└── lib/
    └── waveshare_epd/          # Waveshare driver + epdconfig
        ├── __init__.py
        ├── epd5in65f.py
        ├── epd7in3e.py
        ├── epd7in3f.py
        └── epdconfig.py
```

> Note: `pic/` and `sd_filtered/` are created at runtime by `frame_manager.py`.

---

## 3. Configuration: `settings.json`

Settings are loaded from the first existing file in:

1. `/etc/epaper_frame/settings.json`
2. `~/.config/epaper_frame/settings.json`
3. `<repo>/settings.json`

Both **`sd_monitor.py`** and **`frame_manager.py`** share the same defaults:

```json
{
  "picture_mode": "local",          // "local" | "online" | "both"
  "change_interval_minutes": 15,    // interval in minutes between image changes
  "stop_rotation_between": null,    // or {"evening": "HH:MM", "morning": "HH:MM"}
  "s3_folder": "s3_folder"          // SD subfolder treated as “online” content
}
```

### 3.1 `picture_mode`

* `"both"`
  Use all images on the SD card (`sd_path`).

* `"online"`
  Use only images under `<sd_path>/<s3_folder>`.

* `"local"`

  * Build a **filtered mirror** of the SD card under `./sd_filtered/`, excluding the `s3_folder` subtree.
  * Display images from this filtered copy (local-only content).

`frame_manager.py` handles this logic via:

* `get_effective_source_dir(sd_path, settings)`
* `build_local_only_source(sd_path, s3_folder_name)` (for `picture_mode="local"`)

### 3.2 `change_interval_minutes`

* Primary way to set the display rotation interval.
* Used by `sd_monitor.get_refresh_time()` to compute the **refresh time in seconds**.
* If not set or invalid, falls back to `refresh_time.txt` on the SD card (see below), and finally to 600 seconds (10 minutes).

### 3.3 `stop_rotation_between`

Optional quiet-hours configuration:

```json
"stop_rotation_between": {
  "evening": "22:00",
  "morning": "07:00"
}
```

* `sd_monitor.py` parses this (`parse_stop_rotation_between`) and uses `in_quiet_hours` to determine if the Pi is in quiet hours.
* Behavior:

  * When entering quiet hours → **stop `frame_manager.py`**.
  * While in quiet hours → panel shows the last image, no rotation.
  * When quiet hours end → **restart `frame_manager.py`**, reprocessing the SD content.

### 3.4 `s3_folder`

* Logical name of a subfolder on the SD card where “online” (cloud-synced) content lives.
* Example SD structure:

```text
/mnt/epaper_sd
├── local_photos/
├── holidays/
└── s3_folder/        # Online content that may be synced from S3
```

---

## 4. SD Card Layout & Refresh Time

### 4.1 Mount point

* SD card is expected to be mounted at:

```text
/mnt/epaper_sd
```

* A corresponding `systemd` mount unit such as `mnt-epaper_sd.mount` is expected to be configured at the OS level.
* `sd_monitor.py` only checks `.ismount()` and access permissions; it does *not* perform the mount itself.

### 4.2 Optional `refresh_time.txt`

Secondary way to set the rotation interval, used **only if** `change_interval_minutes` in `settings.json` is missing/invalid.

* Path: `/mnt/epaper_sd/refresh_time.txt`
* Contents: a single integer, e.g. `900` (seconds).
* If invalid or missing, defaults to **600 seconds**.

---

## 5. Why the `/pic` Directory?

The `/pic` folder (actually `PIC_PATH = <repo>/pic`) is a **local staging area** for images:

1. **Normalization**
   `ImageConverter` resizes, crops, and enhances arbitrary input images to **exactly** the panel resolution (800x480) and a suitable color/contrast profile.

2. **Separation of concerns**

   * SD card can contain any random content (nested folders, large images, too many colors, etc.).
   * `DisplayManager` only ever sees **clean, ready-to-display** images in one place.

3. **Robustness**

   * If the SD card is removed, the Pi can still display whatever is in `./pic` (i.e. the last converted set).
   * The e-paper itself retains the last image even if nothing is running.

Each run of `frame_manager.py`:

* Deletes and recreates `./pic`.
* Converts all valid source images into that directory.
* Then starts rotating them on the display.

---

## 6. Do SD Updates Get Picked Up Automatically?

### 6.1 DisplayManager’s behavior

`DisplayManager` works only on the **working directory** you gave it (`image_folder = PIC_PATH`):

* At startup:

  * Reads the list of files from `image_folder` (`fetch_image_files`).
  * Picks a random image and displays it.
* In the rotation loop:

  * Every `refresh_time` seconds, it **re-reads** `image_folder` (via `fetch_image_files` again).
  * So it *does* notice new or deleted images **in `./pic/`**.

However, by default:

* `DisplayManager` **does not look at the SD card**.
* It has no idea what happens under `/mnt/epaper_sd` directly.

### 6.2 New behavior (Option 1) in `sd_monitor.py`

To make SD card updates propagate into `./pic/`, `sd_monitor.py` now:

1. Keeps a baseline **“latest file mtime”** for the SD card tree:

   ```python
   last_tree_mtime = compute_tree_mtime(sd_path)
   ```

2. Every 30 seconds (configurable via `MTIME_CHECK_INTERVAL` in code):

   * Scans the SD tree again using `compute_tree_mtime(sd_path)`.
   * If the newest mtime has **increased**, it assumes something changed:

     * New image added
     * Image replaced
     * File deleted or modified

3. On detection of a change:

   * Logs: `Detected change on SD card, restarting frame_manager...`
   * Calls `start_frame_manager(sd_path, settings)`:

     * Stops the old `frame_manager.py` process (and thus the old `DisplayManager`).
     * Starts a new one, which:

       * Rebuilds `./pic` from the **current** SD contents.
       * Restarts the rotation based on the updated images.

Result:

> **Yes, SD card updates are noticed now.**
> The monitor process picks up changes on the SD card and triggers a full reprocess, which then flows into the display rotation via the refreshed `./pic` directory.

---

## 7. Script-by-Script Overview

### 7.1 `sd_monitor.py`

Responsibilities:

* Ensure `/mnt/epaper_sd` directory exists (`cleanup_stale_mounts()`).
* Monitor:

  * SD presence (`os.path.ismount(SD_PATH)` + access).
  * Quiet hours (`stop_rotation_between`).
  * SD content changes (via `compute_tree_mtime`).
* Start / stop `frame_manager.py` as appropriate using `subprocess.Popen`.

Key behaviors:

* On SD insert:

  * Calls `start_frame_manager(sd_path, settings)`.
  * Stores the initial SD content mtime baseline.
* On SD remove:

  * Stops `frame_manager.py`.
* On entering quiet hours:

  * Stops `frame_manager.py`.
* On leaving quiet hours:

  * Restarts `frame_manager.py` and refreshes `./pic`.
* On SD content change:

  * Restarts `frame_manager.py` to regenerate `./pic`.

### 7.2 `frame_manager.py`

Command-line usage:

```bash
python3 frame_manager.py <sd_path> <refresh_time_sec>
```

Responsibilities:

1. Load `settings.json` via `load_settings()`.
2. Choose SD **source directory** via `get_effective_source_dir(sd_path, settings)`:

   * `both`  → `sd_path`
   * `online` → `os.path.join(sd_path, s3_folder)`
   * `local` → filtered copy under `sd_filtered/` (excludes `s3_folder` subtree)
3. Recreate `PIC_PATH = ./pic/`.
4. Instantiate:

   * `DisplayManager(image_folder=PIC_PATH, refresh_time=refresh_time_sec)`
   * `ImageConverter(source_dir=effective_source_dir, output_dir=PIC_PATH)`
5. Show boot screen:

   * `display_manager.display_message('start.jpg')` (from `messages/start.jpg`).
6. Run conversion:

   * `image_converter.process_images()`
7. Start rotation:

   * `display_manager.display_images()`

### 7.3 `display_manager.py`

Core behaviors:

* Initializes the Waveshare 7.3" driver (`epd7in3f.EPD()`).
* Manages rotation:

```python
images = self.fetch_image_files()  # os.listdir(image_folder)
random_image = self.select_random_image(images)
# ...
while not self.stop_display:
    if elapsed_time >= self.refresh_time:
        images = self.fetch_image_files()  # picks up new files in ./pic
        random_image = self.select_random_image(images)
        self._display_pil_image(pic)
```

* Fallback logic:

  * If no images in the folder:

    * If `pollock_text` import succeeded → `display_pollock_status()`
    * Else → `display_message('no_valid_images.jpg')`

### 7.4 `image_converter.py`

What it does:

* Scans the `source_dir` for valid image formats:

  * `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tiff`
* Skips hidden files (`.`-prefixed).
* For each image:

  * Corrects EXIF orientation.
  * Resizes to fit 800x480 while keeping aspect ratio.
  * Crops to exactly 800x480 (center-crop).
  * Enhances colors & contrast (`ImageEnhance.Color` + `ImageEnhance.Contrast` with factor 1.5).
  * Saves into `output_dir` (usually `./pic/`).

### 7.5 `pollock_text.py`

* Builds time-of-day dependent palettes:

  * early_morning
  * late_morning
  * afternoon_golden
  * evening_night
* Renders:

  * Pollock-style background with strokes and dots.
  * A white rounded rectangle “card” with auto-wrapped text.
  * Text includes:

    * Internet status (`has_internet()` via a connection to `8.8.8.8:53`).
    * Settings summary (`summarize_settings(load_settings())`).
    * Hostname-based link (for use with a browser GUI).

Used by `DisplayManager.display_pollock_status()`.

### 7.6 `lib/waveshare_epd/*`

* Vendor driver code for:

  * 5.65" panel (`epd5in65f.py`)
  * 7.3" panels (`epd7in3e.py`, `epd7in3f.py`)
  * Hardware abstraction (`epdconfig.py`) for:

    * Raspberry Pi
    * Jetson Nano
    * SunriseX3

You normally don’t need to modify these unless you change hardware.

### 7.7 `setup.sh`

One-time installation script:

1. Enables SPI and I2C via `raspi-config` and `/boot/config.txt`.
2. Writes a `systemd` service:

```ini
[Unit]
Description=ePaper Display Service
After=network.target mnt-epaper_sd.mount
Wants=mnt-epaper_sd.mount

[Service]
ExecStart=/usr/bin/python3 <repo>/sd_monitor.py
WorkingDirectory=<repo>
Restart=always
User=<current user>

[Install]
WantedBy=multi-user.target
```

3. Creates a default `~/.config/epaper_frame/settings.json` if missing.
4. Enables the service (`systemctl enable epaper.service`).
5. Prompts for reboot.

---

## 8. Manual Running & Debugging

### 8.1 Run the monitor directly

```bash
python3 sd_monitor.py
```

You’ll see logs for:

* SD detect/remove
* Quiet hours
* Starting/stopping frame_manager
* SD content change detection

### 8.2 Run the frame manager directly

Useful if you just want to test the display logic for a given SD folder:

```bash
python3 frame_manager.py /mnt/epaper_sd 600
```

* Processes images from `/mnt/epaper_sd` according to `picture_mode`.
* Writes converted images into `./pic`.
* Starts rotating them every 600 seconds.

---

## 9. FAQ

### Q: Why is there a separate `/pic` folder?

Because it acts as a **clean, preprocessed, panel-ready cache**:

* All images are guaranteed to:

  * Be 800x480.
  * Have appropriate contrast and color treatment.
* The display code doesn’t need to worry about EXIF, resolutions, or nested directories.
* It also decouples SD I/O from display I/O.

### Q: Will the frame notice if I change images on the SD card?

Yes, with the updated `sd_monitor.py`:

* Changes on the SD card (add/remove/overwrite files) update its latest modification time.
* `sd_monitor.py` compares this value every ~30 seconds.
* If it changed:

  * `frame_manager.py` is restarted.
  * `./pic` is rebuilt from the new SD contents.
  * `DisplayManager` is re-created and starts rotating through the updated images.

Within a short window, new images you copy onto the SD card will join the rotation automatically.

