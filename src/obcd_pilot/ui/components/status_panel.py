"""Status panel for object-based change detection."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot.ui.utils import separators

_ALARM_CHANNELS: list[str] = [
    "Pop-up",
    "Red text",
    "Sound",
    "Email",
    "HTTP post",
]


class StatusPanel(QWidget):
    """Right-side panel showing detection status and pipeline informations."""

    def __init__(self) -> None:
        super().__init__()

        self.setFixedWidth(200)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._create_detection_status())
        root.addWidget(separators.create_h_separator())

        root.addWidget(self._create_alarm_status(), stretch=1)
        root.addWidget(separators.create_h_separator())

        root.addWidget(self._create_detection_details())
        root.addWidget(separators.create_h_separator())

        self.setLayout(root)

    def _create_detection_status(self) -> QWidget:
        """Create the large centered status indicator."""
        detection_status = QWidget()

        v_layout = QVBoxLayout()
        v_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.setContentsMargins(14, 16, 14, 16)

        self._status_icon = QLabel()
        self._status_icon.setPixmap(QIcon.fromTheme("checkmark").pixmap(24, 24))
        self._status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_icon.setFixedSize(48, 48)
        v_layout.addWidget(self._status_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        self._status_label = QLabel("No change")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.addWidget(self._status_label)

        self._status_desc_label = QLabel("—")
        self._status_desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.addWidget(self._status_desc_label)

        detection_status.setLayout(v_layout)

        return detection_status

    def _create_alarm_status(self) -> QWidget:
        """Create an alarm channel list with status indicators."""
        alarm_status = QWidget()

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(14, 12, 14, 12)

        header = QLabel("Alarms")
        v_layout.addWidget(header)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(4)

        self._alarm_indicators: list[QLabel] = []
        self._alarm_names: list[QLabel] = []
        self._alarm_messages: list[QLabel] = []

        for row_idx, name in enumerate(_ALARM_CHANNELS):
            alarm_indicator = QLabel("●")
            alarm_indicator.setFixedWidth(12)
            grid_layout.addWidget(alarm_indicator, row_idx, 0)
            self._alarm_indicators.append(alarm_indicator)

            alarm_name = QLabel(name)
            grid_layout.addWidget(alarm_name, row_idx, 1)
            self._alarm_names.append(alarm_name)

            alarm_message = QLabel("Sent")
            alarm_message.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid_layout.addWidget(alarm_message, row_idx, 2)
            self._alarm_messages.append(alarm_message)

        v_layout.addLayout(grid_layout)
        v_layout.addStretch(1)
        alarm_status.setLayout(v_layout)

        return alarm_status

    def _create_detection_details(self) -> QWidget:
        """Create the detection pipeline informations."""
        detection_details = QWidget()

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(14, 12, 14, 12)

        header = QLabel("Details")
        v_layout.addWidget(header)

        form_layout = QFormLayout()
        form_layout.setSpacing(6)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self._model = QLabel("—")
        self._inference = QLabel("—")
        self._confidence = QLabel("—")
        self._ram = QLabel("—")

        for value_label in (
            self._model,
            self._inference,
            self._confidence,
            self._ram,
        ):
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        form_layout.addRow("Model", self._model)
        form_layout.addRow("Inference", self._inference)
        form_layout.addRow("Confidence", self._confidence)
        form_layout.addRow("RAM", self._ram)

        v_layout.addLayout(form_layout)
        detection_details.setLayout(v_layout)

        return detection_details
