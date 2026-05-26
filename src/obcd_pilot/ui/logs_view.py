"""Log viewer with filter, search, refresh, and export,
following the OBCD desktop wireframe.

Rendered with the canonical Qt MVC stack (QListView plus QAbstractListModel
plus QStyledItemDelegate plus QSortFilterProxyModel), the same pattern Qt
Creator's Issues pane and Qt's basicsortfiltermodel example use. Live records
arrive via app_log.bridge(). The refresh path tails the log file with the
deque(f, maxlen=N) recipe from the Python collections docs.
"""

import logging
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Self

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Slot,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot import app_log
from obcd_pilot.ui import icons_rc  # noqa: F401

_HISTORY_TAIL_LINES = 500
_MAX_ROWS = 5_000

_LINE_RE = re.compile(
    r"^(?P<ts>\S+)\s+(?P<level>\w+)\s+(?P<logger>[\w.]+):\s+(?P<msg>.*)$"
)

_ICON_FILTER = QIcon(":/icons/filter.svg")
_ICON_SEARCH = QIcon(":/icons/search.svg")
_ICON_REFRESH = QIcon(":/icons/refresh-cw.svg")
_ICON_DOWNLOAD = QIcon(":/icons/download.svg")

_COLOR_TS = QColor(245, 245, 245, 110)
_COLOR_MSG = QColor(245, 245, 245, 200)
_COLOR_HOVER = QColor(255, 255, 255, 10)
_LEVEL_COLORS: dict[str, QColor] = {
    "INFO": QColor("#4A9CFF"),
    "WARNING": QColor("#E0A63A"),
    "ERROR": QColor("#E24B4A"),
}

_CATEGORIES: list[tuple[str, str]] = [
    ("All logs", "all"),
    ("Detection events", "detection"),
    ("Info", "INFO"),
    ("Warnings", "WARNING"),
    ("Errors", "ERROR"),
]


@dataclass(frozen=True, slots=True)
class _LogEntry:
    """One log line displayed as a row."""

    timestamp: str
    level: str
    logger_name: str
    message: str

    @classmethod
    def from_record(cls, record: logging.LogRecord) -> Self:
        """Build an entry from a stdlib LogRecord arriving on the Qt bridge.

        Timestamp matches the on disk ISO format so Export round trips cleanly.
        """
        dt = datetime.fromtimestamp(record.created)
        timestamp = f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{int(record.msecs):03d}"
        return cls(
            timestamp=timestamp,
            level=record.levelname,
            logger_name=record.name,
            message=record.getMessage(),
        )


class _LogModel(QAbstractListModel):
    """List model that grows by append and drops oldest beyond _MAX_ROWS."""

    EntryRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent: QObject | None = None) -> None:
        """Create an empty model."""
        super().__init__(parent)
        self._entries: list[_LogEntry] = []

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        """Overloaded Qt method.

        Number of rows in the flat list. Zero for any valid parent index.
        """
        return 0 if parent.isValid() else len(self._entries)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        """Overloaded Qt method.

        Returns the entry under the custom role, or a plain text fallback so
        accessibility tools can read the row.
        """
        row = index.row()
        # Bound check because QAbstractListModel.index() does not validate.
        if not index.isValid() or not 0 <= row < len(self._entries):
            return None
        entry = self._entries[row]
        if role == self.EntryRole:
            return entry
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{entry.timestamp} {entry.level} {entry.message}"
        return None

    def append(self, entry: _LogEntry) -> None:
        """Append one entry, dropping the oldest when at the cap."""
        if len(self._entries) >= _MAX_ROWS:
            self.beginRemoveRows(QModelIndex(), 0, 0)
            self._entries.pop(0)
            self.endRemoveRows()
        row = len(self._entries)
        self.beginInsertRows(QModelIndex(), row, row)
        self._entries.append(entry)
        self.endInsertRows()

    def replace(self, entries: list[_LogEntry]) -> None:
        """Replace all rows in one transaction, keeping only the last cap."""
        self.beginResetModel()
        self._entries = entries[-_MAX_ROWS:]
        self.endResetModel()


