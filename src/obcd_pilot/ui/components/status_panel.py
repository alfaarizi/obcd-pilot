"""Status panel for object-based change detection."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot.ui import icons_rc  # noqa: F401
from obcd_pilot.ui.utils import separators

_ALARM_CHANNELS: list[str] = [
    "Pop-up",
    "Red text",
    "Sound",
    "Email",
    "HTTP post",
]


def _create_section_header(text: str) -> QLabel:
    """Return an uppercase, semi-bold section header label."""
    label = QLabel(text.upper())
    label.setObjectName("section-header")
    font = label.font()
    font.setWeight(QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
    label.setFont(font)
    return label


class StatusPanel(QWidget):
    """Right-side panel showing detection status and pipeline information."""

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("status-panel")
        self.setFixedWidth(240)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._create_detection_status())
        separator_1 = separators.create_h_separator()
        separator_1.setObjectName("panel-separator")
        root.addWidget(separator_1)

        root.addWidget(self._create_alarm_status(), stretch=1)
        separator_2 = separators.create_h_separator()
        separator_2.setObjectName("panel-separator")
        root.addWidget(separator_2)

        root.addWidget(self._create_detection_details())

        self.setLayout(root)

    def _create_detection_status(self) -> QWidget:
        """Create the large centered status indicator."""
        detection_status = QWidget()

        v_layout = QVBoxLayout()
        v_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.setContentsMargins(14, 16, 14, 16)
        v_layout.setSpacing(6)

        self._status_icon = QLabel()
        self._status_icon.setPixmap(QIcon(":/icons/circle-check-big.svg").pixmap(24, 24))
        self._status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_icon.setFixedSize(48, 48)
        v_layout.addWidget(self._status_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        self._status_label = QLabel("No change")
        self._status_label.setObjectName("status-label")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.addWidget(self._status_label)

        self._status_desc_label = QLabel("—")
        self._status_desc_label.setObjectName("status-desc-label")
        self._status_desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.addWidget(self._status_desc_label)

        detection_status.setLayout(v_layout)
        return detection_status

    def _create_alarm_status(self) -> QWidget:
        """Create an alarm channel list with status indicators."""
        alarm_status = QWidget()

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(14, 12, 14, 12)

        v_layout.addWidget(_create_section_header("Alarms"))

        grid_layout = QGridLayout()
        grid_layout.setSpacing(4)

        self._alarm_indicators: list[QLabel] = []
        self._alarm_names: list[QLabel] = []
        self._alarm_messages: list[QLabel] = []

        for row_idx, name in enumerate(_ALARM_CHANNELS):
            alarm_indicator = QLabel("●")
            alarm_indicator.setObjectName("alarm-dot")
            alarm_indicator.setFixedWidth(12)
            grid_layout.addWidget(alarm_indicator, row_idx, 0)
            self._alarm_indicators.append(alarm_indicator)

            alarm_name = QLabel(name)
            alarm_name.setObjectName("alarm-name")
            grid_layout.addWidget(alarm_name, row_idx, 1)
            self._alarm_names.append(alarm_name)

            alarm_message = QLabel("Sent")
            alarm_message.setObjectName("alarm-status")
            alarm_message.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid_layout.addWidget(alarm_message, row_idx, 2)
            self._alarm_messages.append(alarm_message)

        v_layout.addLayout(grid_layout)
        v_layout.addStretch(1)
        alarm_status.setLayout(v_layout)
        return alarm_status

    def _create_detection_details(self) -> QWidget:
        """Create the detection pipeline information."""
        detection_details = QWidget()

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(14, 12, 14, 12)

        v_layout.addWidget(_create_section_header("Details"))

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

        for field_name, value_label in (
            ("Model", self._model),
            ("Inference", self._inference),
            ("Confidence", self._confidence),
            ("RAM", self._ram),
        ):
            label = QLabel(field_name)
            label.setObjectName("detail-label")
            value_label.setObjectName("detail-value")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            form_layout.addRow(label, value_label)

        v_layout.addLayout(form_layout)
        detection_details.setLayout(v_layout)

        return detection_details
