"""Video Widget.

Displays camera frames.
"""

import logging
import os
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QSize,
    QStandardPaths,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QIcon,
    QImage,
    QPainter,
    QPaintEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QStackedLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot import app_log
from obcd_pilot.capture import (
    CameraInfo,
    CameraWorker,
    VideoWorker,
    retrieve_cameras,
)
from obcd_pilot.pipeline import Detection, ModelVariant, OBCDWorker
from obcd_pilot.ui import icons_rc  # noqa: F401
from obcd_pilot.ui.components.playback_overlay import PlaybackOverlay

_ICON_VIDEO_ON = QIcon(":/icons/video.svg")
_ICON_VIDEO_OFF = QIcon(":/icons/video-off.svg")
_ICON_UPLOAD = QIcon(":/icons/upload.svg")
_ICON_CAMERA_OFF = QIcon(":/icons/camera-off.svg")
_ICON_FILE_X = QIcon(":/icons/file-x.svg")

_VIDEO_FILTER = "Video Files (*.mp4)"

_MODEL_VARIANT: ModelVariant = "conv"

logger = logging.getLogger(__name__)


def _weights_dir() -> Path:
    """Checkpoint dir: OBCD_WEIGHTS_DIR, else <cwd>/weights, else Qt AppDataLocation."""
    override = os.environ.get("OBCD_WEIGHTS_DIR")
    if override:
        return Path(override)
    cwd_weights = Path.cwd() / "weights"
    if cwd_weights.is_dir():
        return cwd_weights
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    return Path(base) / "weights"


def _checkpoint_path(variant: ModelVariant) -> Path | None:
    """Return the checkpoint for variant if one is present on disk."""
    path = _weights_dir() / f"obcd_{variant}.pth"
    return path if path.exists() else None


