"""Integration tests for _Canvas and Preview widget."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction, QImage
from pytestqt.qtbot import QtBot

from obcd_pilot.capture import CameraInfo
from obcd_pilot.pipeline import Detection
from obcd_pilot.ui.components.preview import Preview, _Canvas, _ChangeOverlay


@pytest.fixture()
def canvas(qtbot: QtBot) -> _Canvas:
    """A _Canvas widget registered with qtbot for cleanup."""
    widget = _Canvas()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture()
def preview(qtbot: QtBot, no_cameras: None) -> Preview:
    """A Preview widget with camera enumeration suppressed."""
    widget = Preview()
    qtbot.addWidget(widget)
    return widget


def _create_solid_image(width: int = 16, height: int = 12) -> QImage:
    """Return a solid-colour QImage for use in canvas tests."""
    image = QImage(width, height, QImage.Format.Format_RGB888)
    image.fill(Qt.GlobalColor.red)
    return image


class TestCanvasState:
    """Tests for _Canvas internal state management."""

    def test_starts_with_no_image(self, canvas: _Canvas) -> None:
        """_Canvas holds no image immediately after construction."""
        assert canvas._image is None

    def test_set_stores_image(self, canvas: _Canvas) -> None:
        """set() replaces the internal image reference."""
        image = _create_solid_image()
        canvas.set(image)
        assert canvas._image is image

    def test_set_replaces_previous_image(self, canvas: _Canvas) -> None:
        """Calling set() twice leaves only the most recent image."""
        first = _create_solid_image(8, 6)
        second = _create_solid_image(16, 12)
        canvas.set(first)
        canvas.set(second)
        assert canvas._image is second

    def test_clear_removes_image(self, canvas: _Canvas) -> None:
        """clear() sets the internal image to None."""
        canvas.set(_create_solid_image())
        canvas.clear()
        assert canvas._image is None


class TestCanvasPaint:
    """Tests for _Canvas.paintEvent."""

    def test_paint_with_no_image_does_not_raise(
        self, canvas: _Canvas, qtbot: QtBot
    ) -> None:
        """paintEvent with _image=None completes without raising."""
        canvas.resize(100, 80)
        canvas.show()
        qtbot.waitExposed(canvas)
        canvas.update()

    def test_paint_with_image_does_not_raise(
        self, canvas: _Canvas, qtbot: QtBot
    ) -> None:
        """paintEvent with a valid QImage completes without raising."""
        canvas.set(_create_solid_image())
        canvas.resize(100, 80)
        canvas.show()
        qtbot.waitExposed(canvas)
        canvas.update()

    def test_paint_after_clear_does_not_raise(
        self, canvas: _Canvas, qtbot: QtBot
    ) -> None:
        """paintEvent after clear() does not raise even with no image."""
        canvas.set(_create_solid_image())
        canvas.clear()
        canvas.resize(100, 80)
        canvas.show()
        qtbot.waitExposed(canvas)
        canvas.update()


class TestPreviewConstruction:
    """Tests for Preview widget construction and initial state."""

    def test_constructs_without_error(self, preview: Preview) -> None:
        """Preview can be created when camera enumeration returns no devices."""
        assert preview is not None

    def test_initial_camera_worker_is_none(self, preview: Preview) -> None:
        """No camera capture is started until the user requests it."""
        assert preview._camera_worker is None

    def test_initial_video_worker_is_none(self, preview: Preview) -> None:
        """No video playback is started at construction."""
        assert preview._video_worker is None

    def test_playback_overlay_is_hidden_at_start(self, preview: Preview) -> None:
        """The playback overlay is invisible until a video is loaded."""
        assert not preview._playback_overlay.isVisible()

    def test_canvas_message_visible_when_no_cameras(self, preview: Preview) -> None:
        """Canvas message overlay is shown at startup when no camera is detected."""
        assert not preview._canvas_message.isHidden()

    def test_initial_cameras_list_is_empty(
        self, preview: Preview, no_cameras: None
    ) -> None:
        """_cameras is empty when no devices are enumerated."""
        assert preview._cameras == []

    def test_current_camera_is_none_when_no_devices(
        self, preview: Preview, no_cameras: None
    ) -> None:
        """_current_camera is None when retrieve_cameras returns an empty list."""
        assert preview._current_camera is None


class TestPreviewSetCameras:
    """Tests for Preview._set_cameras."""

    def test_set_cameras_populates_camera_list(self, preview: Preview) -> None:
        """_set_cameras replaces the internal camera list."""
        cameras = [CameraInfo("Cam A", 0), CameraInfo("Cam B", 1)]
        preview._set_cameras(cameras)
        assert preview._cameras == cameras

    def test_set_cameras_selects_first_as_current(self, preview: Preview) -> None:
        """_set_cameras makes the first camera the current selection."""
        cameras = [CameraInfo("Cam A", 0), CameraInfo("Cam B", 1)]
        preview._set_cameras(cameras)
        assert preview._current_camera == cameras[0]

    def test_set_cameras_adds_menu_actions(self, preview: Preview) -> None:
        """_set_cameras populates the camera menu with one action per device."""
        cameras = [CameraInfo("Front", 0), CameraInfo("Rear", 1)]
        preview._set_cameras(cameras)
        assert len(preview._camera_menu.actions()) == 2

    def test_set_cameras_replaces_previous_entries(self, preview: Preview) -> None:
        """Calling _set_cameras twice leaves only the most recent camera list."""
        preview._set_cameras([CameraInfo("Old", 0)])
        preview._set_cameras([CameraInfo("New", 1), CameraInfo("Also New", 2)])
        assert len(preview._camera_menu.actions()) == 2

    def test_set_cameras_with_empty_list_clears_menu(self, preview: Preview) -> None:
        """_set_cameras([]) removes all menu entries and clears the current camera."""
        preview._set_cameras([CameraInfo("Cam", 0)])
        preview._set_cameras([])
        assert preview._camera_menu.actions() == []

    def test_set_cameras_shows_message_when_empty(self, preview: Preview) -> None:
        """_set_cameras([]) shows the canvas message overlay."""
        preview._set_cameras([])
        assert not preview._canvas_message.isHidden()

    def test_set_cameras_hides_message_when_populated(self, preview: Preview) -> None:
        """_set_cameras hides the canvas message overlay when cameras are available."""
        preview._set_cameras([CameraInfo("Cam A", 0)])
        assert preview._canvas_message.isHidden()


class TestPreviewCameraHandlers:
    """Tests for camera-related event handlers."""

    def test_stop_camera_is_noop_when_no_worker(self, preview: Preview) -> None:
        """_stop_camera does not raise when no camera worker is running."""
        preview._stop_camera()

    def test_close_video_is_noop_when_no_worker(self, preview: Preview) -> None:
        """_close_video does not raise when no video worker is running."""
        preview._close_video()

    def test_on_camera_clicked_does_nothing_without_current_camera(
        self, preview: Preview
    ) -> None:
        """_on_camera_clicked is a no-op when _current_camera is None."""
        assert preview._current_camera is None
        preview._on_camera_clicked()

    def test_on_video_ended_sets_playing_false(self, preview: Preview) -> None:
        """_on_video_ended updates the playback overlay to the paused state."""
        preview._on_video_ended()
        assert not preview._playback_overlay._is_playing

    def test_on_camera_error_clears_canvas(self, preview: Preview) -> None:
        """_on_camera_error clears the canvas and shows an error message."""
        preview._canvas.set(_create_solid_image())
        preview._on_camera_error("Device lost")
        assert preview._canvas._image is None
        assert not preview._canvas_message.isHidden()

    def test_on_video_error_closes_video(self, preview: Preview) -> None:
        """_on_video_error closes video, clears canvas, and shows an error message."""
        preview._canvas.set(_create_solid_image())
        preview._on_video_error("Decode failed")
        assert preview._canvas._image is None
        assert not preview._canvas_message.isHidden()

    def test_on_video_closed_clears_canvas(self, preview: Preview) -> None:
        """_on_video_closed discards the current frame."""
        preview._canvas.set(_create_solid_image())
        preview._on_video_closed()
        assert preview._canvas._image is None

    def test_on_video_closed_restores_no_camera_message(self, preview: Preview) -> None:
        """_on_video_closed re-shows no-camera message when no cameras are connected."""
        preview._canvas_message.hide_message()
        preview._on_video_closed()
        assert not preview._canvas_message.isHidden()


class TestPreviewRefreshCameras:
    """Tests for Preview._refresh_cameras."""

    def test_refresh_cameras_does_not_update_when_list_unchanged(
        self, preview: Preview, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_refresh_cameras skips _set_cameras when the device list is identical."""
        cameras = [CameraInfo("Fixed", 0)]
        preview._cameras = cameras
        monkeypatch.setattr(
            "obcd_pilot.ui.components.preview.retrieve_cameras",
            lambda: cameras,
        )
        preview._current_camera = cameras[0]
        preview._refresh_cameras()
        assert preview._current_camera == cameras[0]


