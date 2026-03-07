.PHONY: install lint test all

install:
	poetry install --quiet

lint:
	poetry run python -m py_compile imageuiapp/app.py
	poetry run python -m py_compile imageuiapp/main.py
	poetry run python -m py_compile imageuiapp/tabs/file_tab.py
	poetry run python -m py_compile imageuiapp/tabs/view_tab.py
	poetry run python -m py_compile imageuiapp/tabs/downloads_tab.py
	poetry run python -m py_compile imageuiapp/tabs/info_tab.py

test:
	poetry run pytest -q --tb=short

all: lint test
