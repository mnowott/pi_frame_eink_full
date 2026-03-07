# T-004: Standardize settings directory name across modules

Status: Open
Last updated: 2026-03-07

## Problem

The settings directory name is inconsistent across modules:

| Module / File | Path Used |
|---------------|-----------|
| `sd_monitor.py` | `/mnt/epaper_sd/epaper_settings/settings.json` |
| `frame_manager.py` | `/mnt/epaper_sd/epaper_settings/settings.json` |
| `pollock_text.py` | `/mnt/epaper_sd/epaper_settings/settings.json` |
| `SettingsApp/app.py` | `/mnt/epaper_sd/epaper_settings/settings.json` |
| `setup.sh` (default config) | `~/.config/epaper_frame/settings.json` |
| Some README docs | `/mnt/epaper_sd/epaper_frame/settings.json` |

The SD card path uses `epaper_settings/` while the home fallback uses `epaper_frame/`. Documentation sometimes references `epaper_frame/` for the SD path too.

## Plan

1. Pick one canonical name for both SD and home paths. Recommendation: `epaper_settings/` everywhere (matches current SD behavior).
2. Update `setup.sh` default config path from `~/.config/epaper_frame/` to `~/.config/epaper_settings/`
3. Update all fallback paths in `sd_monitor.py`, `frame_manager.py`, `pollock_text.py`, `SettingsApp/app.py`
4. Update documentation (READMEs, CLAUDE.md, docs/)
5. Add migration: if old `epaper_frame/` dir exists, copy settings to new location

## Acceptance Criteria

- Single directory name used everywhere (`epaper_settings/`)
- Old path still works as last-resort fallback (graceful migration)
- All docs updated
