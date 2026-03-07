# T-007: Complete missing README documentation

Status: Closed
Last updated: 2026-03-07

## Problem

Several module READMEs are empty or incomplete:

| File | Status |
|------|--------|
| `s3_image_croper_ui_app/README.md` | Title only, no content |
| `s3_image_croper_ui_app/ImageUiApp/README.md` | Title only, no content |
| `s3_image_croper_ui_app/SettingsApp/README.md` | Title only, no content |
| `pi-s3-sync/README.md` | Incomplete, cuts off mid-documentation |

The `eInkFrameWithStreamlitMananger/README.md` and root `README.md` are comprehensive and can serve as templates.

## Plan

1. Complete `pi-s3-sync/README.md`: add installation, systemd setup, troubleshooting sections
2. Write `s3_image_croper_ui_app/README.md`: overview of both apps, deployment options
3. Write `ImageUiApp/README.md`: features, tabs, .env setup, running locally
4. Write `SettingsApp/README.md`: features, form fields, settings paths, systemd service

Content for each README is available in `docs/services/` — READMEs should be user-focused summaries, not duplicates of the docs.

## Acceptance Criteria

- All module READMEs have: purpose, prerequisites, installation, usage, configuration, debugging
- No empty/placeholder READMEs
