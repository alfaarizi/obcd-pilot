"""Integration tests for PopupAlarm."""

from collections.abc import Callable

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from obcd_pilot import alarm
from obcd_pilot.pipeline import Detection
from obcd_pilot.ui.components.popup_alarm import PopupAlarm


@pytest.fixture()
def parent(qtbot: QtBot) -> QWidget:
    """A sized parent so the toast can anchor against a known width."""
    widget = QWidget()
    widget.resize(640, 360)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture()
def popup(qtbot: QtBot, parent: QWidget) -> PopupAlarm:
    """A PopupAlarm parented to the given fixture parent."""
    widget = PopupAlarm(parent)
    qtbot.addWidget(widget)
    return widget


def test_shows_when_channel_enabled(
    popup: PopupAlarm, make_detection: Callable[..., Detection]
) -> None:
    """show_alert reveals the toast when the pop-up channel is enabled."""
    popup.show_alert(make_detection(change_detected=True))
    assert not popup.isHidden()


def test_suppressed_when_channel_disabled(
    popup: PopupAlarm, make_detection: Callable[..., Detection]
) -> None:
    """show_alert is a noop while the pop-up channel is off."""
    alarm.store().set_popup_enabled(False)
    popup.show_alert(make_detection(change_detected=True))
    assert popup.isHidden()


def test_ignores_non_change_detection(
    popup: PopupAlarm, make_detection: Callable[..., Detection]
) -> None:
    """A detection with change_detected False does not surface a toast."""
    popup.show_alert(make_detection(change_detected=False))
    assert popup.isHidden()


def test_meta_includes_confidence(
    popup: PopupAlarm, make_detection: Callable[..., Detection]
) -> None:
    """The meta row renders the confidence score."""
    popup.show_alert(make_detection(change_detected=True, confidence=0.92))
    assert "92%" in popup._meta_label.text()


def test_time_label_renders_wall_clock(
    popup: PopupAlarm, make_detection: Callable[..., Detection]
) -> None:
    """The time row renders the wall clock timestamp."""
    popup.show_alert(make_detection(change_detected=True))
    assert popup._time_label.text().count(":") == 2


def test_rapid_alerts_replace_existing_toast(
    popup: PopupAlarm, make_detection: Callable[..., Detection]
) -> None:
    """A second alert overwrites the first without spawning a second widget."""
    popup.show_alert(make_detection(confidence=0.80, change_detected=True))
    popup.show_alert(make_detection(confidence=0.95, change_detected=True))
    assert not popup.isHidden()
    assert "95%" in popup._meta_label.text()


def test_left_click_dismisses(
    qtbot: QtBot,
    popup: PopupAlarm,
    make_detection: Callable[..., Detection],
) -> None:
    """A left click on the toast triggers the dismiss animation and hides it."""
    popup.show_alert(make_detection(change_detected=True))
    qtbot.mouseClick(popup, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: popup.isHidden(), timeout=1000)


def test_anchors_to_horizontal_center_of_parent(
    parent: QWidget,
    popup: PopupAlarm,
    make_detection: Callable[..., Detection],
) -> None:
    """The toast sits centered on the parent's horizontal axis."""
    popup.show_alert(make_detection(change_detected=True))
    expected_x = (parent.width() - popup.width()) // 2
    assert popup.x() == max(0, expected_x)


def test_resize_mid_animation_retargets_slide_end(
    parent: QWidget,
    popup: PopupAlarm,
    make_detection: Callable[..., Detection],
) -> None:
    """A parent resize during the slide animation retargets its x end value."""
    popup.show_alert(make_detection(change_detected=True))
    original_end_y = popup._slide.endValue().y()

    old_size = parent.size()
    new_size = QSize(960, 540)
    parent.resize(new_size)
    popup.eventFilter(parent, QResizeEvent(new_size, old_size))

    expected_x = max(0, (parent.width() - popup.width()) // 2)
    end = popup._slide.endValue()
    assert end.x() == expected_x
    assert end.y() == original_end_y
