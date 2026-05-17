"""Main Window for Qt Application.

Displays a live webcam feed.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    """Top-level window for the application."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("OBCD Pilot")

        self._video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._video_label.setMinimumSize(640, 480)
        self._video_label.setText("Hi there.")

        layout = QVBoxLayout()
        layout.addWidget(self._video_label, stretch=1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
