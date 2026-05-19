from pathlib import Path
from threading import Event

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from obcd_pilot.capture._types import Frame, VideoInfo

_FPS_FALLBACK = 30.0


class VideoWorker(QThread):
    """Decode a video file and emit frames at the file's native rate."""

    sig_frame = Signal(Frame)
    sig_video_info = Signal(VideoInfo)
    sig_end_of_file = Signal()
    sig_error_occured = Signal(str)

    def __init__(self, path: Path) -> None:
        super().__init__()

        self._path = path
        self._playing_event = Event()
        self._seek_index: int | None = None
        self._pause_after_seek = False

        self.play()

    def play(self) -> None:
        """Start/Resume playback."""
        self._playing_event.set()

    def pause(self) -> None:
        """Pause playback."""
        self._playing_event.clear()

    def is_playing(self) -> bool:
        """Return True when the worker is not paused."""
        return self._playing_event.is_set()

    def seek(self, frame_index: int) -> None:
        """Request a seek to frame_index.

        Wakes the thread if paused to process the seek.
        """
        self._seek_index = frame_index
        self._pause_after_seek = not self.is_playing()
        # Wake thread to process seek
        self.play()

    def stop(self) -> None:
        """Request the worker to stop.

        Wakes the thread if paused to interrupt.
        """
        self.requestInterruption()
        # Wake thread to check interruption
        self.play()

    def run(self) -> None:
        """Open the file and read frames until stopped or EOF."""
        capture = cv2.VideoCapture(str(self._path))
        if not capture.isOpened():
            self.sig_error_occured.emit(f"Cannot open video file: {self._path.name}")
            return

        try:
            self._read(capture)
        finally:
            capture.release()

    def _read(self, capture: cv2.VideoCapture) -> None:
        """Read frames until interrupted or EOF."""
        fps = capture.get(cv2.CAP_PROP_FPS) or _FPS_FALLBACK
        frame_count = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        duration_ms = frame_count / fps * 1000.0
        frame_interval_ms = max(1, int(1000.0 / fps))

        while not self.isInterruptionRequested():
            self._playing_event.wait()
            if self.isInterruptionRequested():
                break

            seek_index = self._seek_index
            if seek_index is not None:
                self._seek_index = None
                capture.set(cv2.CAP_PROP_POS_FRAMES, seek_index)
                if self._pause_after_seek:
                    self.pause()
                    self._pause_after_seek = False

            ok, bgr = capture.read()
            # cv2 treats EOF as False
            if not ok:
                self.pause()
                self.sig_end_of_file.emit()
                continue

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

            self.sig_frame.emit(Frame(image, w, h, fps))
            self.sig_video_info.emit(
                VideoInfo(
                    capture.get(cv2.CAP_PROP_POS_MSEC),
                    duration_ms,
                    int(capture.get(cv2.CAP_PROP_POS_FRAMES)),
                    frame_count,
                )
            )

            self.msleep(frame_interval_ms)
