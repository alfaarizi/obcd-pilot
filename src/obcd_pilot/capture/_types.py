"""Data types for the Capture module"""

from dataclasses import dataclass
from typing import NamedTuple

from PySide6.QtGui import QImage


class Frame(NamedTuple):
    """A single captured video frame."""

    image: QImage
    width: int
    height: int
    fps: float


class VideoInfo(NamedTuple):
    """Playback position emitted by ``VideoWorker``."""

    position_ms: float
    duration_ms: float
    frame_index: int
    frame_count: int


@dataclass(frozen=True, slots=True)
class CameraInfo:
    """An available camera device.

    Attributes:
        name: Human-readable label shown in the UI.
        index: OpenCV device index passed to ``cv2.VideoCapture``.
    """

    name: str
    index: int
