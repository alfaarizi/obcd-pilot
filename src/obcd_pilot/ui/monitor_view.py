"""Main Monitoring view."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QWidget,
)

from obcd_pilot.ui.components.status_panel import StatusPanel
from obcd_pilot.ui.components.viewport import Viewport


class MonitorView(QWidget):
    """Monitoring view combines camera display and status panel."""

    def __init__(self) -> None:
        super().__init__()

        self._viewport = Viewport()
        self._status_panel = StatusPanel()

        # capture view and status panel side by side
        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._viewport, stretch=1)
        root.addWidget(self._status_panel)

        self.setLayout(root)
