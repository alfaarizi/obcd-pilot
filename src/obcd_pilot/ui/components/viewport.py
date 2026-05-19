"""Video Widget.

Displays camera frames.
"""

import logging

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QImage, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot.capture import Camera, CameraWorker, retrieve_cameras
from obcd_pilot.ui import icons_rc  # noqa: F401

_ICON_VIDEO_ON = QIcon(":/icons/video.svg")
_ICON_VIDEO_OFF = QIcon(":/icons/video-off.svg")
_ICON_UPLOAD = QIcon(":/icons/upload.svg")

logger = logging.getLogger(__name__)


class Viewport(QWidget):
    """Camera feed canvas with Zoom-style control bar."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("viewport")

        self._camera_worker: CameraWorker | None = None
        self._cameras: list[Camera] = []
        self._current_camera: Camera | None = None

        # Widgets
        self._canvas = _FrameCanvas()
        self._camera_menu = QMenu(self)
        self._camera_group = QActionGroup(self)
        self._camera_button = self._create_camera_button(self._camera_menu)
        self._open_file_button = self._create_open_file_button()
        control_bar = self._create_control_bar(
            self._camera_button, self._open_file_button
        )

        # Setup Widgets
        self._camera_menu.setObjectName("camera-menu")
        self._camera_menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._camera_group.setExclusive(True)

        # Layouts
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._canvas, stretch=1)
        root.addWidget(control_bar)
        self.setLayout(root)

        # Signals
        self._camera_menu.installEventFilter(self)
        self._camera_menu.triggered.connect(self._on_camera_selected)
        self._camera_button.clicked.connect(self._on_camera_clicked)

        app = QApplication.instance()
        assert app is not None
        app.aboutToQuit.connect(self._stop_camera)

        cameras = retrieve_cameras()
        self._set_cameras(cameras)

    def _set_cameras(self, cameras: list[Camera]) -> None:
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

    def _start_camera(self, camera: Camera) -> None:
        """Start capturing from the given camera."""
        self._stop_camera()

        worker = CameraWorker(camera.index)
        worker.sig_frame.connect(lambda frame: self._canvas.set(frame.image))
        worker.sig_error_occurred.connect(self._on_camera_error)
        worker.start()

        self._camera_worker = worker
        self._camera_button.setIcon(_ICON_VIDEO_ON)

    def _stop_camera(self) -> None:
        """Stop the current camera worker if running."""
        if self._camera_worker is None:
            return

        self._camera_worker.stop()
        self._camera_worker.wait()
        self._camera_worker = None
        self._camera_button.setIcon(_ICON_VIDEO_OFF)

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
            return

        if self._current_camera is not None:
            self._start_camera(self._current_camera)

    def _on_camera_error(self, message: str) -> None:
        """Handle a camera error by stopping and clearing."""
        logger.warning(message)
        self._stop_camera()
        self._canvas.clear()

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
    def _create_control_bar(*buttons: QWidget) -> QWidget:
        """Lay out buttons in a centered horizontal bar."""
        bar = QWidget()
        bar.setObjectName("control-bar")
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
            menu_size = self._camera_menu.sizeHint()
            x = self._camera_button.width() - 12
            y = -menu_size.height()
            pos = self._camera_button.mapToGlobal(QPoint(x, y))
            self._camera_menu.move(pos)
        return super().eventFilter(watched, event)


class _FrameCanvas(QWidget):
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
