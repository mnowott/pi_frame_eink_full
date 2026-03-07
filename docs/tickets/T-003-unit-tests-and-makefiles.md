# T-003: Add unit tests and Makefiles to all modules

Status: Closed
Last updated: 2026-03-07

## Problem

Only `eInkFrameWithStreamlitMananger` has tests (S3Manager only). No module has a Makefile for standardized dev workflows.

## Current Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| eInkFrameWithStreamlitMananger | `tests/test_s3_manager.py` | S3Manager only |
| pi-s3-sync | None | — |
| ImageUiApp | None | — |
| SettingsApp | None | — |

## Plan

### Top-Level Makefile

The repo root gets a `Makefile` that orchestrates all module checks:

```makefile
MODULES := eInkFrameWithStreamlitMananger \
           pi-s3-sync \
           s3_image_croper_ui_app/ImageUiApp \
           s3_image_croper_ui_app/SettingsApp

.PHONY: check install format lint test

check: format lint test

install:
	@for mod in $(MODULES); do echo "=== install $$mod ===" && $(MAKE) -C $$mod install; done

format:
	@for mod in $(MODULES); do echo "=== format $$mod ===" && $(MAKE) -C $$mod format; done

lint:
	@for mod in $(MODULES); do echo "=== lint $$mod ===" && $(MAKE) -C $$mod lint; done

test:
	@for mod in $(MODULES); do echo "=== test $$mod ===" && $(MAKE) -C $$mod test; done
```

`make check` runs format + lint + test across all modules. This is the single command to validate the entire codebase.

### Per-Module Makefiles

Each module gets a `Makefile` with standardized targets, optimized for agent usage (minimal output, failure-only reporting):

```makefile
.PHONY: install format lint test all

install:
	poetry install --quiet

format:
	poetry run ruff format . --quiet

lint:
	poetry run ruff check . --quiet

test:
	poetry run pytest -q --tb=short

all: format lint test
```

### Test Priorities

1. **pi-s3-sync:** Test config loading (wifi.json parsing, env var fallbacks), S3 sync command construction, Wi-Fi connection logic (mock subprocess)
2. **SettingsApp:** Test settings load/save, path priority logic, form validation, refresh_time.txt generation
3. **ImageUiApp:** Test image cropping math, S3 upload/list/delete (mocked), ZIP generation
4. **eInkFrameWithStreamlitMananger:** Extend to cover image_converter (resize/crop/enhance), settings loading, quiet hours logic, sd_monitor change detection

Hardware-dependent code (display_manager, waveshare drivers) is not testable without mocking the entire SPI/GPIO stack — skip or mock at interface boundary.

## Mocking

Where cloud resources are mocked, rely on trustworthy pre-established mocking frameworks (e.g., moto for S3, already a dev dependency in eInkFrame) instead of brittle self-made mocks. For subprocess calls (nmcli, aws cli), use `unittest.mock.patch` on `subprocess.run`.

## Acceptance Criteria

- Root `Makefile` with `make check` that runs all modules
- Every module has a `Makefile` with `install`, `format`, `lint`, `test`, `all` targets
- Makefile output is agent-friendly: quiet on success, actionable on failure
- Test coverage for all non-hardware logic
- CI-ready: `make check` exits 0 on clean codebase
