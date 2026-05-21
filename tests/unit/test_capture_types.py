"""Unit tests for capture data types: Frame, Playback, and CameraInfo."""

import pytest
from PySide6.QtGui import QImage

from obcd_pilot.capture._types import CameraInfo, Frame, Playback


@pytest.fixture()
def rgb_image() -> QImage:
    """A minimal valid QImage for use as a Frame payload."""
    return QImage(8, 6, QImage.Format.Format_RGB888)


class TestFrame:
    """Tests for the Frame named tuple."""

    def test_fields_are_accessible_by_name(self, rgb_image: QImage) -> None:
        """Frame exposes image, width, height, and fps as named attributes."""
        frame = Frame(image=rgb_image, width=8, height=6, fps=25.0)

        assert frame.image is rgb_image
        assert frame.width == 8
        assert frame.height == 6
        assert frame.fps == 25.0

    def test_fields_are_accessible_by_index(self, rgb_image: QImage) -> None:
        """Frame supports positional unpacking like a regular tuple."""
        frame = Frame(rgb_image, 8, 6, 25.0)

        image, width, height, fps = frame

        assert image is rgb_image
        assert width == 8
        assert height == 6
        assert fps == 25.0

    def test_is_immutable(self, rgb_image: QImage) -> None:
        """Frame fields cannot be reassigned after construction."""
        frame = Frame(rgb_image, 8, 6, 25.0)

        with pytest.raises(AttributeError):
            frame.width = 100  # type: ignore[misc]

    def test_equality_by_value(self, rgb_image: QImage) -> None:
        """Two Frame instances with identical values compare equal."""
        a = Frame(rgb_image, 8, 6, 25.0)
        b = Frame(rgb_image, 8, 6, 25.0)

        assert a == b

    def test_fps_fallback_value_accepted(self, rgb_image: QImage) -> None:
        """fps of 30.0 (the module fallback) is stored without truncation."""
        frame = Frame(rgb_image, 1280, 720, 30.0)

        assert frame.fps == 30.0


class TestPlayback:
    """Tests for the Playback named tuple."""

    def test_fields_are_accessible_by_name(self) -> None:
        """Playback exposes all four positional fields by name."""
        playback = Playback(
            position_ms=1500.0,
            duration_ms=60000.0,
            frame_index=45,
            frame_count=1800,
        )

        assert playback.position_ms == 1500.0
        assert playback.duration_ms == 60000.0
        assert playback.frame_index == 45
        assert playback.frame_count == 1800

    def test_is_immutable(self) -> None:
        """Playback fields cannot be reassigned after construction."""
        playback = Playback(0.0, 1000.0, 0, 30)

        with pytest.raises(AttributeError):
            playback.frame_index = 5  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        """Two Playback instances with identical values compare equal."""
        a = Playback(0.0, 1000.0, 0, 30)
        b = Playback(0.0, 1000.0, 0, 30)

        assert a == b

    def test_at_end_of_file_boundary(self) -> None:
        """Playback at EOF has position_ms equal to duration_ms."""
        playback = Playback(
            position_ms=5000.0,
            duration_ms=5000.0,
            frame_index=149,
            frame_count=150,
        )

        assert playback.position_ms == playback.duration_ms
        assert playback.frame_index == playback.frame_count - 1


class TestCameraInfo:
    """Tests for the CameraInfo frozen dataclass."""

    def test_fields_are_accessible_by_name(self) -> None:
        """CameraInfo stores name and index as readable attributes."""
        camera = CameraInfo(name="FaceTime HD Camera", index=0)

        assert camera.name == "FaceTime HD Camera"
        assert camera.index == 0

    def test_is_immutable(self) -> None:
        """CameraInfo is frozen: assigning fields raises FrozenInstanceError."""
        camera = CameraInfo("Built-in Webcam", 0)

        with pytest.raises(Exception):
            camera.index = 1  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        """Two CameraInfo instances with the same name and index are equal."""
        a = CameraInfo("USB Cam", 1)
        b = CameraInfo("USB Cam", 1)

        assert a == b

    def test_different_indices_are_not_equal(self) -> None:
        """CameraInfo instances with different indices are distinct."""
        a = CameraInfo("Cam", 0)
        b = CameraInfo("Cam", 1)

        assert a != b

    def test_slots_are_used(self) -> None:
        """CameraInfo uses __slots__ so arbitrary attributes cannot be set."""
        camera = CameraInfo("Cam", 0)

        with pytest.raises((AttributeError, TypeError)):
            camera.extra = "unexpected"  # type: ignore[attr-defined]
