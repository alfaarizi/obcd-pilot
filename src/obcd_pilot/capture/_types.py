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


@dataclass(frozen=True, slots=True)
class Camera:
    """An available camera device.

    Attributes:
        name: Human-readable label shown in the UI.
        index: OpenCV device index passed to ``cv2.VideoCapture``.
    """

    name: str
    index: int
