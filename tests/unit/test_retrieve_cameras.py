"""Unit tests for the retrieve_cameras function."""

from unittest.mock import MagicMock, patch

import cv2

from obcd_pilot.capture._types import CameraInfo
from obcd_pilot.capture.camera_worker import _BACKENDS, retrieve_cameras


def _create_camera_info(name: str, index: int) -> MagicMock:
    """Return a mock that looks like a cv2_enumerate_cameras CameraInfo."""
    mock = MagicMock()
    mock.name = name
    mock.index = index
    return mock


def test_returns_list_of_camera_info() -> None:
    """retrieve_cameras converts enumeration results to CameraInfo objects."""
    raw = [_create_camera_info("FaceTime HD", 0), _create_camera_info("USB Cam", 1)]

    with patch("obcd_pilot.capture.camera_worker.enumerate_cameras", return_value=raw):
        cameras = retrieve_cameras()

    assert cameras == [CameraInfo("FaceTime HD", 0), CameraInfo("USB Cam", 1)]


def test_returns_empty_list_when_no_cameras_found() -> None:
    """retrieve_cameras returns an empty list when no devices are enumerated."""
    with patch("obcd_pilot.capture.camera_worker.enumerate_cameras", return_value=[]):
        cameras = retrieve_cameras()

    assert cameras == []


def test_passes_platform_specific_backend_on_darwin() -> None:
    """On macOS, AVFoundation backend is passed to the enumerator."""
    captured: list[int] = []

    def capture_backend(backend: int) -> list[MagicMock]:
        captured.append(backend)
        return []

    with (
        patch("platform.system", return_value="Darwin"),
        patch(
            "obcd_pilot.capture.camera_worker.enumerate_cameras",
            side_effect=capture_backend,
        ),
    ):
        retrieve_cameras()

    assert captured == [cv2.CAP_AVFOUNDATION]


def test_passes_platform_specific_backend_on_linux() -> None:
    """On Linux, V4L2 backend is passed to the enumerator."""
    captured: list[int] = []

    def capture_backend(backend: int) -> list[MagicMock]:
        captured.append(backend)
        return []

    with (
        patch("platform.system", return_value="Linux"),
        patch(
            "obcd_pilot.capture.camera_worker.enumerate_cameras",
            side_effect=capture_backend,
        ),
    ):
        retrieve_cameras()

    assert captured == [cv2.CAP_V4L2]


def test_falls_back_to_cap_any_on_unknown_platform() -> None:
    """On an unrecognised platform, cv2.CAP_ANY is used as the backend."""
    captured: list[int] = []

    def capture_backend(backend: int) -> list[MagicMock]:
        captured.append(backend)
        return []

    with (
        patch("platform.system", return_value="SunOS"),
        patch(
            "obcd_pilot.capture.camera_worker.enumerate_cameras",
            side_effect=capture_backend,
        ),
    ):
        retrieve_cameras()

    assert captured == [cv2.CAP_ANY]


def test_backends_map_covers_all_three_platforms() -> None:
    """The platform-to-backend map defines entries for Darwin, Linux, and Windows."""
    assert set(_BACKENDS.keys()) == {"Darwin", "Linux", "Windows"}
