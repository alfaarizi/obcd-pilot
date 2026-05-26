"""Status panel for object-based change detection."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot.pipeline import Detection
from obcd_pilot.ui import icons_rc  # noqa: F401
from obcd_pilot.ui.utils import separators

_ICON_NO_CHANGE = QIcon(":/icons/message-circle-check.svg")
_ICON_CHANGE = QIcon(":/icons/triangle-alert.svg")
_ICON_SIZE = 28

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

        self._status_icon = QLabel()
        self._status_icon.setPixmap(_ICON_NO_CHANGE.pixmap(_ICON_SIZE, _ICON_SIZE))
        self._status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_icon.setFixedSize(_ICON_SIZE, _ICON_SIZE)

        self._status_label = QLabel("No change")
        self._status_label.setObjectName("status-label")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._status_desc_label = QLabel("—")
        self._status_desc_label.setObjectName("status-desc-label")
        self._status_desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._model = QLabel("—")
        self._inference = QLabel("—")
        self._confidence = QLabel("—")

        self._alarm_indicators: list[QLabel] = []
        self._alarm_names: list[QLabel] = []
        self._alarm_messages: list[QLabel] = []
        for name in _ALARM_CHANNELS:
            indicator = QLabel("●")
            indicator.setObjectName("alarm-dot")
            indicator.setFixedWidth(12)
            self._alarm_indicators.append(indicator)

            name_label = QLabel(name)
            name_label.setObjectName("alarm-name")
            self._alarm_names.append(name_label)

            message = QLabel("Sent")
            message.setObjectName("alarm-status")
            message.setAlignment(Qt.AlignmentFlag.AlignRight)
            self._alarm_messages.append(message)

        separator_1 = separators.create_h_separator()
        separator_1.setObjectName("panel-separator")
        separator_2 = separators.create_h_separator()
        separator_2.setObjectName("panel-separator")

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._create_detection_status())
        root.addWidget(separator_1)
        root.addWidget(self._create_alarm_status(), stretch=1)
        root.addWidget(separator_2)
        root.addWidget(self._create_detection_details())
        self.setLayout(root)

    @Slot(str)
    def set_model_status(self, name: str) -> None:
        """Show the active model's name in the details section."""
        self._model.setText(name)

    @Slot(Detection)
    def update_detection(self, detection: Detection) -> None:
        """Render the latest detection result from the pipeline."""
        changed = detection.change_detected
        icon = _ICON_CHANGE if changed else _ICON_NO_CHANGE
        self._status_icon.setPixmap(icon.pixmap(_ICON_SIZE, _ICON_SIZE))
        self._status_label.setText("Change detected" if changed else "No change")
        self._status_desc_label.setText(f"Frame {detection.frame_id}")
        self._confidence.setText(f"{detection.confidence:.2f}")
        self._inference.setText(f"{detection.inference_ms:.0f} ms")
        self._set_changed(changed)

    @Slot()
    def reset_detection(self) -> None:
        """Restore the idle state when the pipeline is torn down with the source."""
        self._status_icon.setPixmap(_ICON_NO_CHANGE.pixmap(_ICON_SIZE, _ICON_SIZE))
        self._status_label.setText("No change")
        self._status_desc_label.setText("—")
        self._model.setText("—")
        self._inference.setText("—")
        self._confidence.setText("—")
        self._set_changed(False)

    def _set_changed(self, changed: bool) -> None:
        """Toggle the changed style property so the QSS can recolour."""
        for widget in (
            self._detection_status,
            self._status_label,
            self._status_desc_label,
        ):
            widget.setProperty("changed", changed)
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)

    def _create_detection_status(self) -> QWidget:
        """Assemble the centred status indicator section."""
        self._detection_status = QWidget()
        self._detection_status.setObjectName("detection-status")
        self._detection_status.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(2)
        layout.addWidget(self._status_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(2)
        layout.addWidget(self._status_label)
        layout.addSpacing(4)
        layout.addWidget(self._status_desc_label)

        self._detection_status.setLayout(layout)
        return self._detection_status

    def _create_alarm_status(self) -> QWidget:
        """Assemble the alarm channel grid section."""
        grid = QGridLayout()
        grid.setSpacing(4)
        rows = zip(
            self._alarm_indicators,
            self._alarm_names,
            self._alarm_messages,
            strict=True,
        )
        for row_idx, (indicator, name, message) in enumerate(rows):
            grid.addWidget(indicator, row_idx, 0)
            grid.addWidget(name, row_idx, 1)
            grid.addWidget(message, row_idx, 2)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(_create_section_header("Alarms"))
        layout.addLayout(grid)
        layout.addStretch(1)

        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _create_detection_details(self) -> QWidget:
        """Assemble the details form section."""
        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for field_name, value_label in (
            ("Model", self._model),
            ("Inference", self._inference),
            ("Confidence", self._confidence),
        ):
            label = QLabel(field_name)
            label.setObjectName("detail-label")
            value_label.setObjectName("detail-value")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            form.addRow(label, value_label)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(_create_section_header("Details"))
        layout.addLayout(form)

        widget = QWidget()
        widget.setLayout(layout)
        return widget
