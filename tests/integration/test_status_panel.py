"""Integration tests for StatusPanel widget."""

import pytest
from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from obcd_pilot.ui.components.status_panel import (
    _ALARM_CHANNELS,
    StatusPanel,
    _create_section_header,
)


@pytest.fixture()
def panel(qtbot: QtBot) -> StatusPanel:
    """A StatusPanel widget registered with qtbot for cleanup."""
    widget = StatusPanel()
    qtbot.addWidget(widget)
    return widget


class TestStatusPanelConstruction:
    """Tests for StatusPanel construction and initial layout."""

    def test_constructs_without_error(self, panel: StatusPanel) -> None:
        """StatusPanel can be created without raising."""
        assert panel is not None

    def test_fixed_width_is_240(self, panel: StatusPanel) -> None:
        """StatusPanel is anchored to 240 px wide."""
        assert panel.width() == 240

    def test_object_name_is_set(self, panel: StatusPanel) -> None:
        """StatusPanel carries the 'status-panel' object name for QSS styling."""
        assert panel.objectName() == "status-panel"


class TestAlarmIndicators:
    """Tests for the alarm-channel grid inside StatusPanel."""

    def test_alarm_indicators_count_matches_channels(self, panel: StatusPanel) -> None:
        """One indicator dot is created per alarm channel."""
        assert len(panel._alarm_indicators) == len(_ALARM_CHANNELS)

    def test_alarm_names_count_matches_channels(self, panel: StatusPanel) -> None:
        """One name label is created per alarm channel."""
        assert len(panel._alarm_names) == len(_ALARM_CHANNELS)

    def test_alarm_messages_count_matches_channels(self, panel: StatusPanel) -> None:
        """One status label is created per alarm channel."""
        assert len(panel._alarm_messages) == len(_ALARM_CHANNELS)

    def test_alarm_channel_names_match_spec(self, panel: StatusPanel) -> None:
        """The alarm name labels display exactly the channel names from _ALARM_CHANNELS.

        Each label text must equal the corresponding entry in _ALARM_CHANNELS.
        """
        displayed = [label.text() for label in panel._alarm_names]
        assert displayed == _ALARM_CHANNELS

    def test_all_alarm_channels_are_defined(self) -> None:
        """_ALARM_CHANNELS contains at least one entry."""
        assert len(_ALARM_CHANNELS) > 0


class TestDetectionStatusSection:
    """Tests for the detection status area inside StatusPanel."""

    def test_status_label_default_text(self, panel: StatusPanel) -> None:
        """The status label defaults to 'No change'."""
        assert panel._status_label.text() == "No change"

    def test_status_desc_label_default_text(self, panel: StatusPanel) -> None:
        """The description label defaults to an em dash."""
        assert panel._status_desc_label.text() == "—"


class TestDetectionDetailsSection:
    """Tests for the detection details form inside StatusPanel."""

    def test_model_label_default_text(self, panel: StatusPanel) -> None:
        """Model field starts as '—' (no model loaded)."""
        assert panel._model.text() == "—"

    def test_inference_label_default_text(self, panel: StatusPanel) -> None:
        """Inference field starts as '—' (no inference data)."""
        assert panel._inference.text() == "—"

    def test_confidence_label_default_text(self, panel: StatusPanel) -> None:
        """Confidence field starts as '—' (no confidence reported)."""
        assert panel._confidence.text() == "—"


class TestCreateSectionHeader:
    """Tests for the _create_section_header factory function."""

    def test_returns_qlabel(self, qapp: object) -> None:
        """_create_section_header returns a QLabel instance."""
        label = _create_section_header("Alarms")
        assert isinstance(label, QLabel)

    def test_uppercases_text(self, qapp: object) -> None:
        """The section header displays the text in uppercase."""
        label = _create_section_header("details")
        assert label.text() == "DETAILS"

    def test_object_name_is_section_header(self, qapp: object) -> None:
        """The returned label uses 'section-header' as its object name."""
        label = _create_section_header("Alarms")
        assert label.objectName() == "section-header"
