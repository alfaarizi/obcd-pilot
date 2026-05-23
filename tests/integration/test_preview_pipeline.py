"""Integration tests for the OBCD pipeline wiring inside Preview."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytestqt.qtbot import QtBot

from obcd_pilot.capture._types import CameraInfo
from obcd_pilot.ui.components.preview import Preview

StubPipeline = tuple[MagicMock, MagicMock]


@pytest.fixture()
def preview(qtbot: QtBot, no_cameras: None) -> Preview:
    """A Preview widget with camera enumeration suppressed."""
    widget = Preview()
    qtbot.addWidget(widget)
    return widget


class TestStartPipeline:
    """Tests for Preview._start_pipeline."""

    def test_sets_worker_and_thread(
        self, preview: Preview, stub_pipeline: StubPipeline
    ) -> None:
        """_start_pipeline stores the created worker and thread."""
        worker_cls, thread_cls = stub_pipeline
        preview._start_pipeline()
        assert preview._obcd_worker is worker_cls.return_value
        assert preview._obcd_thread is thread_cls.return_value

    def test_moves_worker_to_thread_and_starts(
        self, preview: Preview, stub_pipeline: StubPipeline
    ) -> None:
        """_start_pipeline moves the worker to the thread and starts it."""
        worker_cls, thread_cls = stub_pipeline
        preview._start_pipeline()
        worker_cls.return_value.moveToThread.assert_called_once_with(
            thread_cls.return_value
        )
        thread_cls.return_value.start.assert_called_once()

    def test_relays_worker_signals(
        self, preview: Preview, stub_pipeline: StubPipeline
    ) -> None:
        """_start_pipeline relays the worker's signals through Preview's own."""
        worker_cls, _ = stub_pipeline
        preview._start_pipeline()
        worker = worker_cls.return_value
        worker.sig_detection.connect.assert_any_call(preview.sig_detection)
        worker.sig_model_ready.connect.assert_any_call(preview.sig_model_ready)

    def test_replaces_existing_pipeline(
        self, preview: Preview, stub_pipeline: StubPipeline
    ) -> None:
        """Calling _start_pipeline twice tears the first thread down."""
        _, thread_cls = stub_pipeline
        preview._start_pipeline()
        preview._start_pipeline()
        thread_cls.return_value.quit.assert_called_once()


class TestStopPipeline:
    """Tests for Preview._stop_pipeline."""

    def test_quits_waits_and_clears(
        self, preview: Preview, stub_pipeline: StubPipeline
    ) -> None:
        """_stop_pipeline quits the thread and clears the references."""
        _, thread_cls = stub_pipeline
        preview._start_pipeline()
        preview._stop_pipeline()
        thread_cls.return_value.quit.assert_called_once()
        thread_cls.return_value.wait.assert_called_once()
        assert preview._obcd_worker is None
        assert preview._obcd_thread is None

    def test_emits_reset(self, preview: Preview) -> None:
        """_stop_pipeline emits sig_pipeline_reset for downstream widgets."""
        received: list[bool] = []
        preview.sig_pipeline_reset.connect(lambda: received.append(True))
        preview._start_pipeline()
        preview._stop_pipeline()
        assert received == [True]

    def test_noop_without_thread(self, preview: Preview) -> None:
        """_stop_pipeline does nothing and emits nothing when idle."""
        received: list[bool] = []
        preview.sig_pipeline_reset.connect(lambda: received.append(True))
        preview._stop_pipeline()
        assert received == []


class TestSourceLifecycleDrivesPipeline:
    """Tests that starting/stopping a source starts/stops the pipeline."""

    def test_start_camera_connects_frames_to_pipeline(
        self, preview: Preview, stub_pipeline: StubPipeline, no_cameras: None
    ) -> None:
        """_start_camera feeds the camera's frames into the pipeline worker."""
        worker_cls, _ = stub_pipeline
        with patch("obcd_pilot.ui.components.preview.CameraWorker") as mock_camera:
            preview._start_camera(CameraInfo("Cam", 0))
        mock_camera.return_value.sig_frame.connect.assert_any_call(
            worker_cls.return_value.push_frame
        )

    def test_stop_camera_stops_pipeline(
        self, preview: Preview, stub_pipeline: StubPipeline, no_cameras: None
    ) -> None:
        """_stop_camera tears the pipeline down with the camera."""
        with patch("obcd_pilot.ui.components.preview.CameraWorker"):
            preview._start_camera(CameraInfo("Cam", 0))
        preview._stop_camera()
        assert preview._obcd_thread is None

    def test_load_video_connects_frames_to_pipeline(
        self, preview: Preview, stub_pipeline: StubPipeline, tmp_path: Path
    ) -> None:
        """_load_video feeds the video's frames into the pipeline worker."""
        worker_cls, _ = stub_pipeline
        with patch("obcd_pilot.ui.components.preview.VideoWorker") as mock_video:
            preview._load_video(tmp_path / "clip.mp4")
        mock_video.return_value.sig_frame.connect.assert_any_call(
            worker_cls.return_value.push_frame
        )

    def test_close_video_stops_pipeline(
        self, preview: Preview, stub_pipeline: StubPipeline, tmp_path: Path
    ) -> None:
        """_close_video tears the pipeline down with the video."""
        with patch("obcd_pilot.ui.components.preview.VideoWorker"):
            preview._load_video(tmp_path / "clip.mp4")
        preview._close_video()
        assert preview._obcd_thread is None
