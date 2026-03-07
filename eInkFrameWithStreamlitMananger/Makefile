.PHONY: install lint test all

install:
	poetry install --quiet

lint:
	poetry run python -m py_compile settings_loader.py
	poetry run python -m py_compile sd_monitor.py
	poetry run python -m py_compile frame_manager.py
	poetry run python -m py_compile image_converter.py
	poetry run python -m py_compile pollock_text.py
	poetry run python -m py_compile display_manager.py

test:
	poetry run pytest -q --tb=short

all: lint test
