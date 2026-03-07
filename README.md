Here’s a proposed **`README.md`** for the repo based on the code you pasted.

---

````markdown
# ePaper Family Frame System

End-to-end setup for a family ePaper photo frame:

- Crop & manage images via a browser UI.
- Store them centrally in **S3**.
- Sync them onto an SD card on a Raspberry Pi.
- Show them in rotation on a **Waveshare 7-color ePaper display**.
- Control picture mode, refresh interval, and quiet hours via a web-based **Settings** UI.

This repository contains all the pieces to do that.

---

## High-Level Architecture

```text
                   ┌───────────────────────────┐
                   │ ImageUiApp (Streamlit)    │
                   │ - Crop images to 800x480  │
   Laptop / EC2 →  │ - Save crops to S3        │
                   └────────────┬──────────────┘
                                │
                                │ S3 (boto3 / awscli)
                                ▼
                       ┌─────────────────┐
                       │   S3 bucket     │
                       │ e.g. rasp-pi-…  │
                       └────────┬────────┘
                                │  (aws s3 sync, every 15 min)
                                ▼
                  ┌───────────────────────────────┐
                  │ Raspberry Pi (Zero/3/4)       │
                  │                               │
                  │ 1) SD + Wi-Fi / S3 sync:      │
                  │    - /mnt/epaper_sd mounted   │
                  │    - wifi.json on SD          │
                  │    - sd-s3-sync.timer →       │
                  │      sync_s3_from_sd.py →     │
                  │      sync S3 → /mnt/epaper_sd │
                  │                      /s3_folder
                  │                               │
                  │ 2) ePaper display pipeline:   │
                  │    epaper.service → sd_monitor.py
                  │     • watch /mnt/epaper_sd
                  │     • respect quiet hours     │
                  │     • start frame_manager.py  │
                  │          ↳ ImageConverter     │
                  │          ↳ DisplayManager     │
                  │          ↳ waveshare_epd      │
                  │                               │
                  │ 3) Settings UI (Streamlit):   │
                  │    settingsapp.service →      │
                  │    SettingsApp                │
                  │      - writes /mnt/epaper_sd      │
                  │        epaper_settings/settings.json
                  │      - writes /mnt/epaper_sd/ │
                  │        refresh_time.txt       │
                  └───────────────────────────────┘
                                │
                                ▼
                      Waveshare 7-color ePaper
````

---

## Repository Structure

At a high level:

* **`eInkFrameWithStreamlitMananger/`**
  The **display stack** running on the Pi that is physically connected to the ePaper panel
  (mount monitoring, image conversion, display rotation, hardware drivers).

* **`pi-s3-sync/`**
  A small **daemon + timer** that syncs images from S3 **into** an SD card (or another base directory),
  using configuration from `wifi.json` and `nmcli` to manage Wi-Fi.

* **`s3_image_croper_ui_app/`**
  Two Streamlit apps:

  * **ImageUiApp**: Local image cropper that writes final 800×480 images to S3.
  * **SettingsApp**: Web settings UI to control picture mode, interval, and quiet hours.

* **`install_all_pi.sh` / `install_sd_card_reader.sh` / `install_env.sh` / `s3_image_croper_ui_app/install_*.sh`**
  Convenience scripts to provision a Raspberry Pi and an AWS Linux EC2 instance.

* **`src/s3_manager`**
  A small reusable `S3Manager` helper class for managing S3 buckets and syncing to/from local folders.

* **`src/pollock`**
  A script that generates a “Pollock-style” status card as an image, summarising connectivity and settings.

* **`collect_scripts.py`**
  Utility to dump all scripts in the repo into one `ALL_SCRIPTS.txt` (the thing that produced the listing you pasted).

* **`usefull_commands.py`**
  Just a scratchpad of useful systemctl / journalctl / nmcli commands (comments only).

Below you’ll find details for each major subsystem and how they connect.

---

## 1. ePaper Display Stack (`eInkFrameWithStreamlitMananger/`)

This is the part that actually drives the Waveshare ePaper display.

### 1.1 Core components

#### `sd_monitor.py`

* **Responsibility:**
  Long-running process that:

  * Watches for the SD card mount at `/mnt/epaper_sd`.
  * Applies **quiet hours** (no image rotation during the configured interval).
  * Starts and stops `frame_manager.py` as a subprocess when:

    * SD is inserted/removed.
    * Quiet hours start/end.
    * `frame_manager.py` has died.
* **Configuration:**

  * Reads settings from one of:

    * `/etc/epaper_settings/settings.json`
    * `/mnt/epaper_sd/epaper_settings/settings.json`
    * `eInkFrameWithStreamlitMananger/settings.json`
  * Uses defaults if not found.

Key bits:

* `load_settings()` merges any found settings into `DEFAULT_SETTINGS`.
* `get_refresh_time()` determines the **refresh interval** (in seconds) using:

  1. `change_interval_minutes` from settings, if present.
  2. Else `refresh_time.txt` on the SD card.
  3. Else default **600 seconds**.
* `stop_rotation_between` is parsed into two times: `evening`, `morning`.
  `in_quiet_hours(now, evening, morning)` handles both same-day and overnight ranges.

When image rotation should be active:

1. It ensures `/mnt/epaper_sd` is mounted and readable.

2. It calls:

   ```bash
   python3 frame_manager.py /mnt/epaper_sd <refresh_time_sec>
   ```

3. It keeps a handle to the subprocess and restarts or kills it as needed.

#### `frame_manager.py`

* **Responsibility:**
  Bridge between **SD content** and the **display loop**. It:

  1. Decides which directory of images to use, based on `picture_mode` and `s3_folder`.
  2. Clears and recreates a local `pic/` folder.
  3. Uses `ImageConverter` to preprocess/resize images into `pic/`.
  4. Uses `DisplayManager` to:

     * show a boot image (`start.jpg`),
     * then rotate through converted images indefinitely.

* **Settings usage:**

  ```jsonc
  {
    "picture_mode": "local" | "online" | "both",
    "change_interval_minutes": 15,
    "stop_rotation_between": { "evening": "22:00", "morning": "06:00" } | null,
    "s3_folder": "s3_folder"
  }
  ```

* **Source selection logic (`get_effective_source_dir`)**:

  * `picture_mode == "online"`
    → use only: `<SD_PATH>/<s3_folder>`
    (i.e. S3-synced images only)
  * `picture_mode == "local"`
    → use everything on the SD card **except** `<s3_folder>`
    (`build_local_only_source()` creates a filtered copy into `FILTERED_SD_PATH`)
  * `picture_mode == "both"` (or anything else)
    → use full SD tree: `<SD_PATH>`

The effective directory is then fed into `ImageConverter`.

#### `image_converter.py` → `ImageConverter`

* **Responsibility:**
  Convert arbitrary images from `source_dir` into display-ready files in `output_dir`:

  * Supported formats: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tiff`.
  * Skips hidden files.
  * For each image:

    * Rotate according to EXIF.
    * Resize **while preserving aspect ratio** to cover at least 800×480.
    * Center-crop to **exact** 800×480.
    * Enhance color and contrast (1.5× each).
    * Save to `output_dir` with same filename.

