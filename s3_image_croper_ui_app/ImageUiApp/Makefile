SOURCES := imageuiapp/app.py imageuiapp/main.py \
           imageuiapp/tabs/file_tab.py imageuiapp/tabs/view_tab.py \
           imageuiapp/tabs/downloads_tab.py imageuiapp/tabs/info_tab.py

.PHONY: install lint typecheck format format-check doctest test coverage all check

install:
	poetry install --quiet

lint:
	@for src in $(SOURCES); do poetry run python -m py_compile $$src || exit 1; done

typecheck:
	poetry run mypy --ignore-missing-imports $(SOURCES)

format:
	poetry run ruff format imageuiapp/ tests/

format-check:
	poetry run ruff format --check imageuiapp/ tests/

doctest:
	poetry run pytest --doctest-modules imageuiapp/ -q --tb=short || true

test:
	poetry run pytest -q --tb=short

coverage:
	poetry run pytest --cov=imageuiapp --cov-report=term-missing -q --tb=short

check: lint typecheck format-check test

all: check
