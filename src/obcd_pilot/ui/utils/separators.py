"""Factory functions for horizontal and vertical separator lines."""

from PySide6.QtWidgets import QFrame


def create_h_separator() -> QFrame:
    """Return a styled horizontal rule widget."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    return line


def create_v_separator() -> QFrame:
    """Return a styled vertical rule widget."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    return line
