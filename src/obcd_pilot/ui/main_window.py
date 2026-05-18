"""Main Window for Qt Application.

Displays a live webcam feed.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot import __version__
from obcd_pilot.ui.monitor_view import MonitorView


class MainWindow(QMainWindow):
    """Top-level window for the application."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("OBCD Pilot")
        self.setMinimumSize(640, 480)

        self._stack = QStackedWidget()
        self._stack.addWidget(MonitorView())
        self._nav_sidebar: QToolBar = self._create_nav_sidebar()
        self._status_bar: QWidget = self._create_service_bar()

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)
        v_layout.addWidget(self._stack, stretch=1)
        v_layout.addWidget(self._status_bar)

        root = QWidget()
        root.setLayout(v_layout)

        # attach to window
        self.setCentralWidget(root)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._nav_sidebar)

    def _create_nav_sidebar(self) -> QToolBar:
        """Create a sidebar and dock it to the left."""
        nav_sidebar = QToolBar("Navigation sidebar")
        nav_sidebar.setIconSize(QSize(24, 24))
        nav_sidebar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        nav_sidebar.setMovable(False)
        nav_sidebar.setFixedWidth(56)

        nav_group = QActionGroup(self)
        nav_group.setExclusive(True)

        action = QAction(QIcon.fromTheme("camera-video"), "Monitor", self)
        action.setCheckable(True)
        action.setChecked(True)
        action.triggered.connect(lambda: self._stack.setCurrentIndex(0))

        nav_group.addAction(action)

        nav_sidebar.addAction(action)

        return nav_sidebar

    def _create_service_bar(self) -> QWidget:
        """Create a status bar and dock it to the bottom."""
        self._service_label = QLabel("Service: —")
        self._version_label = QLabel(f"v{__version__}")

        service_bar = QWidget()

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.addWidget(self._service_label, stretch=1)
        h_layout.addWidget(self._version_label)

        service_bar.setLayout(h_layout)

        return service_bar
