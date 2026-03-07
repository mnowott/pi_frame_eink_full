.PHONY: install lint test all

install:
	poetry install --quiet

lint:
	poetry run python -m py_compile scripts/sync_s3_from_sd.py

test:
	poetry run pytest -q --tb=short

all: lint test