class TestPreviewStaticFactoryMethods:
    """Tests for the static factory methods that build control widgets."""

    def test_create_preview_bar_has_all_buttons(self, preview: Preview) -> None:
        """_create_preview_bar lays out each passed button in the bar."""
        from PySide6.QtWidgets import QToolButton

        bar = Preview._create_preview_bar(
            preview._camera_button, preview._open_file_button
        )
        buttons = bar.findChildren(QToolButton)
        assert len(buttons) == 2

    def test_camera_button_has_popup_menu(self, preview: Preview) -> None:
        """The camera button is configured for popup-menu mode."""
        from PySide6.QtWidgets import QToolButton

        assert (
            preview._camera_button.popupMode()
            == QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )


class TestPreviewVideoHandlers:
    """Tests for video-state handlers that do not require a real VideoWorker."""

    def test_on_video_played_is_noop_without_worker(self, preview: Preview) -> None:
        """_on_video_played does not raise when no video worker is active."""
        preview._on_video_played()

    def test_on_seek_started_is_noop_without_worker(self, preview: Preview) -> None:
        """_on_video_seek_started does not raise without an active video worker."""
        preview._on_video_seek_started()

    def test_on_seek_moved_is_noop_without_worker(self, preview: Preview) -> None:
        """_on_video_seek_moved does not raise without an active video worker."""
        preview._on_video_seek_moved(10)

    def test_on_seek_ended_is_noop_without_worker(self, preview: Preview) -> None:
        """_on_video_seek_ended does not raise without an active video worker."""
        preview._on_video_seek_ended(10)