class Preview(QWidget):
    """Camera feed canvas with Zoom-style control bar."""

    sig_detection = Signal(Detection)
    sig_model_ready = Signal(str)
    sig_pipeline_reset = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("preview")

        self._camera_worker: CameraWorker | None = None
        self._cameras: list[CameraInfo] = []
        self._current_camera: CameraInfo | None = None

        self._video_worker: VideoWorker | None = None
        self._resume_after_seek = False

        self._obcd_worker: OBCDWorker | None = None
        self._obcd_thread: QThread | None = None

        # Widgets
        self._canvas = _Canvas()
        self._canvas_message = _CanvasMessage()
        self._playback_overlay = PlaybackOverlay()

        self._camera_menu = QMenu(self)
        self._camera_group = QActionGroup(self)
        self._camera_button = self._create_camera_button(self._camera_menu)
        self._open_file_button = self._create_open_file_button()
        preview_bar = self._create_preview_bar(
            self._camera_button, self._open_file_button
        )

        # Setup Widgets
        self._playback_overlay.setVisible(False)

        self._camera_menu.setObjectName("camera-menu")
        self._camera_menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._camera_group.setExclusive(True)

        # Layouts
        canvas_stack = QWidget()
        stack_layout = QStackedLayout()
        stack_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        stack_layout.addWidget(self._canvas)
        stack_layout.addWidget(self._canvas_message)
        stack_layout.addWidget(self._playback_overlay)
        canvas_stack.setLayout(stack_layout)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(canvas_stack, stretch=1)
        root.addWidget(preview_bar)
        self.setLayout(root)

        # Signals
        self._camera_menu.installEventFilter(self)
        self._camera_menu.triggered.connect(self._on_camera_selected)
        self._camera_button.clicked.connect(self._on_camera_clicked)
        self._open_file_button.clicked.connect(self._on_open_file_clicked)
        self._playback_overlay.sig_video_played.connect(self._on_video_played)
        self._playback_overlay.sig_video_seek_started.connect(
            self._on_video_seek_started
        )
        self._playback_overlay.sig_video_seek_moved.connect(self._on_video_seek_moved)
        self._playback_overlay.sig_video_seek_ended.connect(self._on_video_seek_ended)
        self._playback_overlay.sig_video_closed.connect(self._on_video_closed)

        app = QApplication.instance()
        if app is None:
            raise RuntimeError("Preview requires a running QApplication.")
        app.aboutToQuit.connect(self._stop_camera)
        app.aboutToQuit.connect(self._close_video)

        self._refresh_cameras()

    def _set_cameras(self, cameras: list[CameraInfo]) -> None:
        """Replace camera dropdown entries."""
        self._cameras = cameras
        self._camera_menu.clear()

        for action in self._camera_group.actions():
            self._camera_group.removeAction(action)

        for camera in cameras:
            action = self._camera_menu.addAction(camera.name)
            action.setData(camera.index)
            action.setCheckable(True)
            self._camera_group.addAction(action)

        if cameras:
            self._current_camera = cameras[0]
            self._camera_group.actions()[0].setChecked(True)
            self._canvas_message.hide_message()
        else:
            self._current_camera = None
            self._canvas_message.show_message(
                _ICON_CAMERA_OFF,
                "No camera found",
                "Connect a camera and try again",
            )

    def _refresh_cameras(self) -> None:
        """Re-detect cameras, preserving the current selection."""
        cameras = retrieve_cameras()
        if cameras and cameras == self._cameras:
            return

        # restore selected camera
        selected_camera_idx = None
        if self._current_camera:
            selected_camera_idx = self._current_camera.index

        self._set_cameras(cameras)

        if selected_camera_idx is not None:
            for action in self._camera_group.actions():
                if action.data() == selected_camera_idx:
                    self._current_camera = next(
                        c for c in cameras if c.index == selected_camera_idx
                    )
                    action.setChecked(True)
                    break

    def _start_camera(self, camera: CameraInfo) -> None:
        """Start capturing from the given camera."""
        self._stop_camera()
        self._close_video()
        self._canvas_message.hide_message()

        self._start_pipeline()

        worker = CameraWorker(camera.index)
        worker.sig_frame.connect(lambda frame: self._canvas.set(frame.image))
        if self._obcd_worker is not None:
            worker.sig_frame.connect(self._obcd_worker.push_frame)
        worker.sig_error_occurred.connect(self._on_camera_error)
        worker.start()

        self._camera_worker = worker
        self._camera_button.setIcon(_ICON_VIDEO_ON)
        logger.info("Camera started: %s", camera.name)

    def _stop_camera(self) -> None:
        """Stop the current camera worker if running."""
        if self._camera_worker is None:
            return

        self._camera_worker.stop()
        self._camera_worker.wait()
        self._camera_worker = None
        self._camera_button.setIcon(_ICON_VIDEO_OFF)
        self._stop_pipeline()

    def _load_video(self, path: Path) -> None:
        """Stop any active camera, then start a VideoWorker for path."""
        self._stop_camera()
        self._close_video()
        self._canvas_message.hide_message()

        self._start_pipeline()

        worker = VideoWorker(path)
        worker.sig_frame.connect(lambda frame: self._canvas.set(frame.image))
        if self._obcd_worker is not None:
            worker.sig_frame.connect(self._obcd_worker.push_frame)
        worker.sig_playback.connect(self._playback_overlay.update_position)
        worker.sig_error_occurred.connect(self._on_video_error)
        worker.sig_end_of_file.connect(self._on_video_ended)
        worker.start()

        self._video_worker = worker
        self._video_worker.seek(0, resume=False)
        self._playback_overlay.setVisible(True)
        self._playback_overlay.set_playing(False)
        logger.info("Video loaded: %s", path.name)

    def _close_video(self) -> None:
        """Stop and discard the current video worker."""
        if self._video_worker is None:
            return

        self._video_worker.stop()
        self._video_worker.wait()
        self._video_worker = None
        self._playback_overlay.reset()
        self._playback_overlay.setVisible(False)
        self._stop_pipeline()

    def _start_pipeline(self) -> None:
        """Run an OBCD worker on a dedicated thread for the active source."""
        self._stop_pipeline()

        obcd_worker = OBCDWorker(
            variant=_MODEL_VARIANT,
            checkpoint_path=_checkpoint_path(_MODEL_VARIANT),
        )
        obcd_thread = QThread(self)
        obcd_worker.moveToThread(obcd_thread)
        obcd_worker.sig_detection.connect(self.sig_detection)
        obcd_worker.sig_detection.connect(app_log.log_detection)
        obcd_worker.sig_model_ready.connect(self.sig_model_ready)
        obcd_thread.started.connect(obcd_worker.start_model)
        # Reclaim both after quit() per https://doc.qt.io/qt-6/qthread.html
        obcd_thread.finished.connect(obcd_worker.deleteLater)
        obcd_thread.finished.connect(obcd_thread.deleteLater)
        obcd_thread.start()

        self._obcd_worker = obcd_worker
        self._obcd_thread = obcd_thread

    def _stop_pipeline(self) -> None:
        """Stop the pipeline thread and reset downstream detection state."""
        if self._obcd_thread is None:
            return

        self._obcd_thread.quit()
        self._obcd_thread.wait()
        self._obcd_worker = None
        self._obcd_thread = None
        self.sig_pipeline_reset.emit()

    def _on_camera_selected(self, action: QAction) -> None:
        """Switch to the camera chosen from the dropdown."""
        camera_idx = action.data()

        camera = next((c for c in self._cameras if c.index == camera_idx), None)
        if camera is None:
            return

        self._current_camera = camera

        if self._camera_worker is not None:
            self._start_camera(camera)

    def _on_camera_clicked(self) -> None:
        """Toggle the current camera on or off."""
        if self._camera_worker is not None:
            self._stop_camera()
            self._canvas.clear()
            self._canvas_message.hide_message()
            return

        if self._current_camera is not None:
            self._start_camera(self._current_camera)

    def _on_camera_error(self, message: str) -> None:
        """Handle a camera error by stopping camera and showing an error message."""
        logger.warning(message)
        self._stop_camera()
        self._canvas.clear()
        self._canvas_message.show_message(_ICON_CAMERA_OFF, "Camera error", message)

    def _on_open_file_clicked(self) -> None:
        """Open a file dialog and load the selected video."""
        path_str, _ = QFileDialog.getOpenFileName(self, "Open Video", "", _VIDEO_FILTER)
        if path_str:
            self._load_video(Path(path_str))

    def _on_video_played(self) -> None:
        """Toggle video play/pause from the overlay button."""
        if self._video_worker is None:
            return

        if self._video_worker.is_playing():
            self._video_worker.pause()
            self._playback_overlay.set_playing(False)
        else:
            self._video_worker.play()
            self._playback_overlay.set_playing(True)

    def _on_video_seek_started(self) -> None:
        """Pause the video worker when the user begins scrubbing the slider."""
        if self._video_worker is None:
            return
        self._resume_after_seek = self._video_worker.is_playing()
        if self._resume_after_seek:
            self._video_worker.pause()

    def _on_video_seek_moved(self, frame_index: int) -> None:
        """Seek the video to the requested frame."""
        if self._video_worker is None:
            return
        self._video_worker.seek(frame_index, resume=False)

    def _on_video_seek_ended(self, frame_index: int) -> None:
        """Seek to the final slider position and restore play state."""
        if self._video_worker is None:
            return
        self._video_worker.seek(frame_index, resume=self._resume_after_seek)

    def _on_video_closed(self) -> None:
        """Close the video and clear the canvas."""
        self._close_video()
        self._canvas.clear()
        if not self._cameras:
            self._canvas_message.show_message(
                _ICON_CAMERA_OFF,
                "No camera found",
                "Connect a camera and try again",
            )

    def _on_video_ended(self) -> None:
        """Pause video at end-of-file."""
        self._playback_overlay.set_playing(False)

    def _on_video_error(self, message: str) -> None:
        """Handle a video error by closing video and showing an error message."""
        logger.warning(message)
        self._close_video()
        self._canvas.clear()
        self._canvas_message.show_message(_ICON_FILE_X, "Video error", message)

    @staticmethod
    def _create_camera_button(menu: QMenu) -> QToolButton:
        """Create the split camera toggle/switch button."""
        button = QToolButton()

        button.setObjectName("camera-button")
        button.setIcon(_ICON_VIDEO_OFF)
        button.setText("Video")
        button.setIconSize(QSize(24, 24))
        button.setFixedSize(64, 52)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        button.setMenu(menu)

        return button

    @staticmethod
    def _create_open_file_button() -> QToolButton:
        """Create the open-file button."""
        button = QToolButton()

        button.setObjectName("open-file-button")
        button.setIcon(QIcon(_ICON_UPLOAD))
        button.setText("Upload")
        button.setIconSize(QSize(24, 24))
        button.setFixedSize(64, 52)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        return button

    @staticmethod
    def _create_preview_bar(*buttons: QWidget) -> QWidget:
        """Lay out buttons in a centered horizontal bar."""
        bar = QWidget()
        bar.setObjectName("preview-bar")
        bar.setFixedHeight(60)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(10, 0, 10, 0)
        h_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for button in buttons:
            h_layout.addWidget(button)

        bar.setLayout(h_layout)

        return bar

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Overloaded Qt method.

        Reposition the camera menu above the button on show.
        """
        if watched is self._camera_menu and event.type() == QEvent.Type.Show:
            self._refresh_cameras()
            self._camera_menu.adjustSize()

            menu_size = self._camera_menu.sizeHint()
            x = self._camera_button.width() - 12
            y = -menu_size.height()
            pos = self._camera_button.mapToGlobal(QPoint(x, y))
            self._camera_menu.move(pos)
        return super().eventFilter(watched, event)


class _CanvasMessage(QWidget):
    """Full-canvas overlay for broadcasting status or error messages."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("canvas-message")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._icon_label = QLabel()
        self._icon_label.setObjectName("canvas-message-icon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fade = QGraphicsOpacityEffect()
        fade.setOpacity(0.22)
        self._icon_label.setGraphicsEffect(fade)

        self._title_label = QLabel()
        self._title_label.setObjectName("canvas-message-title")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._subtitle_label = QLabel()
        self._subtitle_label.setObjectName("canvas-message-subtitle")
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        root = QVBoxLayout()
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._icon_label)
        root.addSpacing(12)
        root.addWidget(self._title_label)
        root.addSpacing(4)
        root.addWidget(self._subtitle_label)
        self.setLayout(root)

        self.setVisible(False)

    def show_message(self, icon: QIcon, title: str, subtitle: str) -> None:
        """Display an icon, title, and subtitle over the canvas."""
        self._icon_label.setPixmap(icon.pixmap(QSize(40, 40)))
        self._title_label.setText(title)
        self._subtitle_label.setText(subtitle)
        self.setVisible(True)

    def hide_message(self) -> None:
        """Dismiss the overlay."""
        self.setVisible(False)


class _Canvas(QWidget):
    """Paint a QImage with aspect-ratio preservation."""

    def __init__(self) -> None:
        super().__init__()

        self._image: QImage | None = None

        self.setObjectName("frame-canvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set(self, image: QImage) -> None:
        """Replace the displayed image and schedule a repaint."""
        self._image = image
        self.update()

    def clear(self) -> None:
        """Remove the current frame and repaint to blank."""
        self._image = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Overloaded Qt method.

        Paint the current frame scaled to fit the widget.
        """
        super().paintEvent(event)
        if self._image is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        canvas_size = self.size()
        scaled_image_size = self._image.size().scaled(
            canvas_size, Qt.AspectRatioMode.KeepAspectRatio
        )
        x = (canvas_size.width() - scaled_image_size.width()) // 2
        y = (canvas_size.height() - scaled_image_size.height()) // 2

        painter.drawImage(
            x,
            y,
            self._image.scaled(
                scaled_image_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        )
        painter.end()
