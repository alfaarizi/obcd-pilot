"""Integration tests for MonitorView."""

import pytest
from pytestqt.qtbot import QtBot

from obcd_pilot.pipeline import Detection
from obcd_pilot.ui.components.preview import Preview
from obcd_pilot.ui.components.status_panel import StatusPanel
from obcd_pilot.ui.monitor_view import MonitorView


@pytest.fixture()
def view(qtbot: QtBot, no_cameras: None) -> MonitorView:
    """A MonitorView registered with qtbot for cleanup."""
    widget = MonitorView()
    qtbot.addWidget(widget)
    return widget


def _detection(*, change_detected: bool = True) -> Detection:
    """Build a Detection for routing tests."""
    return Detection(
        frame_id=3,
        timestamp_ms=1.0,
        change_detected=change_detected,
        confidence=0.77,
        inference_ms=50.0,
        model_name="ConvOBCD",
    )


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


def test_detection_is_routed_to_status_panel(view: MonitorView) -> None:
    """A detection emitted by Preview updates the StatusPanel."""
    view._preview.sig_detection.emit(_detection(change_detected=True))
    assert view._status_panel._status_label.text() == "Change detected"
    assert view._status_panel._confidence.text() == "0.77"


def test_model_ready_is_routed_to_status_panel(view: MonitorView) -> None:
    """The model name announced by Preview reaches the StatusPanel."""
    view._preview.sig_model_ready.emit("ConvOBCD · untrained")
    assert view._status_panel._model.text() == "ConvOBCD · untrained"


def test_pipeline_reset_is_routed_to_status_panel(
    view: MonitorView, qtbot: QtBot
) -> None:
    """A pipeline reset returns the StatusPanel to its idle state."""
    view._preview.sig_model_ready.emit("ConvOBCD")
    view._preview.sig_detection.emit(_detection(change_detected=True))
    view._preview.sig_pipeline_reset.emit()
    # The reset uses a queued connection. Wait for it to land.
    qtbot.waitUntil(
        lambda: view._status_panel._status_label.text() == "No change",
        timeout=1000,
    )
    assert view._status_panel._model.text() == "—"
