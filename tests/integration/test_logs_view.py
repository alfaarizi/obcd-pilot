"""Integration tests for LogsView widget."""

import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QModelIndex, QRect
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QStyleOptionViewItem
from pytestqt.qtbot import QtBot

from obcd_pilot import app_log
from obcd_pilot.pipeline import Detection
from obcd_pilot.ui.logs_view import (
    LogsView,
    _LogDelegate,
    _LogEntry,
    _LogModel,
    _parse_line,
)


@pytest.fixture()
def view(qtbot: QtBot) -> LogsView:
    """A LogsView registered with qtbot for cleanup."""
    widget = LogsView()
    qtbot.addWidget(widget)
    return widget


def _select_category(view: LogsView, value: str) -> None:
    """Select the dropdown entry by its data value, regardless of position."""
    view._category_combo.setCurrentIndex(view._category_combo.findData(value))


class TestConstruction:
    """Tests for LogsView construction."""

    def test_constructs_without_error(self, view: LogsView) -> None:
        """LogsView can be created without raising."""
        assert view is not None

    def test_object_name_is_set(self, view: LogsView) -> None:
        """LogsView carries the 'logs-view' object name for QSS styling."""
        assert view.objectName() == "logs-view"

    def test_starts_with_zero_rows(self, view: LogsView) -> None:
        """Both the source model and the proxy start empty."""
        assert view._source_model.rowCount() == 0
        assert view._proxy.rowCount() == 0

    def test_default_category_is_all(self, view: LogsView) -> None:
        """The dropdown defaults to 'All logs'."""
        assert view._category_combo.currentIndex() == 0
        assert view._category_combo.currentData() == "all"

    def test_toolbar_has_expected_controls(self, view: LogsView) -> None:
        """The toolbar exposes category, search, refresh, and export controls."""
        assert view._category_combo is not None
        assert view._search_input.placeholderText() == "Search logs..."
        assert view._refresh_btn.text() == "Refresh"
        assert view._export_btn.text() == "Export"


class TestLiveRecords:
    """Tests for live records arriving through the Qt bridge."""

    def test_detection_event_shows_up(
        self, view: LogsView, make_detection: Callable[..., Detection]
    ) -> None:
        """A change-positive detection populates the model."""
        app_log.log_detection(make_detection(frame_id=11))
        assert view._source_model.rowCount() == 1

    def test_negative_detection_is_silent(
        self, view: LogsView, make_detection: Callable[..., Detection]
    ) -> None:
        """A change negative detection does not populate the model."""
        app_log.log_detection(make_detection(change_detected=False))
        assert view._source_model.rowCount() == 0

    def test_child_logger_records_appear(self, view: LogsView) -> None:
        """Records from obcd_pilot.* child loggers reach the view."""
        logging.getLogger("obcd_pilot.capture.test").info("camera started")
        assert view._source_model.rowCount() == 1

    def test_count_label_reflects_total(self, view: LogsView) -> None:
        """The status bar count grows with each new record."""
        logging.getLogger("obcd_pilot.x").info("one")
        logging.getLogger("obcd_pilot.x").info("two")
        assert "2 entries" in view._count_label.text()


class TestCategoryFilter:
    """Tests for the level/category dropdown filter."""

    @pytest.fixture()
    def populated_view(
        self, view: LogsView, make_detection: Callable[..., Detection]
    ) -> LogsView:
        """LogsView pre-populated with one entry per filterable level."""
        logging.getLogger("obcd_pilot.x").info("info entry")
        logging.getLogger("obcd_pilot.x").warning("warn entry")
        logging.getLogger("obcd_pilot.x").error("error entry")
        app_log.log_detection(make_detection(frame_id=1))
        return view

    def test_all_logs_shows_everything(self, populated_view: LogsView) -> None:
        """Selecting 'All logs' shows every source row."""
        _select_category(populated_view, "all")
        proxy_rows = populated_view._proxy.rowCount()
        source_rows = populated_view._source_model.rowCount()
        assert proxy_rows == source_rows

    def test_detection_only_filters_to_detection_logger(
        self, populated_view: LogsView
    ) -> None:
        """Selecting 'Detection events' shows only obcd_pilot.detection rows."""
        _select_category(populated_view, "detection")
        for row in range(populated_view._proxy.rowCount()):
            entry = populated_view._proxy.index(row, 0).data(_LogModel.EntryRole)
            assert entry.logger_name == app_log.DETECTION_LOGGER_NAME

    def test_errors_only_filters_to_error_level(self, populated_view: LogsView) -> None:
        """Selecting 'Errors' shows only ERROR level rows."""
        _select_category(populated_view, "ERROR")
        for row in range(populated_view._proxy.rowCount()):
            entry = populated_view._proxy.index(row, 0).data(_LogModel.EntryRole)
            assert entry.level == "ERROR"