class _LogProxy(QSortFilterProxyModel):
    """Filters rows by category dropdown and substring search."""

    ALL = "all"
    DETECTION = "detection"

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the proxy with no category filter and no search."""
        super().__init__(parent)
        self._category: str = self.ALL
        self._needle: str = ""

    def set_category(self, value: str) -> None:
        """Switch the category filter and re-evaluate visible rows."""
        self._category = value
        self.invalidate()

    def set_needle(self, value: str) -> None:
        """Set the case insensitive search needle and re-evaluate rows."""
        self._needle = value.casefold()
        self.invalidate()

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        """Overloaded Qt method.

        Accept a row when it matches both the active category and the needle.
        """
        source = self.sourceModel()
        entry = source.index(source_row, 0, source_parent).data(_LogModel.EntryRole)
        if not isinstance(entry, _LogEntry):
            return False

        if self._category == self.DETECTION:
            if entry.logger_name != app_log.DETECTION_LOGGER_NAME:
                return False
        elif self._category != self.ALL and entry.level != self._category:
            return False

        if self._needle:
            haystack = f"{entry.level} {entry.logger_name} {entry.message}".casefold()
            if self._needle not in haystack:
                return False
        return True

    def lessThan(
        self,
        left: QModelIndex | QPersistentModelIndex,
        right: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        """Overloaded Qt method.

        Order rows by ISO timestamp ascending. Python's logging uses a per
        handler lock, so cross thread emissions can reach the Qt signal handler
        in a different order than the file handler.
        """
        left_entry = left.data(_LogModel.EntryRole)
        right_entry = right.data(_LogModel.EntryRole)
        if isinstance(left_entry, _LogEntry) and isinstance(right_entry, _LogEntry):
            return left_entry.timestamp < right_entry.timestamp
        return False


class _LogDelegate(QStyledItemDelegate):
    """Paints a row as dim timestamp, colored level, message."""

    _ROW_HEIGHT = 22
    _H_PADDING = 16
    _TS_WIDTH = 80
    _LEVEL_WIDTH = 56

    def __init__(self, parent: QObject | None = None) -> None:
        """Cache the fonts and metrics used by every paint call."""
        super().__init__(parent)
        self._mono = QFont("Menlo")
        self._mono.setStyleHint(QFont.StyleHint.Monospace)
        self._mono.setPixelSize(11)
        self._mono_bold = QFont(self._mono)
        self._mono_bold.setWeight(QFont.Weight.DemiBold)
        self._metrics = QFontMetrics(self._mono)

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        """Overloaded Qt method.

        Fixed row height so the list view can short circuit per row measurement.
        """
        return QSize(0, self._ROW_HEIGHT)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Overloaded Qt method.

        Render the row as dim timestamp, colored level token, and message body.
        """
        entry = index.data(_LogModel.EntryRole)
        if not isinstance(entry, _LogEntry):
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, _COLOR_HOVER)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        rect = option.rect
        baseline_y = rect.center().y() + self._metrics.ascent() // 2 - 1
        x = rect.left() + self._H_PADDING

        painter.setFont(self._mono)
        painter.setPen(_COLOR_TS)
        # Render only the wall clock portion HH:MM:SS for visual compactness.
        painter.drawText(x, baseline_y, entry.timestamp[11:19])
        x += self._TS_WIDTH

        level_text = "WARN" if entry.level == "WARNING" else entry.level
        painter.setFont(self._mono_bold)
        painter.setPen(_LEVEL_COLORS.get(entry.level, _COLOR_MSG))
        painter.drawText(x, baseline_y, level_text)
        x += self._LEVEL_WIDTH

        available = rect.right() - x - self._H_PADDING
        painter.setFont(self._mono)
        painter.setPen(_COLOR_MSG)
        painter.drawText(
            x,
            baseline_y,
            self._metrics.elidedText(
                entry.message, Qt.TextElideMode.ElideRight, available
            ),
        )

        painter.restore()