class TestPreviewRefreshCamerasWithChange:
    """Tests for _refresh_cameras when the device list changes."""

    def test_refresh_cameras_calls_set_cameras_on_list_change(
        self, preview: Preview, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_refresh_cameras replaces cameras when the enumerated list differs."""
        new_camera = CameraInfo("New Cam", 0)
        monkeypatch.setattr(
            "obcd_pilot.ui.components.preview.retrieve_cameras",
            lambda: [new_camera],
        )
        preview._refresh_cameras()
        assert preview._cameras == [new_camera]

    def test_refresh_cameras_restores_current_selection(
        self, preview: Preview, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_refresh_cameras preserves the previously selected camera index."""
        old = CameraInfo("Old Name", 1)
        new = CameraInfo("New Name", 1)
        preview._cameras = [old]
        preview._current_camera = old
        monkeypatch.setattr(
            "obcd_pilot.ui.components.preview.retrieve_cameras",
            lambda: [new],
        )
        preview._refresh_cameras()
        assert preview._current_camera == new

    def test_refresh_cameras_without_previous_selection(
        self, preview: Preview, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_refresh_cameras with no prior selection does not raise."""
        preview._current_camera = None
        monkeypatch.setattr(
            "obcd_pilot.ui.components.preview.retrieve_cameras",
            lambda: [CameraInfo("Cam", 0)],
        )
        preview._refresh_cameras()


class TestPreviewCameraWorkerLifecycle:
    """Tests for camera worker start/stop via mocked CameraWorker."""

    def test_start_camera_sets_camera_worker(
        self, preview: Preview, no_cameras: None
    ) -> None:
        """_start_camera assigns a new CameraWorker to _camera_worker."""
        camera = CameraInfo("USB Cam", 0)
        with patch("obcd_pilot.ui.components.preview.CameraWorker") as MockWorker:
            preview._start_camera(camera)

        assert preview._camera_worker is MockWorker.return_value

    def test_start_camera_starts_the_worker_thread(
        self, preview: Preview, no_cameras: None
    ) -> None:
        """_start_camera calls start() on the newly created worker."""
        camera = CameraInfo("USB Cam", 0)
        with patch("obcd_pilot.ui.components.preview.CameraWorker") as MockWorker:
            preview._start_camera(camera)

        MockWorker.return_value.start.assert_called_once()

    def test_start_camera_hides_canvas_message(self, preview: Preview) -> None:
        """_start_camera hides the canvas message overlay."""
        assert not preview._canvas_message.isHidden()
        with patch("obcd_pilot.ui.components.preview.CameraWorker"):
            preview._start_camera(CameraInfo("USB Cam", 0))
        assert preview._canvas_message.isHidden()

    def test_stop_camera_clears_camera_worker(self, preview: Preview) -> None:
        """_stop_camera sets _camera_worker to None after stopping."""
        preview._camera_worker = MagicMock()
        preview._stop_camera()
        assert preview._camera_worker is None

    def test_stop_camera_calls_stop_and_wait(self, preview: Preview) -> None:
        """_stop_camera calls stop() and wait() on the running worker."""
        mock_worker = MagicMock()
        preview._camera_worker = mock_worker
        preview._stop_camera()
        mock_worker.stop.assert_called_once()
        mock_worker.wait.assert_called_once()

    def test_on_camera_clicked_stops_running_camera(self, preview: Preview) -> None:
        """_on_camera_clicked stops the camera when one is already running."""
        mock_worker = MagicMock()
        preview._camera_worker = mock_worker
        preview._on_camera_clicked()
        mock_worker.stop.assert_called_once()
        assert preview._camera_worker is None

    def test_on_camera_clicked_starts_camera_when_idle(
        self, preview: Preview, no_cameras: None
    ) -> None:
        """_on_camera_clicked starts the camera when none is running."""
        camera = CameraInfo("Front", 0)
        preview._current_camera = camera
        with patch("obcd_pilot.ui.components.preview.CameraWorker") as MockWorker:
            preview._on_camera_clicked()
        MockWorker.return_value.start.assert_called_once()

    def test_on_camera_selected_updates_current_camera(self, preview: Preview) -> None:
        """_on_camera_selected stores the chosen camera as _current_camera."""
        cameras = [CameraInfo("Cam A", 0), CameraInfo("Cam B", 1)]
        preview._set_cameras(cameras)
        action = preview._camera_menu.actions()[1]
        preview._on_camera_selected(action)
        assert preview._current_camera == cameras[1]

    def test_on_camera_selected_with_unknown_index_is_noop(
        self, preview: Preview
    ) -> None:
        """_on_camera_selected ignores an action whose data is not in _cameras."""
        preview._cameras = [CameraInfo("Known", 0)]
        action = QAction()
        action.setData(99)
        preview._on_camera_selected(action)

    def test_on_camera_selected_starts_camera_if_worker_running(
        self, preview: Preview, no_cameras: None
    ) -> None:
        """_on_camera_selected calls _start_camera when a camera is already active."""
        cameras = [CameraInfo("Cam A", 0), CameraInfo("Cam B", 1)]
        preview._set_cameras(cameras)
        preview._camera_worker = MagicMock()
        action = preview._camera_menu.actions()[0]
        with patch("obcd_pilot.ui.components.preview.CameraWorker") as MockWorker:
            preview._on_camera_selected(action)
        MockWorker.return_value.start.assert_called_once()


class TestPreviewVideoWorkerLifecycle:
    """Tests for video worker load/close via mocked VideoWorker."""

    def test_load_video_sets_video_worker(
        self, preview: Preview, tmp_path: Path
    ) -> None:
        """_load_video assigns a new VideoWorker to _video_worker."""
        path = tmp_path / "clip.mp4"
        with patch("obcd_pilot.ui.components.preview.VideoWorker") as MockWorker:
            preview._load_video(path)

        assert preview._video_worker is MockWorker.return_value

    def test_load_video_shows_playback_overlay(
        self, preview: Preview, tmp_path: Path
    ) -> None:
        """_load_video marks the playback overlay as not-hidden."""
        path = tmp_path / "clip.mp4"
        with patch("obcd_pilot.ui.components.preview.VideoWorker"):
            preview._load_video(path)

        assert not preview._playback_overlay.isHidden()

    def test_load_video_hides_canvas_message(
        self, preview: Preview, tmp_path: Path
    ) -> None:
        """_load_video hides the canvas message overlay."""
        assert not preview._canvas_message.isHidden()
        path = tmp_path / "clip.mp4"
        with patch("obcd_pilot.ui.components.preview.VideoWorker"):
            preview._load_video(path)
        assert preview._canvas_message.isHidden()

    def test_load_video_starts_worker_thread(
        self, preview: Preview, tmp_path: Path
    ) -> None:
        """_load_video calls start() on the created VideoWorker."""
        path = tmp_path / "clip.mp4"
        with patch("obcd_pilot.ui.components.preview.VideoWorker") as MockWorker:
            preview._load_video(path)

        MockWorker.return_value.start.assert_called_once()

    def test_close_video_clears_video_worker(self, preview: Preview) -> None:
        """_close_video sets _video_worker to None after stopping."""
        preview._video_worker = MagicMock()
        preview._close_video()
        assert preview._video_worker is None

    def test_close_video_calls_stop_and_wait(self, preview: Preview) -> None:
        """_close_video calls stop() and wait() on the running worker."""
        mock_worker = MagicMock()
        preview._video_worker = mock_worker
        preview._close_video()
        mock_worker.stop.assert_called_once()
        mock_worker.wait.assert_called_once()

    def test_close_video_hides_playback_overlay(self, preview: Preview) -> None:
        """_close_video hides the playback overlay after stopping."""
        preview._video_worker = MagicMock()
        preview._playback_overlay.setVisible(True)
        preview._close_video()
        assert not preview._playback_overlay.isVisible()

    def test_on_video_played_pauses_when_playing(self, preview: Preview) -> None:
        """_on_video_played calls pause() when the video is currently playing."""
        mock_worker = MagicMock()
        mock_worker.is_playing.return_value = True
        preview._video_worker = mock_worker
        preview._on_video_played()
        mock_worker.pause.assert_called_once()

    def test_on_video_played_plays_when_paused(self, preview: Preview) -> None:
        """_on_video_played calls play() when the video is currently paused."""
        mock_worker = MagicMock()
        mock_worker.is_playing.return_value = False
        preview._video_worker = mock_worker
        preview._on_video_played()
        mock_worker.play.assert_called_once()

    def test_on_video_seek_started_pauses_if_playing(self, preview: Preview) -> None:
        """_on_video_seek_started pauses the worker if it was playing."""
        mock_worker = MagicMock()
        mock_worker.is_playing.return_value = True
        preview._video_worker = mock_worker
        preview._on_video_seek_started()
        mock_worker.pause.assert_called_once()
        assert preview._resume_after_seek

    def test_on_video_seek_moved_seeks_with_no_resume(self, preview: Preview) -> None:
        """_on_video_seek_moved issues a seek with resume=False."""
        mock_worker = MagicMock()
        preview._video_worker = mock_worker
        preview._on_video_seek_moved(30)
        mock_worker.seek.assert_called_once_with(30, resume=False)

    def test_on_video_seek_ended_seeks_with_resume_state(
        self, preview: Preview
    ) -> None:
        """_on_video_seek_ended resumes according to the pre-seek playing state."""
        mock_worker = MagicMock()
        preview._video_worker = mock_worker
        preview._resume_after_seek = True
        preview._on_video_seek_ended(45)
        mock_worker.seek.assert_called_once_with(45, resume=True)

    def test_on_open_file_clicked_loads_selected_path(
        self, preview: Preview, tmp_path: Path
    ) -> None:
        """_on_open_file_clicked calls _load_video with the user-selected path."""
        fake_path = str(tmp_path / "video.mp4")
        with (
            patch(
                "obcd_pilot.ui.components.preview.QFileDialog.getOpenFileName",
                return_value=(fake_path, ""),
            ),
            patch("obcd_pilot.ui.components.preview.VideoWorker") as MockWorker,
        ):
            preview._on_open_file_clicked()

        MockWorker.assert_called_once_with(Path(fake_path))

    def test_on_open_file_clicked_is_noop_on_cancel(self, preview: Preview) -> None:
        """_on_open_file_clicked does nothing when the dialog is dismissed."""
        with patch(
            "obcd_pilot.ui.components.preview.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            preview._on_open_file_clicked()

        assert preview._video_worker is None


class TestPreviewEventFilter:
    """Tests for Preview.eventFilter."""

    def test_event_filter_show_triggers_refresh(
        self, preview: Preview, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """eventFilter calls _refresh_cameras when the camera menu shows."""
        refreshed: list[bool] = []
        monkeypatch.setattr(
            preview,
            "_refresh_cameras",
            lambda: refreshed.append(True),
        )
        event = QEvent(QEvent.Type.Show)
        preview.eventFilter(preview._camera_menu, event)
        assert refreshed

    def test_event_filter_ignores_non_show_event(
        self, preview: Preview, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """eventFilter does not call _refresh_cameras for non-Show events."""
        refreshed: list[bool] = []
        monkeypatch.setattr(
            preview,
            "_refresh_cameras",
            lambda: refreshed.append(True),
        )
        event = QEvent(QEvent.Type.Hide)
        preview.eventFilter(preview._camera_menu, event)
        assert not refreshed

    def test_event_filter_ignores_unrelated_watched_object(
        self, preview: Preview, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """eventFilter is a no-op for objects other than the camera menu."""
        refreshed: list[bool] = []
        monkeypatch.setattr(
            preview,
            "_refresh_cameras",
            lambda: refreshed.append(True),
        )
        event = QEvent(QEvent.Type.Show)
        preview.eventFilter(preview._canvas, event)
        assert not refreshed


@pytest.fixture()
def overlay(qtbot: QtBot) -> _ChangeOverlay:
    """A _ChangeOverlay backed by a sized canvas holding a 200x100 image."""
    canvas = _Canvas()
    canvas.set(_create_solid_image(200, 100))
    canvas.resize(200, 100)
    qtbot.addWidget(canvas)

    widget = _ChangeOverlay(canvas)
    widget.resize(200, 100)
    qtbot.addWidget(widget)
    return widget


class TestCanvasImageRect:
    """Tests for _Canvas.image_rect."""

    def test_returns_none_without_image(self, canvas: _Canvas) -> None:
        """image_rect returns None when no frame has been set."""
        assert canvas.image_rect() is None

    def test_centers_aspect_preserved_image(self, canvas: _Canvas) -> None:
        """image_rect fits the image and centers any letterbox."""
        canvas.set(_create_solid_image(200, 100))  # 2:1
        canvas.resize(200, 200)
        rect = canvas.image_rect()
        assert rect is not None
        assert (rect.width(), rect.height()) == (200, 100)
        assert (rect.x(), rect.y()) == (0, 50)

    def test_fills_when_aspect_matches(self, canvas: _Canvas) -> None:
        """image_rect spans the full canvas when aspect ratios match."""
        canvas.set(_create_solid_image(100, 100))
        canvas.resize(80, 80)
        rect = canvas.image_rect()
        assert rect is not None
        assert (rect.x(), rect.y(), rect.width(), rect.height()) == (0, 0, 80, 80)


class TestChangeOverlayState:
    """Tests for _ChangeOverlay state transitions."""

    def test_starts_idle(self, overlay: _ChangeOverlay) -> None:
        """Overlay holds no bboxes and no detection at construction."""
        assert overlay._bboxes == ()
        assert overlay._change_detected is False

    def test_on_detection_change_caches_bboxes(
        self, overlay: _ChangeOverlay, make_detection: Callable[..., Detection]
    ) -> None:
        """on_detection with change_detected stores the supplied bboxes."""
        bboxes = ((0.1, 0.1, 0.5, 0.5, "person"),)
        overlay.on_detection(make_detection(change_bboxes=bboxes))
        assert overlay._bboxes == bboxes
        assert overlay._change_detected is True

    def test_on_detection_no_change_resets_state(
        self, overlay: _ChangeOverlay, make_detection: Callable[..., Detection]
    ) -> None:
        """on_detection with change_detected=False drops the cached state."""
        overlay.on_detection(
            make_detection(change_bboxes=((0.0, 0.0, 1.0, 1.0, "car"),))
        )
        overlay.on_detection(make_detection(change_detected=False))
        assert overlay._bboxes == ()
        assert overlay._change_detected is False

    def test_clear_resets_state(
        self, overlay: _ChangeOverlay, make_detection: Callable[..., Detection]
    ) -> None:
        """clear() drops bboxes and the change flag."""
        overlay.on_detection(
            make_detection(change_bboxes=((0.0, 0.0, 1.0, 1.0, "car"),))
        )
        overlay.clear()
        assert overlay._bboxes == ()
        assert overlay._change_detected is False

    def test_on_detection_keeps_previous_bboxes_when_empty(
        self, overlay: _ChangeOverlay, make_detection: Callable[..., Detection]
    ) -> None:
        """change_detected with empty bboxes keeps the previous bboxes sticky.

        The model can report a change driven by matched objects shifting,
        which yields an empty bbox tuple. Preserving the last bboxes avoids
        an overlay blink while the status panel stays red.
        """
        bboxes = ((0.1, 0.1, 0.5, 0.5, "person"),)
        overlay.on_detection(make_detection(change_bboxes=bboxes))
        overlay.on_detection(make_detection(change_bboxes=()))
        assert overlay._bboxes == bboxes
        assert overlay._change_detected is True


class TestChangeOverlayPaint:
    """Tests for _ChangeOverlay.paintEvent."""

    def test_paint_idle_does_not_raise(
        self, overlay: _ChangeOverlay, qtbot: QtBot
    ) -> None:
        """paintEvent in the idle state completes without raising."""
        overlay.show()
        qtbot.waitExposed(overlay)
        overlay.update()

    def test_paint_with_bboxes_does_not_raise(
        self,
        overlay: _ChangeOverlay,
        qtbot: QtBot,
        make_detection: Callable[..., Detection],
    ) -> None:
        """paintEvent with cached bboxes completes without raising."""
        overlay.on_detection(
            make_detection(change_bboxes=((0.1, 0.1, 0.4, 0.4, "person"),))
        )
        overlay.show()
        qtbot.waitExposed(overlay)
        overlay.update()

    def test_paint_change_without_bboxes_does_not_raise(
        self,
        overlay: _ChangeOverlay,
        qtbot: QtBot,
        make_detection: Callable[..., Detection],
    ) -> None:
        """paintEvent with the change flag but no bboxes still completes."""
        overlay.on_detection(make_detection())
        overlay.show()
        qtbot.waitExposed(overlay)
        overlay.update()


class TestPreviewChangeOverlayWiring:
    """Tests for Preview hooking sig_detection into _change_overlay."""

    def test_change_overlay_exists(self, preview: Preview) -> None:
        """Preview constructs a _ChangeOverlay alongside the canvas."""
        assert isinstance(preview._change_overlay, _ChangeOverlay)

    def test_sig_detection_updates_overlay(
        self, preview: Preview, make_detection: Callable[..., Detection]
    ) -> None:
        """Emitting sig_detection feeds bboxes into the overlay."""
        bboxes = ((0.2, 0.2, 0.8, 0.8, "person"),)
        preview.sig_detection.emit(make_detection(change_bboxes=bboxes))
        assert preview._change_overlay._bboxes == bboxes
        assert preview._change_overlay._change_detected is True

    def test_sig_pipeline_reset_clears_overlay(
        self,
        preview: Preview,
        qtbot: QtBot,
        make_detection: Callable[..., Detection],
    ) -> None:
        """Emitting sig_pipeline_reset clears the overlay state."""
        preview.sig_detection.emit(
            make_detection(change_bboxes=((0.0, 0.0, 1.0, 1.0, "car"),))
        )
        preview.sig_pipeline_reset.emit()
        # Reset is wired as QueuedConnection so late detections cannot
        # repopulate bboxes after the clear. Wait for the queue to drain.
        qtbot.waitUntil(lambda: not preview._change_overlay._change_detected)
        assert preview._change_overlay._bboxes == ()
        assert preview._change_overlay._change_detected is False
