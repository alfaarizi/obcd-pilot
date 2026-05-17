"""Video Widget.

Displays camera frames.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot.ui.utils import separators


class CapturePanel(QWidget):
    def __init__(self) -> None:
        super().__init__()

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addLayout(self._create_toolbar_layout())
        root.addStretch(1)

        self.setLayout(root)

    def _create_toolbar_layout(self) -> QHBoxLayout:
        """Create a toolbar at the top of the camera/video display."""
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(12, 8, 12, 8)
        h_layout.setSpacing(6)

        # QComboBox is Qt's standard dropdown
        self._cam_combo = QComboBox()
        self._cam_combo.addItem("Webcam 0")
        self._cam_combo.addItem("Webcam 1")
        self._cam_combo.setToolTip("Select Webcam")
        h_layout.addWidget(self._cam_combo)

        h_layout.addWidget(separators.create_v_separator())

        self._file_button: QPushButton = QPushButton("Open File")
        self._file_button.setToolTip("Upload a video")
        h_layout.addWidget(self._file_button)

        return h_layout
