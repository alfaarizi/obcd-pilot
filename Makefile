.PHONY: rcc lint typecheck test all

rcc:
	pyside6-rcc src/obcd_pilot/ui/icons.qrc -o src/obcd_pilot/ui/icons_rc.py

lint:
	ruff check src tests

typecheck:
	mypy src

test:
	pytest

all: rcc lint typecheck test