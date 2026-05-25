"""OBCD Pilot application entry point."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen, QWidget

from obcd_pilot import __version__


def _resource_path(rel: str) -> Path:
    """Resolve a bundled-asset path. Works in dev and frozen PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / rel  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / rel


def main() -> None:
    """Launch the OBCD Pilot Qt application."""
    QApplication.setOrganizationName("OBCD")
    QApplication.setApplicationName("obcd-pilot")
    QApplication.setApplicationDisplayName("OBCD Pilot")
    app = QApplication(sys.argv)

    splash = _create_splash("Loading models...")
    splash.show()

    # Paint the Qt splash before the bootloader splash is dismissed.
    # Otherwise, there is a brief blank frame between the two.
    app.processEvents()
    _close_bootloader_splash()

    # Hold the window past _finish_init's scope so it isn't garbage-collected.
    window: QWidget | None = None

    def _finish_init() -> None:
        nonlocal window
        app.setStyleSheet(
            _resource_path("ui/styles/app.qss").read_text(encoding="utf-8")
        )

        from obcd_pilot import app_log
        from obcd_pilot.ui.main_window import MainWindow

        app_log.configure().info("Application started, OBCD Pilot v%s", __version__)
        window = MainWindow()
        _center_on_screen(window)
        window.show()
        splash.finish(window)

    # Defer heavy imports (torch, ultralytics) until after the splash paints.
    QTimer.singleShot(0, _finish_init)
    sys.exit(app.exec())


def _create_splash(subtitle: str) -> QSplashScreen:
    """Qt splash. Loads the @2x asset with DPR=2 for crisp rendering on any display."""
    pixmap = QPixmap(str(_resource_path("ui/splash@2x.png")))
    pixmap.setDevicePixelRatio(2.0)
    splash = QSplashScreen(pixmap)
    splash.showMessage(
        subtitle,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#888888"),
    )
    return splash


def _center_on_screen(widget: QWidget) -> None:
    """Center widget on the primary screen."""
    screen = QApplication.primaryScreen()
    if screen is None:
        return
    geometry = widget.frameGeometry()
    geometry.moveCenter(screen.availableGeometry().center())
    widget.move(geometry.topLeft())


def _close_bootloader_splash() -> None:
    """Dismiss PyInstaller's bootstrap splash. No-op in dev runs."""
    try:
        import pyi_splash  # type: ignore[import-untyped]
    except ImportError:
        return
    pyi_splash.close()


if __name__ == "__main__":
    main()
