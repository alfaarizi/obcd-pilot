"""Video Widget.

Displays camera frames.
"""

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot.ui import icons_rc  # noqa: F401

_DEFAULT_SOURCES: list[tuple[str, int]] = [
    ("USB Camera (0)", 0),
    ("USB Camera (1)", 1),
    ("USB Camera (2)", 2),
]


class Viewport(QWidget):
    """Camera feed canvas with Zoom-style control bar."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("viewport")

        # Widgets
        self._canvas = _FrameCanvas()

        self._camera_menu = QMenu(self)
        self._camera_menu.setObjectName("camera-menu")
        self._camera_button = self._create_camera_button(self._camera_menu)
        self._camera_active = False

        self._open_file_button = self._create_open_file_button()

        control_bar = self._create_control_bar(
            self._camera_button, self._open_file_button
        )

        # Layouts
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._canvas, stretch=1)
        root.addWidget(control_bar)
        self.setLayout(root)

        # Signals
        self._camera_menu.installEventFilter(self)

        self.set_camera_sources(_DEFAULT_SOURCES)

    def set_image(self, image: QImage) -> None:
        """Display a frame on the canvas."""
        self._canvas.set(image)

    def clear_image(self) -> None:
        """Clear the canvas to blank."""
        self._canvas.clear()

    def set_camera_sources(self, sources: list[tuple[str, int]]) -> None:
        """Replace camera dropdown entries.

        Args:
            sources: Pairs of (display_name, device_index).
        """
        self._camera_menu.clear()
        for name, index in sources:
            action = self._camera_menu.addAction(name)
            action.setData(index)

    @staticmethod
    def _create_camera_button(menu: QMenu) -> QToolButton:
        """Create the split camera toggle/switch button."""
        button = QToolButton()

        button.setObjectName("camera-button")
        button.setIcon(QIcon(":/icons/video.svg"))
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
        button.setIcon(QIcon(":/icons/upload.svg"))
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
