"""Main application window with navigation sidebar and view stack."""

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
from obcd_pilot.ui import icons_rc  # noqa: F401
from obcd_pilot.ui.logs_view import LogsView
from obcd_pilot.ui.monitor_view import MonitorView

ICON_MONITOR = QIcon(":/icons/monitor.svg")
ICON_FILE_TEXT = QIcon(":/icons/file-text.svg")


class MainWindow(QMainWindow):
    """Top-level window for the application."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("OBCD Pilot")
        self.setMinimumSize(640, 360)

        self._stack = QStackedWidget()
        self._stack.addWidget(MonitorView())
        self._stack.addWidget(LogsView())
        self._nav_sidebar: QToolBar = self._create_nav_sidebar()
        self._status_bar: QWidget = self._create_service_bar()

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)
        v_layout.addWidget(self._stack, stretch=1)
        v_layout.addWidget(self._status_bar)

        root = QWidget()
        root.setLayout(v_layout)

        self.setCentralWidget(root)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._nav_sidebar)

    def _create_nav_sidebar(self) -> QToolBar:
        """Create a sidebar and dock it to the left."""
        nav_sidebar = QToolBar("Navigation sidebar")
        nav_sidebar.setObjectName("nav-sidebar")
        nav_sidebar.setIconSize(QSize(20, 20))
        nav_sidebar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        nav_sidebar.setMovable(False)
        nav_sidebar.setFixedWidth(68)

        nav_group = QActionGroup(self)
        nav_group.setExclusive(True)

        for index, (icon, label) in enumerate(
            (
                (ICON_MONITOR, "Monitor"),
                (ICON_FILE_TEXT, "Logs"),
            )
        ):
            action = QAction(icon, label, self)
            action.setCheckable(True)
            action.setChecked(index == 0)
            action.setToolTip(label)
            action.triggered.connect(
                lambda _checked=False, i=index: self._stack.setCurrentIndex(i)
            )
            nav_group.addAction(action)
            nav_sidebar.addAction(action)

        return nav_sidebar

    def _create_service_bar(self) -> QWidget:
        """Create a status bar and dock it to the bottom."""
        self._service_label = QLabel("Service: —")
        self._service_label.setObjectName("service-label")

        self._version_label = QLabel(f"v{__version__}")
        self._version_label.setObjectName("version-label")

        service_bar = QWidget()
        service_bar.setObjectName("service-bar")
        service_bar.setFixedHeight(30)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        h_layout.addWidget(self._service_label, stretch=1)
        h_layout.addWidget(self._version_label)

        service_bar.setLayout(h_layout)

        return service_bar
