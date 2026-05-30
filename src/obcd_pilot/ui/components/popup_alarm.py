"""Notification toast for change detections.

A single alarm instance handles every alert. show_alert overwrites the content and
restarts the dismiss timer so rapid detections replace the toast rather than stacking.
"""

from datetime import datetime

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    Slot,
)
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot import alarm
from obcd_pilot.pipeline import Detection

_TOP_MARGIN = 14
_SIDE_MARGIN = 16
_MIN_WIDTH = 220
_MAX_WIDTH = 340
_SLIDE_OFFSET = 28
_PRESENT_DURATION_MS = 280
_DISMISS_DURATION_MS = 220


class PopupAlarm(QWidget):
    """Top center toast with slide and fade transitions."""

    def __init__(self, parent: QWidget) -> None:
        """Build the toast, the animation rig, and follow parent resizes."""
        super().__init__(parent)
        self.setObjectName("popup-alarm")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._parent = parent
        self._store = alarm.store()

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._dismiss)

        self._title_label = QLabel("Change detected")
        self._title_label.setObjectName("popup-alarm-title")

        self._time_label = QLabel()
        self._time_label.setObjectName("popup-alarm-time")

        self._meta_label = QLabel()
        self._meta_label.setObjectName("popup-alarm-meta")
        self._meta_label.setWordWrap(True)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(self._title_label, stretch=1)
        header.addWidget(self._time_label, alignment=Qt.AlignmentFlag.AlignRight)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(2)
        root.addLayout(header)
        root.addWidget(self._meta_label)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._slide = QPropertyAnimation(self, b"pos", self)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._animation = QParallelAnimationGroup(self)
        self._animation.addAnimation(self._slide)
        self._animation.addAnimation(self._fade)
        self._animation.finished.connect(self._on_animation_finished)
        self._is_dismissing = False

        self.hide()
        parent.installEventFilter(self)

    @Slot(Detection)
    def show_alert(self, detection: Detection) -> None:
        """Surface detection if the pop-up channel is enabled.

        Restarts the dismiss timer on every call so rapid detections replace
        the current toast instead of stacking.
        """
        settings = self._store.settings
        if not settings.popup_enabled or not detection.change_detected:
            return
        self._time_label.setText(_format_time(detection.timestamp_ms))
        self._meta_label.setText(_format_meta(detection))
        self._fit_to_parent()
        self._present()
        self._dismiss_timer.start(settings.popup_timeout_s * 1000)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Overloaded Qt method.

        Begin dismissal on left click so user can clear the toast manually.
        """
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self._dismiss()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Overloaded Qt method.

        Reanchor on parent resize. When an animation is in flight we re-target
        the slide's x end value instead so a resize mid-present or mid-dismiss
        still converges on the new horizontal center.
        """
        if watched is self._parent and event.type() == QEvent.Type.Resize:
            target = self._target_pos()
            if self._animation.state() == QAbstractAnimation.State.Stopped:
                self.move(target)
            else:
                end = self._slide.endValue()
                self._slide.setEndValue(QPoint(target.x(), end.y()))
        return super().eventFilter(watched, event)

    def _present(self) -> None:
        """Slide down and fade in to the target position at full opacity."""
        self._animation.stop()
        self._is_dismissing = False
        target = self._target_pos()
        if self.isHidden():
            self.move(target.x(), target.y() - _SLIDE_OFFSET)
            self.show()
            self.raise_()
        self._animate_to(
            target=target,
            opacity=1.0,
            duration_ms=_PRESENT_DURATION_MS,
            easing=QEasingCurve.Type.OutCubic,
        )

    def _dismiss(self) -> None:
        """Slide up and fade out, then hide once the animation completes."""
        if self.isHidden() or self._is_dismissing:
            return
        self._dismiss_timer.stop()
        self._animation.stop()
        self._is_dismissing = True
        target = QPoint(self.x(), self._target_pos().y() - _SLIDE_OFFSET)
        self._animate_to(
            target=target,
            opacity=0.0,
            duration_ms=_DISMISS_DURATION_MS,
            easing=QEasingCurve.Type.InCubic,
        )

    def _animate_to(
        self,
        target: QPoint,
        opacity: float,
        duration_ms: int,
        easing: QEasingCurve.Type,
    ) -> None:
        """Drive the slide and fade animations toward the given targets."""
        self._slide.setDuration(duration_ms)
        self._slide.setEasingCurve(easing)
        self._slide.setStartValue(self.pos())
        self._slide.setEndValue(target)

        self._fade.setDuration(duration_ms)
        self._fade.setEasingCurve(easing)
        self._fade.setStartValue(self._opacity.opacity())
        self._fade.setEndValue(opacity)

        self._animation.start()

    def _on_animation_finished(self) -> None:
        """Hide the widget once a dismiss animation completes."""
        if self._is_dismissing:
            self.hide()
            self._is_dismissing = False

    def _fit_to_parent(self) -> None:
        """Resize to fit the parent's current width within sane bounds."""
        available = self._parent.width() - 2 * _SIDE_MARGIN
        self.setFixedWidth(max(_MIN_WIDTH, min(_MAX_WIDTH, available)))
        self.adjustSize()

    def _target_pos(self) -> QPoint:
        """Return the top center anchor point inside the parent preview."""
        x = max(0, (self._parent.width() - self.width()) // 2)
        return QPoint(x, _TOP_MARGIN)


def _format_time(timestamp_ms: float) -> str:
    """Render the wall clock timestamp."""
    return datetime.fromtimestamp(timestamp_ms / 1000.0).strftime("%H:%M:%S")


def _format_meta(detection: Detection) -> str:
    """Render the confidence score as the meta line."""
    return f"Confidence {detection.confidence * 100:.0f}%"
