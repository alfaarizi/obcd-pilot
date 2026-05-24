.PHONY: rcc lint typecheck test bundle all

rcc:
	pyside6-rcc src/obcd_pilot/ui/icons.qrc -o src/obcd_pilot/ui/icons_rc.py

lint:
	ruff check src tests

typecheck:
	mypy src

test: rcc
	pytest

bundle: rcc
	pyinstaller obcd-pilot.spec --noconfirm

all: rcc lint typecheck test