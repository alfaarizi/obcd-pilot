"""Playback controls overlay for video file."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot.capture import Playback
from obcd_pilot.ui import icons_rc  # noqa: F401

_ICON_PLAY = QIcon(":/icons/play.svg")
_ICON_PAUSE = QIcon(":/icons/pause.svg")
_ICON_CLOSE = QIcon(":/icons/close.svg")


def _format_timestamp(ms: float) -> str:
    """Convert milliseconds to mm:ss."""
    total_seconds = int(ms / 1000)
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


class PlaybackOverlay(QWidget):
    """Transparent overlay with video transport controls."""

    sig_video_played = Signal()
    sig_video_seek_started = Signal()
    sig_video_seek_moved = Signal(int)
    sig_video_seek_ended = Signal(int)
    sig_video_closed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("playback-overlay")

        self._last_playback: Playback | None = None
        self._is_playing = True
        self._is_seeking = False

        self._play_button = QToolButton()
        self._play_button.setObjectName("play-video-button")
        self._play_button.setIcon(_ICON_PAUSE)
        self._play_button.setIconSize(QSize(18, 18))
        self._play_button.setFixedSize(32, 32)
        self._play_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self._playback_slider = QSlider(Qt.Orientation.Horizontal)
        self._playback_slider.setObjectName("playback-slider")
        self._playback_slider.setRange(0, 0)

        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setObjectName("playback-time-label")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._time_label.setFixedWidth(100)

        self._close_button = QToolButton()
        self._close_button.setObjectName("close-video-button")
        self._close_button.setIcon(_ICON_CLOSE)
        self._close_button.setIconSize(QSize(18, 18))
        self._close_button.setFixedSize(32, 32)
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)

        playback_layout = QHBoxLayout()
        playback_layout.setContentsMargins(10, 0, 10, 8)
        playback_layout.addWidget(self._play_button, 0, Qt.AlignmentFlag.AlignVCenter)
        playback_layout.addWidget(self._playback_slider, stretch=1)
        playback_layout.addWidget(self._time_label, 0, Qt.AlignmentFlag.AlignVCenter)
        playback_layout.addWidget(self._close_button, 0, Qt.AlignmentFlag.AlignVCenter)

        playback_bar = QWidget()
        playback_bar.setObjectName("playback-bar")
        playback_bar.setFixedHeight(44)
        playback_bar.setLayout(playback_layout)

        # Layout
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch(1)
        root.addWidget(playback_bar)

        self.setLayout(root)

        # Signals
        self._close_button.clicked.connect(self.sig_video_closed.emit)
        self._play_button.clicked.connect(self._on_play_clicked)
        self._playback_slider.sliderPressed.connect(self._on_slider_pressed)
        self._playback_slider.sliderMoved.connect(self._on_slider_moved)
        self._playback_slider.sliderReleased.connect(self._on_slider_released)

    def update_position(self, playback: Playback) -> None:
        """Refresh the slider and time label from a playback signal."""
        self._last_playback = playback
        self._playback_slider.setRange(0, max(0, playback.frame_count - 1))

        if not self._is_seeking:
            self._playback_slider.setValue(playback.frame_index)
            self._time_label.setText(
                f"{_format_timestamp(playback.position_ms)} / "
                f"{_format_timestamp(playback.duration_ms)}"
            )

    def set_playing(self, is_playing: bool) -> None:
        """Update the play/pause icon to reflect external state."""
        self._is_playing = is_playing
        self._play_button.setIcon(_ICON_PAUSE if self._is_playing else _ICON_PLAY)

    def reset(self) -> None:
        """Reset controls to their initial state."""
        self._play_button.setIcon(_ICON_PAUSE)
        self._playback_slider.setValue(0)
        self._playback_slider.setRange(0, 0)
        self._time_label.setText("00:00 / 00:00")
        self._last_playback = None
        self._is_playing = True
        self._is_seeking = False

    def _on_play_clicked(self) -> None:
        """Toggle play/pause and update the icon."""
        self.set_playing(not self._is_playing)
        self.sig_video_played.emit()

    def _on_slider_pressed(self) -> None:
        """Suppress position updates while the user drags."""
        self._is_seeking = True
        self.sig_video_seek_started.emit()

    def _on_slider_moved(self, frame_index: int) -> None:
        """Update the time label as the user drags the slider."""
        if self._last_playback is None or self._last_playback.frame_count == 0:
            return

        position_ms = (
            frame_index / max(1, self._last_playback.frame_count - 1)
        ) * self._last_playback.duration_ms

        self._time_label.setText(
            f"{_format_timestamp(position_ms)} / "
            f"{_format_timestamp(self._last_playback.duration_ms)}"
        )

        self.sig_video_seek_moved.emit(frame_index)

    def _on_slider_released(self) -> None:
        """Emit a seek request when the user releases the slider."""
        self._is_seeking = False
        self.sig_video_seek_ended.emit(self._playback_slider.value())
