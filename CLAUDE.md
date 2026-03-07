# Pi ePaper Photo Frame System

Family photo frame system: crop images via web UI, sync to S3, display on Waveshare 7-color ePaper panels connected to Raspberry Pis. Includes SD-card-based config, Wi-Fi management, and a web settings UI running on each Pi.

Do not mention yourself in any commits and code.

## Architecture

```
User (browser)
  │
  ├─► ImageUiApp (Streamlit, runs on EC2/laptop)
  │     Upload → crop to 800x480 → save to S3
  │
  ▼
S3 Bucket (rasp-pi-family-s3, eu-central-1)
  │
  ▼  every 15 min (systemd timer)
pi-s3-sync  ─► /mnt/epaper_sd/s3_folder/
  │
  ▼
eInkFrame (systemd service)
  sd_monitor.py → frame_manager.py → image_converter.py → display_manager.py
  │                                                          │
  │  watches SD for changes, enforces quiet hours             ▼
  │                                                    Waveshare ePaper 7.3" (SPI)
  ▼
SettingsApp (Streamlit on port 80, systemd service)
  http://<pi-hostname>/ → edit settings.json on SD
```

## Modules

| Module | Path | Purpose | Stack |
|--------|------|---------|-------|
| **eInkFrame** | `eInkFrameWithStreamlitMananger/` | Display driver + image processing | Python 3.13+, Pillow, boto3, waveshare SPI drivers |
| **pi-s3-sync** | `pi-s3-sync/` | S3→SD sync + Wi-Fi management | Python 3, awscli, NetworkManager/nmcli |
| **ImageUiApp** | `s3_image_croper_ui_app/ImageUiApp/` | Web image cropper + S3 upload | Python 3.11+, Streamlit, Pillow, boto3 |
| **SettingsApp** | `s3_image_croper_ui_app/SettingsApp/` | Web settings UI (runs on Pi) | Python 3.11+, Streamlit |

All Python modules use **Poetry** for dependency management.

## Hardware & Cloud

- **Pi targets:** Zero W, Zero 2W, Pi 3, Pi 4 (SPI + I2C + GPIO)
- **Displays:** Waveshare 7.3" 7-color (epd7in3f primary), epd7in3e, epd5in65f
- **Display resolution:** 800x480 (images cropped/processed to fit)
- **SD card:** USB/SD reader auto-mounted at `/mnt/epaper_sd` (vfat, via systemd mount + udev rule)
- **AWS services:** S3 (image storage), EC2 (optional ImageUiApp host), ALB + Entra ID (optional auth), Route 53, ACM

## Systemd Services (on Pi)

| Service | Trigger | Purpose |
|---------|---------|---------|
| `mnt-epaper_sd.mount` | Boot + udev hotplug | Auto-mount SD card |
| `epaper.service` | After network + SD mount | Display driver (sd_monitor.py) |
| `sd-s3-sync.timer` | Boot + every 15 min | S3 sync scheduler |
| `settingsapp.service` | After network | Web settings UI on port 80 |

## Installation Flow

`install_all_pi.sh` orchestrates setup in order:
1. `install_env.sh` — sets AWS env vars in `~/.bashrc`
2. `install_sd_card_reader.sh` — creates systemd mount + udev rule for SD
3. `pi-s3-sync/install.sh` — installs awscli, NetworkManager, systemd timer
4. `s3_image_croper_ui_app/install_settings.sh` — installs SettingsApp + systemd service
5. `eInkFrameWithStreamlitMananger/setup.sh` — **commented out, requires manual run** (enables SPI/I2C, installs drivers, creates epaper.service, prompts reboot)
6. `final_hardening.sh` — **must be run last, separately** (enables watchdog, volatile journald, OverlayFS read-only root — reboot required, changes are irreversible without re-flash)

## Settings (settings.json)

Loaded from (priority order): SD card `/mnt/epaper_sd/epaper_settings/settings.json` → `~/.config/epaper_frame/settings.json`

```json
{
  "picture_mode": "local|online|both",
  "change_interval_minutes": 15,
  "stop_rotation_between": { "evening": "22:00", "morning": "06:00" },
  "s3_folder": "s3_folder"
}
```

## Workflow Rules

After every code change:
1. **Run `make check`** at the repo root — this runs format, lint, and test across all modules. All checks must pass. (Requires T-003 to be completed first; until then, run `poetry run pytest -q --tb=short` in each affected module.)
2. **Review documentation for accuracy** — check that `docs/`, `CLAUDE.md`, and module READMEs still reflect the current state. Update any affected docs (architecture, services, settings, data flow). Update `Last updated` dates on changed docs.
3. **Update tickets/bugs** — if your change resolves a ticket or bug, update its status to Closed. If it introduces new issues, create new entries.

## Security Rules

- **Never commit secrets.** AWS keys, Wi-Fi passwords, and `.pem` files must stay out of git.
- Credentials should live in `.env` files (with `.env.example` templates committed) or `wifi.json` (already gitignored in pi-s3-sync).
- `.pem` files in `s3_image_croper_ui_app/` should be gitignored.

## Documentation

Full project documentation lives in `docs/`. See [docs/index.md](docs/index.md).

```
docs/
├── index.md              # Top-level index
├── conventions.md        # Status values, ID schemes, formatting rules
├── architecture/         # System overview, data flow, deployment topology
├── services/             # Per-service docs (systemd units, config, debugging)
├── tickets/              # Planned improvements (T-001 through T-009)
└── bugs/                 # Known bugs (B-001 through B-006)
```

**Status values:** Open | In Progress | Under Review | Closed | Rejected

When modifying code, check `docs/tickets/` and `docs/bugs/` for related items. Update `Last updated` dates and statuses when resolving issues.

## Known Issues / Tech Debt

Tracked in detail in [docs/tickets/](docs/tickets/index.md) and [docs/bugs/](docs/bugs/index.md). Summary:

| ID | Issue | Severity |
|----|-------|----------|
| T-001 | Hardcoded AWS credentials in install scripts, .env files, systemd units | Critical |
| T-002 | No root .gitignore; .env and .pem files tracked in git | Critical |
| T-003 | Missing unit tests and Makefiles for most modules | Medium |
| T-004 | Settings path inconsistency (`epaper_settings/` vs `epaper_frame/`) | Medium |
| T-005 | Inconsistent AWS env var names (`AWS_KEY_ID` vs `AWS_ACCESS_KEY_ID`) | Low |
| T-006 | Duplicated `load_settings()` across 3 files | Low |
| T-007 | Empty/incomplete module READMEs | Low |
| B-003 | Wi-Fi password logged in plaintext | High |
| B-004 | Potential command injection in Wi-Fi connection | High |
| B-006 | SettingsApp s3_folder input commented out, hardcoded default | Medium |
| T-008 | Systemd services lack sandboxing (ProtectSystem, PrivateTmp, etc.) | High |
| T-009 | No firewall, SSH unhardened, sysctl defaults, swap/BT not disabled | High |
