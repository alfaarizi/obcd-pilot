"""Main Window for Qt Application.

Displays a live webcam feed.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QToolBar,
)

from obcd_pilot.ui.monitor_view import MonitorView


class MainWindow(QMainWindow):
    """Top-level window for the application."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("OBCD Pilot")
        self.setMinimumSize(640, 480)

        self._stack = QStackedWidget()
        self._stack.addWidget(MonitorView())
        self.setCentralWidget(self._stack)

        self._nav_sidebar = self._create_nav_sidebar()

        self._status_bar = self._create_status_bar()

    def _create_nav_sidebar(self) -> QToolBar:
        """Create a sidebar and dock it to the left."""
        nav_sidebar = QToolBar("Navigation sidebar")
        nav_sidebar.setIconSize(QSize(24, 24))
        nav_sidebar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        nav_sidebar.setFixedWidth(56)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, nav_sidebar)

        nav_group = QActionGroup(self)
        nav_group.setExclusive(True)

        action = QAction(QIcon.fromTheme("camera-video"), "Monitor", self)
        action.triggered.connect(lambda _: self._stack.setCurrentIndex(0))
        action.setChecked(True)

        nav_group.addAction(action)

        nav_sidebar.addAction(action)

        return nav_sidebar

    def _create_status_bar(self) -> QStatusBar:
        """Create a status bar and dock it to the bottom."""
        status_bar: QStatusBar = self.statusBar()

        self._service_label = QLabel("Service: —")

        status_bar.addPermanentWidget(self._service_label)

        return status_bar
