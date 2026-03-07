# Services

Last updated: 2026-03-07

## Service Documentation

| Document | Systemd Unit | Runs On |
|----------|-------------|---------|
| [epaper-display.md](epaper-display.md) | `epaper.service` | Pi |
| [s3-sync.md](s3-sync.md) | `sd-s3-sync.service` / `sd-s3-sync.timer` | Pi |
| [settings-ui.md](settings-ui.md) | `settingsapp.service` | Pi |
| [image-ui.md](image-ui.md) | `imageuiapp.service` (EC2) or standalone | EC2 / Laptop |
| [sd-mount.md](sd-mount.md) | `mnt-epaper_sd.mount` | Pi |
| [hardening.md](hardening.md) | `watchdog.service` + OverlayFS | Pi |
