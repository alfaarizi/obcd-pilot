"""Integration tests for MainWindow."""

import pytest
from PySide6.QtCore import QSize
from pytestqt.qtbot import QtBot

from obcd_pilot import __version__
from obcd_pilot.ui.main_window import MainWindow


@pytest.fixture()
def window(qtbot: QtBot, no_cameras: None) -> MainWindow:
    """A MainWindow registered with qtbot for cleanup."""
    widget = MainWindow()
    qtbot.addWidget(widget)
    return widget


class TestMainWindowConstruction:
    """Tests for MainWindow construction."""

    def test_constructs_without_error(self, window: MainWindow) -> None:
        """MainWindow can be created without raising."""
        assert window is not None

    def test_window_title(self, window: MainWindow) -> None:
        """The window title is 'OBCD Pilot'."""
        assert window.windowTitle() == "OBCD Pilot"

    def test_minimum_size(self, window: MainWindow) -> None:
        """MainWindow enforces a minimum size of 640 × 360."""
        assert window.minimumSize() == QSize(640, 360)


class TestMainWindowServiceBar:
    """Tests for the service bar at the bottom of MainWindow."""

    def test_version_label_shows_package_version(self, window: MainWindow) -> None:
        """The version label in the service bar displays the installed version."""
        assert window._version_label.text() == f"v{__version__}"

    def test_service_label_default_text(self, window: MainWindow) -> None:
        """The service label starts with a placeholder value."""
        assert "Service" in window._service_label.text()

    def test_service_bar_fixed_height(self, window: MainWindow) -> None:
        """The service bar is anchored to 30 px tall."""
        assert window._status_bar.height() == 30


class TestMainWindowNavSidebar:
    """Tests for the navigation sidebar."""

    def test_nav_sidebar_is_not_movable(self, window: MainWindow) -> None:
        """The navigation toolbar cannot be dragged to a different area."""
        assert not window._nav_sidebar.isMovable()

    def test_nav_sidebar_fixed_width(self, window: MainWindow) -> None:
        """The navigation sidebar is anchored to 68 px wide."""
        assert window._nav_sidebar.width() == 68


class TestMainWindowStack:
    """Tests for the central stacked widget."""

    def test_stack_has_monitor_view(self, window: MainWindow) -> None:
        """The stacked widget contains exactly one view (MonitorView) at startup."""
        assert window._stack.count() == 1

    def test_monitor_view_is_current(self, window: MainWindow) -> None:
        """MonitorView is the active (index 0) page on startup."""
        assert window._stack.currentIndex() == 0
