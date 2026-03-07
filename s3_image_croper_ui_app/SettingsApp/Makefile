.PHONY: install lint test all

install:
	poetry install --quiet

lint:
	poetry run python -m py_compile settingsapp/app.py
	poetry run python -m py_compile settingsapp/main.py

test:
	poetry run pytest -q --tb=short

all: lint test
