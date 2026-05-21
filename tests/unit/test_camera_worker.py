"""Unit tests for CameraWorker."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from obcd_pilot.capture.camera_worker import (
    _MAX_CONSECUTIVE_FAILURES,
    CameraWorker,
)


@pytest.fixture()
def camera_worker(qapp: object) -> CameraWorker:
    """A CameraWorker targeting device index 0."""
    return CameraWorker(camera_index=0)


def _create_bgr_frame(height: int = 4, width: int = 6) -> np.ndarray:
    """Return a minimal BGR numpy array suitable for cv2.cvtColor."""
    return np.zeros((height, width, 3), dtype=np.uint8)


class TestCameraWorkerConstruction:
    """Tests for CameraWorker construction."""

    def test_stores_camera_index(self, qapp: object) -> None:
        """The camera index passed at construction is retained."""
        w = CameraWorker(camera_index=2)
        assert w._camera_index == 2

    def test_default_camera_index_is_zero(self, qapp: object) -> None:
        """Omitting camera_index defaults to device 0."""
        w = CameraWorker()
        assert w._camera_index == 0


class TestCameraWorkerStop:
    """Tests for CameraWorker.stop."""

    def test_stop_calls_request_interruption(self, camera_worker: CameraWorker) -> None:
        """stop() delegates to QThread.requestInterruption."""
        with patch.object(camera_worker, "requestInterruption") as mock_ri:
            camera_worker.stop()
        mock_ri.assert_called_once()


class TestCameraWorkerRun:
    """Tests for CameraWorker.run – executed synchronously via _read injection."""

    def test_run_emits_error_when_device_cannot_be_opened(
        self, camera_worker: CameraWorker
    ) -> None:
        """run() emits sig_error_occurred when VideoCapture fails to open."""
        errors: list[str] = []
        camera_worker.sig_error_occurred.connect(errors.append)

        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = False

        with patch("cv2.VideoCapture", return_value=mock_capture):
            camera_worker.run()

        assert len(errors) == 1
        assert "0" in errors[0]

    def test_run_releases_capture_when_device_cannot_be_opened(
        self, camera_worker: CameraWorker
    ) -> None:
        """run() releases VideoCapture even when the device fails to open."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = False

        with patch("cv2.VideoCapture", return_value=mock_capture):
            camera_worker.run()

        mock_capture.release.assert_called_once()

    def test_run_releases_capture_after_reading(
        self, camera_worker: CameraWorker
    ) -> None:
        """run() releases the VideoCapture object even after _read returns."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True

        with (
            patch("cv2.VideoCapture", return_value=mock_capture),
            patch.object(camera_worker, "_read"),
        ):
            camera_worker.run()

        mock_capture.release.assert_called_once()

    def test_run_sets_resolution_properties(self, camera_worker: CameraWorker) -> None:
        """run() configures WIDTH and HEIGHT capture properties before reading."""
        import cv2 as _cv2

        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        set_calls: list[tuple[int, float]] = []

        def record_set(prop: int, value: float) -> bool:
            set_calls.append((prop, value))
            return True

        mock_capture.set.side_effect = record_set

        with (
            patch("cv2.VideoCapture", return_value=mock_capture),
            patch.object(camera_worker, "_read"),
        ):
            camera_worker.run()

        props = {prop for prop, _ in set_calls}
        assert _cv2.CAP_PROP_FRAME_WIDTH in props
        assert _cv2.CAP_PROP_FRAME_HEIGHT in props


class TestCameraWorkerRead:
    """Tests for CameraWorker._read – called synchronously without a thread."""

    def test_emits_error_after_max_consecutive_failures(
        self, camera_worker: CameraWorker
    ) -> None:
        """_read emits sig_error_occurred after MAX_CONSECUTIVE_FAILURES bad reads."""
        errors: list[str] = []
        camera_worker.sig_error_occurred.connect(errors.append)

        mock_capture = MagicMock()
        mock_capture.read.return_value = (False, None)
        mock_capture.get.return_value = 30.0

        with patch.object(camera_worker, "isInterruptionRequested", return_value=False):
            camera_worker._read(mock_capture)

        assert errors == ["Camera read failed."]
        assert mock_capture.read.call_count == _MAX_CONSECUTIVE_FAILURES

    def test_emits_frame_on_successful_read(self, camera_worker: CameraWorker) -> None:
        """_read emits sig_frame once for each successful capture.read() call."""
        from obcd_pilot.capture._types import Frame

        frames: list[Frame] = []
        camera_worker.sig_frame.connect(frames.append)

        bgr = _create_bgr_frame()
        mock_capture = MagicMock()
        mock_capture.get.return_value = 30.0
        mock_capture.read.side_effect = [
            (True, bgr),
            (False, None),
        ] * _MAX_CONSECUTIVE_FAILURES

        interrupted = [False] + [True] * 20
        with patch.object(
            camera_worker, "isInterruptionRequested", side_effect=interrupted
        ):
            camera_worker._read(mock_capture)

        assert len(frames) == 1
        assert frames[0].width == bgr.shape[1]
        assert frames[0].height == bgr.shape[0]
        assert frames[0].fps == 30.0

    def test_uses_fps_fallback_when_capture_reports_zero(
        self, camera_worker: CameraWorker
    ) -> None:
        """_read substitutes _FPS_FALLBACK when the device reports fps=0."""
        from obcd_pilot.capture._types import Frame
        from obcd_pilot.capture.camera_worker import _FPS_FALLBACK

        frames: list[Frame] = []
        camera_worker.sig_frame.connect(frames.append)

        bgr = _create_bgr_frame()
        mock_capture = MagicMock()
        mock_capture.get.return_value = 0.0
        mock_capture.read.side_effect = [
            (True, bgr),
            (False, None),
        ] * _MAX_CONSECUTIVE_FAILURES

        interrupted = [False] + [True] * 20
        with patch.object(
            camera_worker, "isInterruptionRequested", side_effect=interrupted
        ):
            camera_worker._read(mock_capture)

        assert frames[0].fps == _FPS_FALLBACK

    def test_stops_immediately_on_interruption(
        self, camera_worker: CameraWorker
    ) -> None:
        """_read exits the loop without reading when interrupted from the start."""
        mock_capture = MagicMock()
        mock_capture.get.return_value = 30.0

        with patch.object(camera_worker, "isInterruptionRequested", return_value=True):
            camera_worker._read(mock_capture)

        mock_capture.read.assert_not_called()

    def test_resets_failure_count_on_successful_read(
        self, camera_worker: CameraWorker
    ) -> None:
        """A successful read resets the consecutive-failure counter to zero."""
        errors: list[str] = []
        camera_worker.sig_error_occurred.connect(errors.append)

        bgr = _create_bgr_frame()
        mock_capture = MagicMock()
        mock_capture.get.return_value = 30.0

        reads = (
            [(False, None)] * (_MAX_CONSECUTIVE_FAILURES - 1)
            + [(True, bgr)]
            + [(False, None)] * _MAX_CONSECUTIVE_FAILURES
        )
        mock_capture.read.side_effect = reads

        n_reads = len(reads)
        interrupted = [False] * n_reads + [True] * 5
        with patch.object(
            camera_worker, "isInterruptionRequested", side_effect=interrupted
        ):
            camera_worker._read(mock_capture)

        assert len(errors) == 1
