"""OBCD Pilot application entry point."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from obcd_pilot.ui.main_window import MainWindow


def main() -> None:
    """Launch the OBCD Pilot Qt application."""
    QApplication.setOrganizationName("OBCD")
    QApplication.setApplicationName("obcd-pilot")
    app = QApplication(sys.argv)

    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", "."))
    else:
        base = Path(__file__).resolve().parent

    qss = base / "ui" / "styles" / "app.qss"
    app.setStyleSheet(qss.read_text(encoding="utf-8"))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
