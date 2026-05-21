"""Unit tests for VideoWorker state management and frame decoding."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from obcd_pilot.capture._types import Frame, Playback
from obcd_pilot.capture.video_worker import _FPS_FALLBACK, VideoWorker


@pytest.fixture()
def video_worker(qapp: object, tmp_path: Path) -> VideoWorker:
    """A VideoWorker pointing at a non-existent dummy path.

    The path is never opened by these tests; it is only used to satisfy
    the constructor signature.
    """
    return VideoWorker(path=tmp_path / "clip.mp4")


def _create_bgr_frame(height: int = 4, width: int = 6) -> np.ndarray:
    """Return a minimal BGR numpy array suitable for cv2.cvtColor."""
    return np.zeros((height, width, 3), dtype=np.uint8)


class TestVideoWorkerConstruction:
    """Tests for VideoWorker construction and initial state."""

    def test_initial_state_is_paused(self, video_worker: VideoWorker) -> None:
        """A freshly created VideoWorker is paused."""
        assert not video_worker.is_playing()

    def test_seek_index_is_none_at_start(self, video_worker: VideoWorker) -> None:
        """No seek is pending immediately after construction."""
        assert video_worker._seek_index is None

    def test_eof_flag_is_false_at_start(self, video_worker: VideoWorker) -> None:
        """is_eof starts False; the worker has not reached end-of-file."""
        assert not video_worker._is_eof


class TestVideoWorkerPlayPause:
    """Tests for the play/pause/is_playing state machine."""

    def test_play_sets_playing(self, video_worker: VideoWorker) -> None:
        """play() transitions the worker from paused to playing."""
        video_worker.play()
        assert video_worker.is_playing()

    def test_pause_clears_playing(self, video_worker: VideoWorker) -> None:
        """pause() transitions the worker from playing to paused."""
        video_worker.play()
        video_worker.pause()
        assert not video_worker.is_playing()

    def test_play_after_eof_resets_eof_flag(self, video_worker: VideoWorker) -> None:
        """play() called at EOF clears the EOF flag so playback can restart."""
        video_worker._is_eof = True
        video_worker.play()
        assert not video_worker._is_eof

    def test_play_after_eof_seeks_to_frame_zero(
        self, video_worker: VideoWorker
    ) -> None:
        """play() at EOF issues a seek to frame 0 to restart from the beginning."""
        video_worker._is_eof = True
        video_worker.play()
        assert video_worker._seek_index == 0

    def test_play_at_eof_sets_resume_flag(self, video_worker: VideoWorker) -> None:
        """play() at EOF sets resume=True so playback continues after the seek."""
        video_worker._is_eof = True
        video_worker.play()
        assert not video_worker._pause_after_seek

    def test_double_play_remains_playing(self, video_worker: VideoWorker) -> None:
        """Calling play() twice has no harmful side effect."""
        video_worker.play()
        video_worker.play()
        assert video_worker.is_playing()


class TestVideoWorkerSeek:
    """Tests for the seek() method."""

    def test_seek_stores_frame_index(self, video_worker: VideoWorker) -> None:
        """seek() records the requested frame index for the read loop to process."""
        video_worker.play()
        video_worker.seek(42)
        assert video_worker._seek_index == 42

    def test_seek_clears_eof(self, video_worker: VideoWorker) -> None:
        """seek() clears the EOF flag so the read loop does not stay paused."""
        video_worker._is_eof = True
        video_worker.play()
        video_worker.seek(0)
        assert not video_worker._is_eof

    def test_seek_while_paused_with_default_resume_pauses_after(
        self, video_worker: VideoWorker
    ) -> None:
        """seek() while paused (resume=None) schedules a pause after the seek."""
        assert not video_worker.is_playing()
        video_worker.seek(10)
        assert video_worker._pause_after_seek

    def test_seek_with_resume_true_does_not_pause_after(
        self, video_worker: VideoWorker
    ) -> None:
        """seek(resume=True) keeps playback running after the seek completes."""
        video_worker.seek(10, resume=True)
        assert not video_worker._pause_after_seek

    def test_seek_with_resume_false_pauses_after(
        self, video_worker: VideoWorker
    ) -> None:
        """seek(resume=False) pauses after the seek regardless of current state."""
        video_worker.play()
        video_worker.seek(10, resume=False)
        assert video_worker._pause_after_seek

    def test_seek_wakes_the_thread_event(self, video_worker: VideoWorker) -> None:
        """seek() sets the playing event so the read loop wakes up to process it."""
        video_worker.seek(5)
        assert video_worker._playing_event.is_set()


class TestVideoWorkerStop:
    """Tests for the stop() method."""

    def test_stop_calls_request_interruption(self, video_worker: VideoWorker) -> None:
        """stop() delegates to QThread.requestInterruption."""
        with patch.object(video_worker, "requestInterruption") as mock_ri:
            video_worker.stop()
        mock_ri.assert_called_once()

    def test_stop_wakes_the_thread_event(self, video_worker: VideoWorker) -> None:
        """stop() sets the playing event so a paused read loop can exit."""
        with patch.object(video_worker, "requestInterruption"):
            video_worker.stop()
        assert video_worker._playing_event.is_set()


class TestVideoWorkerRun:
    """Tests for VideoWorker.run – device-open error path."""

    def test_run_emits_error_when_file_cannot_be_opened(
        self, video_worker: VideoWorker
    ) -> None:
        """run() emits sig_error_occurred when VideoCapture cannot open the file."""
        errors: list[str] = []
        video_worker.sig_error_occurred.connect(errors.append)

        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = False

        with patch("cv2.VideoCapture", return_value=mock_capture):
            video_worker.run()

        assert len(errors) == 1
        assert "clip.mp4" in errors[0]

    def test_run_releases_capture_when_file_cannot_be_opened(
        self, video_worker: VideoWorker
    ) -> None:
        """run() releases VideoCapture even when the file fails to open."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = False

        with patch("cv2.VideoCapture", return_value=mock_capture):
            video_worker.run()

        mock_capture.release.assert_called_once()

    def test_run_releases_capture_on_success(self, video_worker: VideoWorker) -> None:
        """run() releases VideoCapture in its finally block."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True

        with (
            patch("cv2.VideoCapture", return_value=mock_capture),
            patch.object(video_worker, "_read"),
        ):
            video_worker.run()

        mock_capture.release.assert_called_once()


class TestVideoWorkerRead:
    """Tests for VideoWorker._read – called synchronously without a running thread."""

    def _create_capture(
        self,
        fps: float = 30.0,
        frame_count: int = 10,
        reads: list[tuple[bool, object]] | None = None,
    ) -> MagicMock:
        """Return a mock VideoCapture with predictable get/read behaviour."""
        import cv2

        prop_map = {
            cv2.CAP_PROP_FPS: fps,
            cv2.CAP_PROP_FRAME_COUNT: float(frame_count),
            cv2.CAP_PROP_POS_MSEC: 0.0,
            cv2.CAP_PROP_POS_FRAMES: 0.0,
        }
        mock = MagicMock()
        mock.get.side_effect = lambda p: prop_map.get(p, 0.0)

        if reads is not None:
            mock.read.side_effect = reads
        return mock

    def test_emits_frame_for_each_valid_read(self, video_worker: VideoWorker) -> None:
        """_read emits sig_frame once per successfully decoded frame."""
        frames: list[Frame] = []
        video_worker.sig_frame.connect(frames.append)
        video_worker.play()

        bgr = _create_bgr_frame()
        capture = self._create_capture(reads=[(True, bgr)] + [(False, None)] * 5)

        # Read one good frame, hit EOF (which pauses), then stop the loop.
        interrupted = [False, False, True]
        with (
            patch.object(
                video_worker, "isInterruptionRequested", side_effect=interrupted
            ),
            patch.object(video_worker, "msleep"),
        ):
            video_worker._read(capture)

        assert len(frames) == 1
        assert frames[0].fps == 30.0

    def test_emits_playback_signal_per_frame(self, video_worker: VideoWorker) -> None:
        """_read emits sig_playback alongside each frame signal."""
        playbacks: list[Playback] = []
        video_worker.sig_playback.connect(playbacks.append)
        video_worker.play()

        bgr = _create_bgr_frame()
        capture = self._create_capture(reads=[(True, bgr)] + [(False, None)] * 5)

        # Read one good frame, hit EOF (which pauses), then stop the loop.
        interrupted = [False, False, True]
        with (
            patch.object(
                video_worker, "isInterruptionRequested", side_effect=interrupted
            ),
            patch.object(video_worker, "msleep"),
        ):
            video_worker._read(capture)

        assert len(playbacks) >= 1

    def test_emits_end_of_file_on_failed_read(self, video_worker: VideoWorker) -> None:
        """_read emits sig_end_of_file and pauses when cv2 reports EOF."""
        eof_fired: list[bool] = []
        video_worker.sig_end_of_file.connect(lambda: eof_fired.append(True))
        video_worker.play()

        capture = self._create_capture(reads=[(False, None)] * 5)
        # First read fails immediately (EOF pauses), then stop the loop.
        interrupted = [False, True]
        with patch.object(
            video_worker, "isInterruptionRequested", side_effect=interrupted
        ):
            video_worker._read(capture)

        assert eof_fired

    def test_pauses_after_eof(self, video_worker: VideoWorker) -> None:
        """_read calls pause() when cv2 signals end-of-file."""
        video_worker.play()

        capture = self._create_capture(reads=[(False, None)] * 5)
        # First read fails immediately (EOF pauses), then stop the loop.
        interrupted = [False, True]
        with patch.object(
            video_worker, "isInterruptionRequested", side_effect=interrupted
        ):
            video_worker._read(capture)

        assert not video_worker.is_playing()

    def test_uses_fps_fallback_when_device_reports_zero(
        self, video_worker: VideoWorker
    ) -> None:
        """_read substitutes _FPS_FALLBACK when the file's FPS property is zero."""
        frames: list[Frame] = []
        video_worker.sig_frame.connect(frames.append)
        video_worker.play()

        bgr = _create_bgr_frame()
        capture = self._create_capture(
            fps=0.0, reads=[(True, bgr)] + [(False, None)] * 5
        )

        # Read one good frame, hit EOF (which pauses), then stop the loop.
        interrupted = [False, False, True]
        with (
            patch.object(
                video_worker, "isInterruptionRequested", side_effect=interrupted
            ),
            patch.object(video_worker, "msleep"),
        ):
            video_worker._read(capture)

        assert frames[0].fps == _FPS_FALLBACK

    def test_seek_repositions_capture(self, video_worker: VideoWorker) -> None:
        """_read calls capture.set to apply a pending seek_index."""
        import cv2

        video_worker.play()
        video_worker.seek(15, resume=True)

        bgr = _create_bgr_frame()
        capture = self._create_capture(reads=[(True, bgr)] + [(False, None)] * 5)

        # Read one good frame after the seek, hit EOF (which pauses), then stop the loop.
        interrupted = [False, False, True]
        with (
            patch.object(
                video_worker, "isInterruptionRequested", side_effect=interrupted
            ),
            patch.object(video_worker, "msleep"),
        ):
            video_worker._read(capture)

        capture.set.assert_any_call(cv2.CAP_PROP_POS_FRAMES, 15)

    def test_pause_after_seek_pauses_worker(self, video_worker: VideoWorker) -> None:
        """When _pause_after_seek is True, _read pauses the worker after seeking."""
        video_worker.seek(5, resume=False)

        bgr = _create_bgr_frame()
        capture = self._create_capture(reads=[(True, bgr)] + [(False, None)] * 5)
        # Seeking pauses the worker, stop the loop before it waits for playback to resume.
        interrupted = [False, True]
        with (
            patch.object(
                video_worker, "isInterruptionRequested", side_effect=interrupted
            ),
            patch.object(video_worker, "msleep"),
        ):
            video_worker._read(capture)

        assert not video_worker.is_playing()

    def test_exits_cleanly_when_interrupted_while_paused(
        self, video_worker: VideoWorker
    ) -> None:
        """_read exits without reading when interrupted while waiting for playback."""
        capture = self._create_capture()

        # Patch wait() to return immediately, then fire the interruption check.
        interrupted = [False, True]
        with (
            patch.object(video_worker, "isInterruptionRequested", side_effect=interrupted),
            patch.object(video_worker._playing_event, "wait"),
        ):
            video_worker._read(capture)

        capture.read.assert_not_called()

    def test_stops_immediately_when_interrupted(
        self, video_worker: VideoWorker
    ) -> None:
        """_read exits without reading any frames when already interrupted."""
        video_worker.play()
        capture = self._create_capture()

        with patch.object(video_worker, "isInterruptionRequested", return_value=True):
            video_worker._read(capture)

        capture.read.assert_not_called()