class LogsView(QWidget):
    """Log viewer following the OBCD desktop wireframe."""

    def __init__(self) -> None:
        """Build the toolbar, list view, and status bar, then wire signals."""
        super().__init__()
        self.setObjectName("logs-view")

        self._log_path: Path = app_log.current_log_path()

        self._source_model = _LogModel(self)
        self._proxy = _LogProxy(self)
        self._proxy.setSourceModel(self._source_model)
        # Sort by ISO timestamp so live tail and refresh display the same order
        self._proxy.sort(0, Qt.SortOrder.AscendingOrder)

        self._view = QListView()
        self._view.setObjectName("logs-list")
        self._view.setModel(self._proxy)
        self._view.setItemDelegate(_LogDelegate(self._view))
        self._view.setUniformItemSizes(True)
        self._view.setMouseTracking(True)
        self._view.setSelectionMode(QListView.SelectionMode.SingleSelection)

        self._count_label = QLabel()
        self._count_label.setObjectName("logs-count")
        self._path_label = QLabel(f"File: {self._log_path}")
        self._path_label.setObjectName("logs-path")
        self._path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._category_combo = self._create_category_combo()
        self._search_input = self._create_search_input()
        self._refresh_btn = self._create_button("Refresh", _ICON_REFRESH)
        self._export_btn = self._create_button("Export", _ICON_DOWNLOAD)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._create_toolbar())
        root.addWidget(self._view, stretch=1)
        root.addWidget(self._create_statusbar())
        self.setLayout(root)

        self._category_combo.currentIndexChanged.connect(self._on_category_changed)
        self._search_input.textChanged.connect(self._on_search_changed)
        self._refresh_btn.clicked.connect(self._reload_from_file)
        self._export_btn.clicked.connect(self._on_export_clicked)
        for signal in (
            self._proxy.rowsInserted,
            self._proxy.rowsRemoved,
            self._proxy.modelReset,
            self._proxy.layoutChanged,
        ):
            signal.connect(self._update_count_label)

        app_log.bridge().sig_record.connect(self._on_record)
        self._reload_from_file()
        self._update_count_label()

    def showEvent(self, event: QShowEvent) -> None:
        """Overloaded Qt method.

        Anchor to the latest entry every time the view becomes visible.
        """
        super().showEvent(event)
        self._anchor_to_tail(deferred=False)

    @Slot()
    def _reload_from_file(self) -> None:
        """Re read the tail of the log file into the model."""
        try:
            with self._log_path.open("r", encoding="utf-8", errors="replace") as f:
                lines = deque(f, maxlen=_HISTORY_TAIL_LINES)
        except FileNotFoundError:
            self._source_model.replace([])
            return
        entries = [
            e for line in lines if (e := _parse_line(line.rstrip("\n"))) is not None
        ]
        self._source_model.replace(entries)
        self._anchor_to_tail()

    @Slot(logging.LogRecord)
    def _on_record(self, record: logging.LogRecord) -> None:
        """Append a live record and follow the tail when the user is at bottom."""
        # Sample before append so a user reading history is not pulled to the bottom.
        at_bottom = self._is_at_tail()
        self._source_model.append(_LogEntry.from_record(record))
        if at_bottom:
            self._anchor_to_tail()

    @Slot(int)
    def _on_category_changed(self, index: int) -> None:
        """Apply the selected dropdown value as the proxy category filter."""
        value = self._category_combo.itemData(index)
        if isinstance(value, str):
            self._proxy.set_category(value)
            self._anchor_to_tail()

    @Slot(str)
    def _on_search_changed(self, text: str) -> None:
        """Apply the search needle and anchor to the latest matching row."""
        self._proxy.set_needle(text)
        self._anchor_to_tail()

    @Slot()
    def _on_export_clicked(self) -> None:
        """Prompt for a destination file and write the visible rows to it."""
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export Logs",
            str(self._log_path.parent / "obcd_pilot_export.log"),
            "Log files (*.log);;Text files (*.txt);;All files (*)",
        )
        if not target:
            return
        Path(target).write_text(self._export_text(), encoding="utf-8")

    def _export_text(self) -> str:
        """Serialize visible rows in the log file format."""
        lines = [
            f"{entry.timestamp}  {entry.level:<7}  {entry.logger_name}: {entry.message}"
            for row in range(self._proxy.rowCount())
            if isinstance(
                entry := self._proxy.index(row, 0).data(_LogModel.EntryRole),
                _LogEntry,
            )
        ]
        return "\n".join(lines) + ("\n" if lines else "")

    def _update_count_label(self, *_: object) -> None:
        """Refresh the status bar count to reflect the proxy row count."""
        shown = self._proxy.rowCount()
        total = self._source_model.rowCount()
        text = (
            f"Showing {shown} entries"
            if shown == total
            else f"Showing {shown} of {total} entries"
        )
        self._count_label.setText(text)

    def _is_at_tail(self) -> bool:
        """Return True when the vertical scrollbar is parked at tail."""
        bar = self._view.verticalScrollBar()
        return bar.value() >= bar.maximum() - 4

    def _anchor_to_tail(self, deferred: bool = True) -> None:
        """Scroll to the bottom, inline or on the next event loop tick."""
        if deferred:
            QTimer.singleShot(0, self._view, self._view.scrollToBottom)
        else:
            self._view.scrollToBottom()

    def _create_toolbar(self) -> QWidget:
        """Build the top toolbar holding filter, search, refresh, and export."""
        bar = QWidget()
        bar.setObjectName("logs-toolbar")
        bar.setFixedHeight(48)
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)
        layout.addWidget(self._category_combo)
        layout.addWidget(self._search_input, stretch=1)
        layout.addWidget(self._refresh_btn)
        layout.addWidget(self._export_btn)
        bar.setLayout(layout)
        return bar

    def _create_statusbar(self) -> QWidget:
        """Build the bottom status bar holding the count and log file path."""
        bar = QWidget()
        bar.setObjectName("logs-statusbar")
        bar.setFixedHeight(28)
        separator = QFrame()
        separator.setObjectName("logs-separator")
        separator.setFixedWidth(1)
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)
        layout.addWidget(self._count_label)
        layout.addWidget(separator)
        layout.addWidget(self._path_label, stretch=1)
        bar.setLayout(layout)
        return bar

    @staticmethod
    def _create_category_combo() -> QComboBox:
        """Build the filter dropdown populated from _CATEGORIES."""
        combo = QComboBox()
        combo.setObjectName("logs-category")
        combo.setIconSize(QSize(13, 13))
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for label, value in _CATEGORIES:
            combo.addItem(_ICON_FILTER, label, value)
        return combo

    @staticmethod
    def _create_search_input() -> QLineEdit:
        """Build the search line edit with a leading magnifier icon."""
        edit = QLineEdit()
        edit.setObjectName("logs-search")
        edit.setPlaceholderText("Search logs...")
        edit.setClearButtonEnabled(True)
        edit.addAction(_ICON_SEARCH, QLineEdit.ActionPosition.LeadingPosition)
        return edit

    @staticmethod
    def _create_button(text: str, icon: QIcon) -> QPushButton:
        """Build a toolbar action button with consistent icon and text spacing."""
        button = QPushButton(icon, text)
        button.setObjectName("logs-tool-button")
        button.setIconSize(QSize(13, 13))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button


def _parse_line(line: str) -> _LogEntry | None:
    """Parse one log file line into a _LogEntry, or None if it does not match."""
    match = _LINE_RE.match(line)
    if match is None:
        return None
    return _LogEntry(
        timestamp=match["ts"],
        level=match["level"],
        logger_name=match["logger"],
        message=match["msg"],
    )
