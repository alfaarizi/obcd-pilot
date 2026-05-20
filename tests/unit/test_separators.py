"""Unit tests for the separator factory functions."""

from PySide6.QtWidgets import QFrame

from obcd_pilot.ui.utils.separators import create_h_separator, create_v_separator


def test_create_h_separator_returns_qframe() -> None:
    """create_h_separator returns a QFrame widget."""
    frame = create_h_separator()
    assert isinstance(frame, QFrame)


def test_create_h_separator_is_horizontal() -> None:
    """create_h_separator configures the frame shape as HLine."""
    frame = create_h_separator()
    assert frame.frameShape() == QFrame.Shape.HLine


def test_create_h_separator_shadow_is_plain() -> None:
    """create_h_separator uses Plain shadow so it renders without 3-D effect."""
    frame = create_h_separator()
    assert frame.frameShadow() == QFrame.Shadow.Plain


def test_create_v_separator_returns_qframe() -> None:
    """create_v_separator returns a QFrame widget."""
    frame = create_v_separator()
    assert isinstance(frame, QFrame)


def test_create_v_separator_is_vertical() -> None:
    """create_v_separator configures the frame shape as VLine."""
    frame = create_v_separator()
    assert frame.frameShape() == QFrame.Shape.VLine


def test_create_v_separator_shadow_is_plain() -> None:
    """create_v_separator uses Plain shadow."""
    frame = create_v_separator()
    assert frame.frameShadow() == QFrame.Shadow.Plain
