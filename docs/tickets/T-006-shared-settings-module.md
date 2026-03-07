# T-006: Extract duplicated load_settings() into shared module

Status: Open
Last updated: 2026-03-07

## Problem

`load_settings()` is copy-pasted across three files with minor variations:

- `eInkFrameWithStreamlitMananger/sd_monitor.py`
- `eInkFrameWithStreamlitMananger/frame_manager.py`
- `eInkFrameWithStreamlitMananger/pollock_text.py`

Each copy defines the same path priority chain and default values. Changes to the settings format require updating all three.

## Plan

1. Create `eInkFrameWithStreamlitMananger/settings_loader.py` with:
   - `SETTINGS_PATHS` constant (ordered list of paths to check)
   - `DEFAULT_SETTINGS` constant
   - `load_settings() -> dict` function
   - `get_refresh_time(settings, sd_path) -> int` helper
2. Replace duplicated functions in `sd_monitor.py`, `frame_manager.py`, `pollock_text.py` with imports
3. Add tests for settings_loader.py

## Acceptance Criteria

- Single source of truth for settings loading
- All three consumers import from `settings_loader.py`
- Tests cover: path priority, missing files, malformed JSON, default values