class TestSearch:
    """Tests for the search input filter."""

    def test_search_narrows_visible_rows(self, view: LogsView) -> None:
        """Typing in the search input narrows the visible rows by message."""
        logging.getLogger("obcd_pilot.x").info("camera started")
        logging.getLogger("obcd_pilot.x").info("pipeline started")
        view._search_input.setText("camera")
        assert view._proxy.rowCount() == 1

    def test_search_is_case_insensitive(self, view: LogsView) -> None:
        """A lowercase needle matches mixed case messages."""
        logging.getLogger("obcd_pilot.x").info("Camera Started")
        view._search_input.setText("camera")
        assert view._proxy.rowCount() == 1

    def test_clearing_search_restores_all_rows(self, view: LogsView) -> None:
        """Clearing the input restores every source row."""
        logging.getLogger("obcd_pilot.x").info("one")
        logging.getLogger("obcd_pilot.x").info("two")
        view._search_input.setText("nomatch")
        assert view._proxy.rowCount() == 0
        view._search_input.setText("")
        assert view._proxy.rowCount() == 2


class TestRefresh:
    """Tests for the Refresh button."""

    def test_refresh_reloads_from_file(self, qtbot: QtBot, tmp_path: Path) -> None:
        """Refresh re-reads the log file into the model."""
        path = tmp_path / "obcd_pilot.log"
        app_log.configure(path)
        view = LogsView()
        qtbot.addWidget(view)

        # Append a line directly to the file as if another process wrote it.
        with path.open("a", encoding="utf-8") as f:
            f.write("2026-05-24T10:00:00.000  INFO     obcd_pilot.x: external write\n")
        view._refresh_btn.click()
        assert any(
            "external write"
            in view._source_model.index(row, 0).data(_LogModel.EntryRole).message
            for row in range(view._source_model.rowCount())
        )


class TestExport:
    """Tests for the Export button."""

    def test_export_writes_filtered_entries(
        self, view: LogsView, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Export writes currently-visible rows to the chosen file."""
        logging.getLogger("obcd_pilot.x").info("keep me")
        target = tmp_path / "exported.log"
        monkeypatch.setattr(
            "obcd_pilot.ui.logs_view.QFileDialog.getSaveFileName",
            lambda *_a, **_kw: (str(target), "Log files (*.log)"),
        )
        view._export_btn.click()
        assert "keep me" in target.read_text(encoding="utf-8")

    def test_export_cancelled_writes_nothing(
        self, view: LogsView, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cancelling the save dialog leaves no file behind."""
        target = tmp_path / "never.log"
        monkeypatch.setattr(
            "obcd_pilot.ui.logs_view.QFileDialog.getSaveFileName",
            lambda *_a, **_kw: ("", ""),
        )
        view._export_btn.click()
        assert not target.exists()


class TestParseLine:
    """Tests for the log line parser."""

    def test_parses_well_formed_line(self) -> None:
        """A line in the file format parses into a populated _LogEntry."""
        entry = _parse_line(
            "2026-05-24T14:32:07.123  ERROR    obcd_pilot.detection: "
            "Change detected in frame 142"
        )
        assert entry is not None
        assert entry.timestamp == "14:32:07"
        assert entry.level == "ERROR"
        assert entry.logger_name == "obcd_pilot.detection"
        assert "Change detected" in entry.message

    def test_returns_none_for_garbage(self) -> None:
        """A non matching line yields None instead of a partial entry."""
        assert _parse_line("not a log line") is None


class TestDelegate:
    """Tests for the custom paint delegate."""

    def test_paint_does_not_raise(self) -> None:
        """The delegate paints a sample row without raising."""
        model = _LogModel()
        model.append(
            _LogEntry(
                timestamp="14:32:07",
                level="ERROR",
                logger_name="obcd_pilot.detection",
                message="Change detected in frame 142",
            )
        )
        delegate = _LogDelegate()
        pixmap = QPixmap(600, 22)
        painter = QPainter(pixmap)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 600, 22)
        try:
            delegate.paint(painter, option, model.index(0, 0))
        finally:
            painter.end()

    def test_paint_ignores_invalid_index(self) -> None:
        """An invalid index returns silently rather than raising."""
        delegate = _LogDelegate()
        pixmap = QPixmap(10, 22)
        painter = QPainter(pixmap)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 10, 22)
        try:
            delegate.paint(painter, option, QModelIndex())
        finally:
            painter.end()
