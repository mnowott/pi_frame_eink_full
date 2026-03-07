SOURCES := settingsapp/app.py settingsapp/main.py

.PHONY: install lint typecheck format format-check doctest test coverage all check

install:
	poetry install --quiet

lint:
	@for src in $(SOURCES); do poetry run python -m py_compile $$src || exit 1; done

typecheck:
	poetry run mypy --ignore-missing-imports $(SOURCES)

format:
	poetry run ruff format settingsapp/ tests/

format-check:
	poetry run ruff format --check settingsapp/ tests/

doctest:
	poetry run pytest --doctest-modules settingsapp/ -q --tb=short || true

test:
	poetry run pytest -q --tb=short

coverage:
	poetry run pytest --cov=settingsapp --cov-report=term-missing -q --tb=short

check: lint typecheck format-check test

all: check
