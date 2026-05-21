"""Video playback worker running on a dedicated QThread."""

import time
from pathlib import Path
from threading import Event

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from obcd_pilot.capture._types import Frame, Playback

_FPS_FALLBACK = 30.0


class VideoWorker(QThread):
    """Decode a video file and emit frames at the file's native rate."""

    sig_frame = Signal(Frame)
    sig_playback = Signal(Playback)
    sig_end_of_file = Signal()
    sig_error_occurred = Signal(str)

    def __init__(self, path: Path) -> None:
        super().__init__()

        self._path = path
        self._playing_event = Event()
        self._seek_index: int | None = None
        self._is_eof = False
        self._pause_after_seek = False

    def play(self) -> None:
        """Start/Resume playback."""
        if self._is_eof:
            self._is_eof = False
            self.seek(0, resume=True)
            return
        self._playing_event.set()

    def pause(self) -> None:
        """Pause playback."""
        self._playing_event.clear()

    def is_playing(self) -> bool:
        """Return True when the worker is not paused."""
        return self._playing_event.is_set()

    def seek(self, frame_index: int, *, resume: bool | None = None) -> None:
        """Request a seek to frame_index.

        Wakes the thread if paused to process the seek.
        """
        self._seek_index = frame_index
        self._is_eof = False
        self._pause_after_seek = not self.is_playing() if resume is None else not resume
        # Wake thread to process seek
        self._playing_event.set()

    def stop(self) -> None:
        """Request the worker to stop.

        Wakes the thread if paused to interrupt.
        """
        self.requestInterruption()
        # Wake thread to check interruption
        self._playing_event.set()

    def run(self) -> None:
        """Open the file and read frames until stopped or EOF."""
        capture = cv2.VideoCapture(str(self._path))
        if not capture.isOpened():
            self.sig_error_occurred.emit(f"Cannot open video file: {self._path.name}")
            return

        try:
            self._read(capture)
        finally:
            capture.release()

    def _read(self, capture: cv2.VideoCapture) -> None:
        """Read frames until interrupted or EOF."""
        fps = capture.get(cv2.CAP_PROP_FPS) or _FPS_FALLBACK
        frame_count = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        frame_timer_s = time.monotonic()
        frame_interval_s = 1.0 / fps
        duration_ms = frame_count / fps * 1000.0

        while not self.isInterruptionRequested():
            if not self.is_playing():
                self._playing_event.wait()
                if self.isInterruptionRequested():
                    break
                frame_timer_s = time.monotonic()

            seek_index = self._seek_index
            if seek_index is not None:
                self._seek_index = None
                self._is_eof = False
                capture.set(cv2.CAP_PROP_POS_FRAMES, seek_index)
                frame_timer_s = time.monotonic()
                if self._pause_after_seek:
                    self.pause()
                    self._pause_after_seek = False

            ok, bgr = capture.read()
            # cv2 treats EOF as False read
            if not ok:
                # mark video EOF before pausing
                self._is_eof = True
                self.pause()
                self.sig_playback.emit(
                    Playback(
                        duration_ms,
                        duration_ms,
                        max(0, frame_count - 1),
                        frame_count,
                    )
                )
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
            # POS_FRAMES is the next-to-read index, step back for the decoded frame.
            frame_index = max(0, int(capture.get(cv2.CAP_PROP_POS_FRAMES)) - 1)
            self.sig_playback.emit(
                Playback(
                    frame_index / fps * 1000.0,
                    duration_ms,
                    frame_index,
                    frame_count,
                )
            )

            if self._seek_index is None:
                frame_timer_s += frame_interval_s
                sleep_s = frame_timer_s - time.monotonic()
                if sleep_s > 0:
                    self.msleep(int(sleep_s * 1000))
