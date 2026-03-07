# B-002: Image dimension mismatch in documentation

Status: Closed
Last updated: 2026-03-07
Severity: Low

## Description

Different documents state different target image dimensions:

| Source | Stated Dimensions |
|--------|------------------|
| Root README.md | 800x400 |
| eInkFrame README.md | 800x480 |
| intro.md (German) | 480x800 (reversed) |
| image_converter.py (code) | 800x480 |
| file_tab.py (code) | `CROP_WIDTH=800, CROP_HEIGHT=480` |

## Actual Value

The code consistently uses **800x480** (width x height), which matches the Waveshare 7.3" display resolution.

## Fix

1. Update root README.md: change 800x400 references to 800x480
2. Update intro.md: change 480x800 to 800x480 (width x height convention)
3. Verify no code uses 800x400 — the ImageUiApp app.py sets `CROP_HEIGHT = 480` correctly
