"""Integration tests for MonitorView."""

import pytest
from pytestqt.qtbot import QtBot

from obcd_pilot.ui.components.preview import Preview
from obcd_pilot.ui.components.status_panel import StatusPanel
from obcd_pilot.ui.monitor_view import MonitorView


@pytest.fixture()
def view(qtbot: QtBot, no_cameras: None) -> MonitorView:
    """A MonitorView registered with qtbot for cleanup."""
    widget = MonitorView()
    qtbot.addWidget(widget)
    return widget


def test_monitor_view_constructs_without_error(view: MonitorView) -> None:
    """MonitorView can be created without raising."""
    assert view is not None


def test_monitor_view_contains_preview(view: MonitorView) -> None:
    """MonitorView embeds a Preview widget."""
    assert isinstance(view._preview, Preview)


def test_monitor_view_contains_status_panel(view: MonitorView) -> None:
    """MonitorView embeds a StatusPanel widget."""
    assert isinstance(view._status_panel, StatusPanel)


def test_status_panel_width_is_fixed(view: MonitorView) -> None:
    """The embedded StatusPanel retains its 240 px fixed width."""
    assert view._status_panel.width() == 240
