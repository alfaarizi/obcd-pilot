"""Main Monitoring view."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QWidget,
)

from obcd_pilot.ui.components import Preview, StatusPanel


class MonitorView(QWidget):
    """Monitoring view combines camera display and status panel."""

    def __init__(self) -> None:
        super().__init__()

        self._preview = Preview()
        self._status_panel = StatusPanel()

        # capture view and status panel side by side
        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._preview, stretch=1)
        root.addWidget(self._status_panel)

        self.setLayout(root)

        self._preview.sig_detection.connect(self._status_panel.update_detection)
        self._preview.sig_model_ready.connect(self._status_panel.set_model_status)
        # Queued so the reset runs after any in-flight detection events.
        self._preview.sig_pipeline_reset.connect(
            self._status_panel.reset_detection,
            Qt.ConnectionType.QueuedConnection,
        )
