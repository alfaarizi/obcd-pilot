"""Camera capture worker running on a dedicated QThread."""

import platform

import cv2
from cv2_enumerate_cameras import enumerate_cameras as enumerate_cameras
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from obcd_pilot.capture._types import CameraInfo, Frame

_TARGET_WIDTH = 1280
_TARGET_HEIGHT = 720

_BACKENDS = {
    "Darwin": cv2.CAP_AVFOUNDATION,
    "Linux": cv2.CAP_V4L2,
    "Windows": cv2.CAP_MSMF,
}


def retrieve_cameras() -> list[CameraInfo]:
    """Enumerate available cameras with names and indices."""
    backend = _BACKENDS.get(platform.system(), cv2.CAP_ANY)
    return [CameraInfo(info.name, info.index) for info in enumerate_cameras(backend)]


class CameraWorker(QThread):
    """Capture loop that reads frames from a single camera device."""

    sig_frame = Signal(Frame)
    sig_error_occurred = Signal(str)

    def __init__(self, camera_index: int = 0) -> None:
        super().__init__()
        self._camera_index = camera_index

    def stop(self) -> None:
        self.requestInterruption()

    def run(self) -> None:
        capture = cv2.VideoCapture(self._camera_index)
        if not capture.isOpened():
            error = f"Cannot open camera at index {self._camera_index}."
            self.sig_error_occurred.emit(error)
            return

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, _TARGET_WIDTH)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, _TARGET_HEIGHT)

        try:
            self._read(capture)
        finally:
            capture.release()

    def _read(self, capture: cv2.VideoCapture) -> None:
        """Read frames until stopped or the device fails."""

        while not self.isInterruptionRequested():
            ok, bgr = capture.read()
            if not ok:
                self.sig_error_occurred.emit("Camera read failed.")
                break

            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w

            image = QImage(
                rgb.data,
                w,
                h,
                bytes_per_line,
                QImage.Format.Format_RGB888,
            ).copy()

            fps = capture.get(cv2.CAP_PROP_FPS)
            self.sig_frame.emit(Frame(image, w, h, fps))

            frame_interval_ms = max(1, int(1000.0 / fps))
            self.msleep(frame_interval_ms)
