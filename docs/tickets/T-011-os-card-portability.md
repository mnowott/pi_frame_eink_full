# T-011: OS SD card not portable between identical Pi hardware

Status: Closed
Last updated: 2026-03-14

## Problem

An OS SD card set up on one Raspberry Pi does not work when moved to another identical Pi (same model, same display wiring). The system should be fully portable between identical hardware, but multiple install-time values are baked into systemd units and config files, tying the card to the original device.

## Audit Findings

### CRITICAL — Will break on card swap

#### 1. Data SD card UUID hardcoded in mount unit and udev rule

**Files:**
- [install_sd_card_reader.sh:106](install_sd_card_reader.sh#L106) — `What=/dev/disk/by-uuid/$UUID`
- [install_sd_card_reader.sh:126](install_sd_card_reader.sh#L126) — `ENV{ID_FS_UUID}=="$UUID"`

**What happens:** At install time, the physical data SD card's UUID is detected and written into the systemd mount unit (`mnt-epaper_sd.mount`) and udev rule (`99-epaper-sd-mount.rules`). If the new Pi uses a different data SD card (different UUID), the mount silently fails — no images load, no settings found.

**Why this is likely your issue:** This is the single most fragile point. Even two "identical" SD cards from the same batch have different UUIDs.

#### 2. `User=pi` hardcoded in S3 sync service

**File:** [pi-s3-sync/systemd/sd-s3-sync.service:9](pi-s3-sync/systemd/sd-s3-sync.service#L9)

**What happens:** `User=pi` and `Group=pi` are hardcoded in the checked-in service file. If the target Pi uses a different username (e.g. newer Raspberry Pi OS defaults prompt for a username instead of creating `pi`), the service fails to start.

#### 3. `User=pi` hardcoded in pi-s3-sync install.sh

**File:** [pi-s3-sync/install.sh:40-44](pi-s3-sync/install.sh#L40-L44)

**What happens:** The install script hardcodes `pi` when adding to the `netdev` group (`id -nG pi`, `sudo usermod -aG netdev pi`). Fails on non-`pi` usernames.

#### 4. User + absolute paths baked into epaper.service at install time

**File:** [eInkFrameWithStreamlitMananger/setup.sh:58-98](eInkFrameWithStreamlitMananger/setup.sh#L58-L98)

**What happens:** The generated `/etc/systemd/system/epaper.service` contains:
- `User=${CURRENT_USER}` (line 70)
- `ExecStart=${VENV_DIR}/bin/python ${REPO_DIR}/sd_monitor.py` (line 65) — e.g. `/home/pi/epaper-venv/bin/python /home/pi/repo/pi_project/eInkFrameWithStreamlitMananger/sd_monitor.py`

These are absolute paths resolved at install time. If the card moves to a Pi with a different username or different repo checkout location, the service can't find the venv or the script.

#### 5. User + absolute paths baked into settingsapp.service at install time

**File:** [s3_image_croper_ui_app/install_settings.sh:103-143](s3_image_croper_ui_app/install_settings.sh#L103-L143)

**What happens:** The generated service contains:
- `User=$CURRENT_USER` (line 110)
- `WorkingDirectory=$SCRIPT_DIR/SettingsApp` (line 111) — absolute path to repo
- `ReadWritePaths=$CURRENT_HOME/.config/epaper_settings` (line 138)
- `ReadWritePaths=$CURRENT_HOME/.cache` (line 139)

Same issue: paths are install-time snapshots.

#### 6. AWS env vars baked into ~/.bashrc

**File:** [install_env.sh:40-43](install_env.sh#L40-L43)

**What happens:** AWS credentials are appended to the installing user's `~/.bashrc`. The S3 sync service uses `/etc/epaper-settings/s3-sync.env` (good), but the SettingsApp service uses `bash -lc` which sources `~/.bashrc` — so the credentials are tied to the specific user's home directory.

### HIGH — Will likely break on different Pi models

#### 7. GPIO device paths hardcoded in epaper.service

**File:** [eInkFrameWithStreamlitMananger/setup.sh:86-90](eInkFrameWithStreamlitMananger/setup.sh#L86-L90)

```
DeviceAllow=/dev/spidev0.0 rw
DeviceAllow=/dev/spidev0.1 rw
DeviceAllow=/dev/gpiomem rw
DeviceAllow=/dev/gpiochip0 rw
DeviceAllow=/dev/gpiochip4 rw
```

On different Pi models or kernel versions, GPIO chip numbering can differ (`gpiochip4` exists on Pi 5, not on Zero 2W). The service will fail with device-not-found errors.

#### 8. SPI bus hardcoded in driver code

**File:** `eInkFrameWithStreamlitMananger/lib/waveshare_epd/epdconfig.py` — `self.SPI.open(0, 0)`

Hardcoded to SPI bus 0, device 0. Won't break between identical models, but prevents using alternative SPI buses.

### MEDIUM — May cause confusion or partial failures

#### 9. Hostname shown on ePaper status screen

**File:** `eInkFrameWithStreamlitMananger/pollock_text.py` — uses `socket.gethostname()`

Not a breakage, but the display will show the old Pi's hostname in the "change settings at http://..." URL.

#### 10. OverlayFS state in boot config

**File:** [final_hardening.sh:233-243](final_hardening.sh#L233-L243)

`raspi-config nonint enable_overlayfs` modifies `/boot/config.txt` and initramfs. This state *does* transfer with the SD card, but makes debugging harder — any fix you apply after booting is lost on reboot. If the card doesn't work on the new Pi, you can't even persist diagnostic changes without disabling OverlayFS first.

#### 11. Boot config path differs between Pi OS versions

**File:** [final_hardening.sh:30-33](final_hardening.sh#L30-L33) and [eInkFrameWithStreamlitMananger/setup.sh:5-6](eInkFrameWithStreamlitMananger/setup.sh#L5-L6)

`final_hardening.sh` correctly checks both `/boot/config.txt` and `/boot/firmware/config.txt`. But `setup.sh` hardcodes `/boot/config.txt` only. On newer Pi OS (Bookworm+), the config is at `/boot/firmware/config.txt`, so SPI/I2C enablement may silently fail.

## Root Cause Summary

The core issue is that **install scripts resolve values at install time and bake them into systemd units**. This creates a tight coupling between the OS image and:
1. The specific data SD card (UUID)
2. The specific Unix user (username + home path)
3. The specific repo checkout location (absolute path)
4. The specific GPIO/SPI hardware (device numbering)

## Fix Plan

### Phase 1: Make data SD mount hardware-agnostic (fixes #1)

**Change:** Replace UUID-based mounting with filesystem-label-based mounting.

- Modify `install_sd_card_reader.sh` to:
  - Label the data SD card with a known label (e.g. `EPAPER_SD`) using `fatlabel`
  - Use `What=/dev/disk/by-label/EPAPER_SD` in the mount unit
  - Use `ENV{ID_FS_LABEL}=="EPAPER_SD"` in the udev rule
- Add a helper script `label_sd_card.sh` that labels any data SD card for use with the system
- Document that new data SD cards need the label applied before use

### Phase 2: Eliminate hardcoded usernames (fixes #2, #3, #4, #5, #6)

**Change:** Use systemd specifiers and runtime detection instead of baked-in values.

- **sd-s3-sync.service:** Replace `User=pi` / `Group=pi` with a variable set at install time from `$SUDO_USER`, or use a dedicated `epaper` system user created during install
- **pi-s3-sync/install.sh:** Replace hardcoded `pi` with `${SUDO_USER:-pi}` for group membership
- **setup.sh (epaper.service):** Use `%h` (home dir) specifier where possible, or generate paths from a single config file `/etc/epaper-settings/epaper.conf` that stores `EPAPER_USER`, `VENV_DIR`, `REPO_DIR`
- **install_settings.sh (settingsapp.service):** Same approach — read user/paths from `/etc/epaper-settings/epaper.conf`
- **Alternative (simpler):** Create a dedicated `epaper` system user during install. All services run as `epaper`. Eliminates the variable entirely.

### Phase 3: Fix GPIO device portability (fixes #7)

**Change:** Detect available GPIO chips at install time or use a wildcard.

- Replace hardcoded `DeviceAllow=/dev/gpiochip4` with a list generated by scanning `/dev/gpiochip*` at install time
- Or use `DeviceAllow=char-gpiochip rw` (device class wildcard) if systemd version supports it
- Document which Pi models are supported and their GPIO chip mappings

### Phase 4: Fix boot config path (fixes #11)

**Change:** Add the same boot config detection from `final_hardening.sh` to `setup.sh`.

```bash
BOOT_CONFIG="/boot/config.txt"
if [ -f /boot/firmware/config.txt ]; then
  BOOT_CONFIG="/boot/firmware/config.txt"
fi
```

### Phase 5: Document the portability contract (fixes #9, #10)

- Add a "Moving your SD card to another Pi" section to the install guide
- Document: same Pi model required, same display wiring required, data SD card needs `EPAPER_SD` label
- Document: if OverlayFS is enabled, disable it first before troubleshooting
- Document: hostname should be set via `raspi-config` after moving

## Priority Order

1. **Phase 1** (SD label) — highest impact, most likely the user's actual issue
2. **Phase 2** (user/paths) — second most common failure mode
3. **Phase 4** (boot config) — small fix, do alongside Phase 2
4. **Phase 3** (GPIO) — only matters across Pi models
5. **Phase 5** (docs) — do last, after fixes are in place

## Estimated Scope

- Phase 1: Modify 1 file (`install_sd_card_reader.sh`) + new helper script
- Phase 2: Modify 4 files (3 install scripts + 1 service file)
- Phase 3: Modify 1 file (`setup.sh`)
- Phase 4: Modify 1 file (`setup.sh`)
- Phase 5: New docs section