The display driver expects images sized to the display resolution (800×480), which is why the conversion pipeline is strict about resizing and cropping.

#### `display_manager.py` → `DisplayManager`

* **Responsibility:**
  Drive the physical ePaper display (Waveshare 7.3" 7-color panel).

* Uses:

  ```python
  from lib.waveshare_epd import epd7in3f
  ```

  * `epd7in3f.EPD().init()` initializes the hardware via SPI + GPIO.
  * `epd.display(epd.getbuffer(pic))` sends a frame to the panel.

* Key features:

  * `display_images()`:

    * Shows a first random image from `image_folder`.
    * Then, in a loop:

      * Sleeps until `refresh_time` seconds have passed.
      * Reloads the list of images in `image_folder`.
      * Chooses a new random image (`select_random_image`) that is **not the same** as last time (if possible).
      * Displays it.
  * `display_message(message_file)`:

    * Loads e.g. `messages/start.jpg` or `messages/no_valid_images.jpg`
      from the script directory and sends it to the panel.
    * This is used for boot / status screens.

#### `lib/waveshare_epd/*`

* Vendor-provided drivers for various Waveshare panels, adapted slightly:

  * `epd7in3f.py`, `epd7in3e.py`, `epd5in65f.py`:

    * Implement the `EPD` class with:

      * `init()`
      * `getbuffer(PIL.Image)`
      * `display(buf)`
      * `Clear()`
      * `sleep()`
  * `epdconfig.py`:

    * Abstracts hardware IO for:

      * Raspberry Pi (default).
      * Jetson Nano.
      * Sunrise X3.
    * Talks to GPIO + SPI via `spidev` and `gpiozero` (on Pi).

You normally don’t touch these unless you switch to a different Waveshare panel.

---

### 1.2 Systemd service for the display

`setup.sh` in `eInkFrameWithStreamlitMananger`:

* Enables SPI and I²C in `/boot/config.txt` and via `raspi-config`.

* Creates a systemd service:

  ```ini
  [Unit]
  Description=ePaper Display Service
  After=network.target mnt-epaper_sd.mount
  Wants=mnt-epaper_sd.mount

  [Service]
  ExecStart=/usr/bin/python3 <repo>/eInkFrameWithStreamlitMananger/sd_monitor.py
  WorkingDirectory=<repo>/eInkFrameWithStreamlitMananger
  Restart=always
  User=<current user>

  [Install]
  WantedBy=multi-user.target
  ```

* Ensures `/mnt/epaper_sd/epaper_settings/settings.json` exists with sane defaults.

* Reloads systemd and enables `epaper.service`.

After running `setup.sh` and rebooting, the Pi:

1. Mounts the SD card at `/mnt/epaper_sd` (see next section).
2. Starts `epaper.service` → `sd_monitor.py`.
3. `sd_monitor.py` starts `frame_manager.py` when conditions are met.
4. The display starts showing images.

---

## 2. SD Card Mount & S3 Sync (`install_sd_card_reader.sh`, `pi-s3-sync/`)

### 2.1 SD card auto-mount at `/mnt/epaper_sd`

`install_sd_card_reader.sh`:

* Scans `/dev/sdX*` for a **vfat** partition that:

  * is not labeled `boot` or `bootfs` (first pass).
  * or, if none found, any vfat partition as a fallback.

* Derives its **UUID** and creates:

  * systemd mount unit: `/etc/systemd/system/mnt-epaper_sd.mount`
  * udev rule: `/etc/udev/rules.d/99-epaper-sd-mount.rules`

* The mount unit:

  ```ini
  [Mount]
  What=/dev/disk/by-uuid/<UUID>
  Where=/mnt/epaper_sd
  Type=vfat
  Options=defaults,uid=<user>,gid=<user>,umask=0022,nofail
  ```

* Effect:

  * On boot, systemd tries to mount the partition at `/mnt/epaper_sd`.
  * On re-plug, udev triggers the mount again.
  * Ownership is set so the non-root user can read/write.

This is the same mount path used by `sd_monitor.py` and `SettingsApp`.

### 2.2 S3 sync service (`pi-s3-sync/`)

The goal here: **sync the S3 bucket down into a folder on the SD card**, typically:

```text
/mnt/epaper_sd/s3_folder
```

#### `scripts/sync_s3_from_sd.py`

**Steps:**

1. **Find `wifi.json`:**

   * Scans `/proc/mounts` for a mount that has `wifi.json` at its root.
   * If none is found:

     * If running as `sudo`, falls back to the **calling user’s home** (`~$SUDO_USER`).
     * Else uses `~` of the current user.
2. **Load configuration** from `wifi.json`:

   * Accepts different key names and environment fallbacks, but logically needs:

     * `aws_access_key_id`
     * `aws_secret_access_key`
     * `s3_bucket`
     * `aws_region` (default `eu-central-1`)
     * `wifi_name` (SSID, optional)
     * `wifi_password` (optional)
3. **Wi-Fi connection (optional):**

   * If `wifi_name` + `wifi_password` provided:

     * Uses `nmcli` to:

       * Check current SSID.
       * Rescan (`nmcli dev wifi rescan`).
       * Connect if not already online:
         `nmcli dev wifi connect <ssid> password <pwd>`
     * This requires:

       * NetworkManager installed and active.
       * The user running the service to be in `netdev` group.
       * A matching polkit rule (installed by `pi-s3-sync/install.sh`).
4. **Prepare sync target:**

   * `target_folder = base_path / "s3_folder"` (usually `/mnt/epaper_sd/s3_folder`).
5. **Run S3 sync:**

   * Using environment variables:

     ```bash
     AWS_ACCESS_KEY_ID
     AWS_SECRET_ACCESS_KEY
     AWS_DEFAULT_REGION
     ```

   * Executes:

     ```bash
     aws s3 sync s3://<bucket> <target_folder> --only-show-errors
     ```

#### `pi-s3-sync/install.sh`

* Installs system dependencies:

  * `awscli`, `python3`, `git`, `network-manager`.
* Ensures NetworkManager is active (best effort).
* Adds user `pi` to `netdev` so it can use `nmcli` via polkit.
* Installs a polkit rule allowing `netdev` users to control NetworkManager.
* Copies:

  * `scripts/sync_s3_from_sd.py` → `/usr/local/bin/`.
  * `systemd/sd-s3-sync.service` and `.timer` → `/etc/systemd/system/`.
* Enables `sd-s3-sync.timer` so sync runs periodically (every 15 minutes).

---

## 3. Image Cropping UI (`s3_image_croper_ui_app/ImageUiApp`)

The **ImageUiApp** is a Streamlit app to:

1. Upload large photos.
2. Interactively crop a fixed-size region (default 800×480).
3. Save the cropped region as PNG to an S3 bucket.

### 3.1 Configuration

* Project config: `ImageUiApp/pyproject.toml`
  Includes dependencies: `streamlit`, `pillow`, `boto3`, `python-dotenv`, etc.
* Environment:

  * Reads `.env` via `python-dotenv` + `pyhere`:

    ```bash
    S3_BUCKET=your-bucket-name
    REGION=eu-central-1
    ```

  * Or set these directly in the environment.

### 3.2 Entry point

`imageuiapp/main.py`:

* CLI:

  ```bash
  poetry run imageuiapp --port 8501 --address 0.0.0.0
  ```

* Internally runs:

  ```bash
  streamlit run imageuiapp/app.py --server.port <port> --server.address <address>
  ```

### 3.3 UI behaviour (`imageuiapp/app.py`)

* Sets page title and layout.
* Displays **internet status** (simple socket check to 8.8.8.8:53).
* Sidebar:

  * File uploader (multiple PNG/JPG/JPEG).
  * Step size for moving the crop window.
  * `max_dim` for optional downscaling before cropping.
  * Output folder / S3 prefix (fixed to `"images"` in the current code).
* Tabs:

  1. **Info** → `tabs/info_tab.py`:

     * Renders `data/intro.md` as Markdown.
  2. **Image management** → `tabs/file_tab.py`:

     * Main cropping UI and S3 upload.
  3. **View** → `tabs/view_tab.py`:

     * View images from S3.
  4. **Downloads** → `tabs/downloads_tab.py`:

     * Download `wifi.json`.
     * Generate a **pre-signed ZIP URL** containing all S3 images under a prefix.

### 3.4 Cropping workflow (`tabs/file_tab.py`)

* Loads images via `PIL.Image`.
* Optional downscale:

  * If image is larger than `resize_max_dim`, scale it down while preserving aspect ratio,
    but **never** to a size smaller than the desired crop (800×480).
* Cropping:

  * Fixed crop size (800×480 by default, clamped if image smaller).
  * Maintains crop position per image in `st.session_state`.
  * Four directional movement buttons + center button.
  * Shows both:

    * Original with red rectangle overlay.
    * Cropped preview.
* Saving:

  * On “Save cropped image”:

    * Saves a PNG to S3 under `output_folder` prefix (`images/`).
    * S3 key includes base name and crop coordinates.
    * Clears Streamlit cache so image lists update.

### 3.5 Viewing & downloads

* `tabs/view_tab.py`:

  * Lists S3 keys under a prefix, caches results.
  * Lets you select a file and shows its contents via PIL.
* `tabs/downloads_tab.py`:

  * **Wi-Fi config download:**

    * Lets you download a `wifi.json` file that you copy onto the SD card root.
  * **ZIP link:**

    * Lists all S3 objects under a prefix.
    * Builds an in-memory ZIP.
    * Uploads ZIP to S3 under `zips/...`.
    * Generates a pre-signed URL to download that ZIP (valid 1 hour).

---

## 4. Settings UI (`s3_image_croper_ui_app/SettingsApp`)

Streamlit app that configures the ePaper behaviour **without SSHing into the Pi**.

### 4.1 Configuration & storage

* Settings live at:

  ```text
  /mnt/epaper_sd/epaper_settings/settings.json
  ```

  Same format used by `sd_monitor.py` and `frame_manager.py`.

* The app also tries to write:

  ```text
  /mnt/epaper_sd/refresh_time.txt
  ```

  whenever you save settings, so the SD card content is self-describing.

### 4.2 Behaviour (`settingsapp/app.py`)

* Checks whether `/mnt/epaper_sd` exists and is a mountpoint.
* Loads the current settings via `load_settings()`, merging with defaults.
* Form fields:

  * **Picture mode**: `local | online | both`
  * **Change interval (minutes)**: `1..1440`.
  * **Online folder** on SD card (`s3_folder`, e.g. `"s3_folder"`).
  * **Quiet hours toggle**:

    * If enabled: `evening` and `morning` time inputs.

On submit:

1. Writes updated `settings.json` to `/mnt/epaper_sd/epaper_settings/`.
2. Computes `interval_seconds = change_interval_minutes * 60`.
3. If SD is mounted:

   * Writes `/mnt/epaper_sd/refresh_time.txt` with `interval_seconds`.
4. Shows status messages in the UI.

`sd_monitor.py` and `frame_manager.py` will pick up these settings on next run.

### 4.3 Systemd integration (`install_settings.sh`)

* Installs `python3`, `python3-pip`, `python3-venv`, `curl`, `awscli`.

* Installs Poetry and project dependencies in `SettingsApp/`.

* Creates a systemd service, `settingsapp.service`:

  ```ini
  [Service]
  User=<current user>
  WorkingDirectory=<repo>/s3_image_croper_ui_app/SettingsApp
  CapabilityBoundingSet=CAP_NET_BIND_SERVICE
  AmbientCapabilities=CAP_NET_BIND_SERVICE
  ExecStart=/bin/bash -lc 'poetry run settingsapp --port 80 --address 0.0.0.0'
  Restart=always
  ```

* Enables and starts the service.

After that, the settings UI is available at:

```text
http://<pi-ip>/
```

---

## 5. Status Image Generator (`src/pollock/pollock_text.py`)

This script creates a “status card” image (Pollock-style background with clean text overlay) summarising:

* Whether the Pi has internet connectivity.
* Current `epaper_settings` settings.
* Hostname and how to access the settings UI.

### 5.1 How it works

* Reads `/mnt/epaper_sd/epaper_settings/settings.json` (same as the other components).

* Checks internet via a simple socket call to `8.8.8.8:53`.

* Builds a multi-line status text, e.g.:

  ```text
  Internet active.
  Current settings: mode=both, interval=15min, s3=s3_folder, quiet=22:00–06:00
  Change settings unter http://<hostname>/ in the browser.
  ```

* Renders:

  * Pollock-style background (lots of lines & dots, blurred).
  * White rounded rectangle card in the center.
  * Centered multi-line text in a serif font.

* Outputs a downscaled 800×480 PNG: `text.png`.

You can:

* Copy `text.png` into `eInkFrameWithStreamlitMananger/messages/` and use it as a boot/status image via `display_manager.display_message(...)`.

---

## 6. Generic S3 Helper (`src/s3_manager/S3Manager`)

`S3Manager` is a reusable, testable abstraction around `boto3`:

* `check_connection()`:

  * `head_bucket` and a tiny `list_objects_v2` with `MaxKeys=1` to validate access.
* `put_file(local_path, key=None)`:

  * Upload a single file to `bucket_name/prefix/...`.
* `sync_bucket_to_local(local_dir, delete_extraneous_local=False, overwrite_existing=True)`:

  * Download a whole prefix from S3.
  * Optionally delete local files not in S3.
* `sync_local_to_bucket(local_dir, delete_extraneous_remote=False, overwrite_existing=True)`:

  * Upload an entire local folder into the S3 prefix.
  * Optionally delete S3 objects that are no longer present locally.

This is not directly used by the ePaper pipeline (which uses `aws s3 sync` and explicit `boto3` calls in the Streamlit apps), but is included as a utility for future enhancements.

---

## 7. End-to-End Flow

Putting it all together:

1. **Prepare images & Wi-Fi config**

   * Run **ImageUiApp** (locally or on an EC2 instance).
   * Upload and crop images → saved as 800×480 PNG into S3 bucket under `images/` (or the chosen prefix).
   * From the **Downloads** tab, download `wifi.json` and fill in:

     * `wifi_name`, `wifi_password`
     * `aws_access_key_id`, `aws_secret_access_key`
     * `s3_bucket`, `aws_region`
   * Copy `wifi.json` onto the root of the SD card that will go into the Pi.

2. **Set up the Pi**

   > **For a complete step-by-step guide, see [docs/pi-install-guide.md](docs/pi-install-guide.md).**

   * Copy the repo to the Pi via `scp` (preferred) or clone it.

   * Run:

     ```bash
     ./install_all_pi.sh
     ```

     This:

     * Adds environment exports (edit the placeholder values in `install_env.sh` first!).
     * Sets up the `/mnt/epaper_sd` mount.
     * Installs `pi-s3-sync` service + timer.
     * Installs and enables the **SettingsApp** service.

   * Go into `eInkFrameWithStreamlitMananger/` and run:

     ```bash
     ./setup.sh
     ```

     This:

     * Enables SPI / I²C.
     * Creates and enables the `epaper.service` that runs `sd_monitor.py`.

   * Reboot the Pi.

3. **Insert SD card**

   * Plug the prepared SD card (with `wifi.json`) into the Pi.
   * On boot / insertion:

     * `/mnt/epaper_sd` is mounted.
     * `sd-s3-sync.timer` periodically runs `sync_s3_from_sd.py`:

       * Ensures Wi-Fi connectivity (if configured).
       * Syncs the S3 bucket into `/mnt/epaper_sd/s3_folder`.
     * `epaper.service` runs `sd_monitor.py`:

       * Detects the SD card and quiet hours.
       * Starts `frame_manager.py` with the appropriate refresh interval.

4. **Display images**

   * `frame_manager.py`:

     * Loads `settings.json` to decide `picture_mode` and `s3_folder`.
     * Decides which part of the SD tree to use.
     * Converts images into `eInkFrameWithStreamlitMananger/pic/`.
     * Shows `messages/start.jpg` as a boot image.
     * Starts `DisplayManager.display_images()` which rotates through pics.

5. **Adjust settings**

   * Open a browser on your laptop:

     * `http://<pi-ip>/`
   * Use **SettingsApp** to:

     * Switch between `local / online / both`.
     * Adjust change interval.
     * Configure quiet hours.
   * On save:

     * `/mnt/epaper_sd/epaper_settings/settings.json` is updated.
     * `refresh_time.txt` on the SD card is written if available.
   * The next (re)run of `sd_monitor.py` / `frame_manager.py` picks these up.

---

## 8. Security & Credentials

A couple of important notes:

* **Never commit real AWS credentials** to Git.

  * The `install_env.sh` files contain placeholders; replace them **locally** and never push secrets.
* Prefer using:

  * `wifi.json` on the SD card for **this Pi only**.
  * Or `aws configure` and IAM roles where possible.
* Ensure your S3 bucket has appropriate access policies; the Pi only needs access to:

  * List and read objects (for sync).
  * Possibly write ZIPs (from ImageUiApp’s Downloads tab).

---

## 9. Useful Commands

From `usefull_commands.py` (translated from comments):

```bash
# Start S3 import service manually
sudo systemctl start sd-s3-sync.service

# View S3 sync logs
journalctl -u sd-s3-sync.service

# Wi-Fi info via nmcli
nmcli device wifi list
# or
nmcli dev wifi

# Rescan Wi-Fi networks
sudo nmcli device wifi rescan
```

---

## 10. Summary

This repo gives you a **full pipeline**:

1. **Create & curate images** via a Streamlit cropper UI.
2. **Store them centrally in S3.**
3. **Sync them to an SD card** on a Pi (with Wi-Fi auto-config).
4. **Display them on a Waveshare ePaper**, with quiet hours and picture modes.
5. **Control everything via a Web Settings UI**, without touching the terminal.

All roles (cropper, settings, sync, display) can run on one Pi or be split across devices, depending on your performance and network requirements.

```

::contentReference[oaicite:0]{index=0}
```
