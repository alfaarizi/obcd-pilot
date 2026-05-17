"""OBCD Pilot application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from obcd_pilot.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
