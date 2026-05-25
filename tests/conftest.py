"""Shared pytest fixtures for the obcd-pilot test suite."""

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from obcd_pilot.pipeline import Detection


@pytest.fixture(scope="session")
def qapp_args() -> list[str]:
    """Override pytest-qt default args to suppress platform warnings."""
    return [sys.argv[0]]


@pytest.fixture()
def make_detection() -> Callable[..., Detection]:
    """Factory fixture that builds a Detection with overridable fields."""

    def _build(
        *,
        change_detected: bool = True,
        frame_id: int = 42,
        confidence: float = 0.91,
    ) -> Detection:
        return Detection(
            frame_id=frame_id,
            timestamp_ms=1.0,
            change_detected=change_detected,
            confidence=confidence,
            inference_ms=120.0,
            model_name="ConvOBCD",
        )

    return _build


@pytest.fixture(autouse=True)
def app_log_isolated(tmp_path: Path) -> None:
    """Reset and reconfigure the app logger per test with a tmp file."""
    from obcd_pilot import app_log

    app_log.reset()
    app_log.configure(tmp_path / "obcd_pilot.log")


@pytest.fixture()
def no_cameras(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch retrieve_cameras to return an empty list.

    Prevents real camera enumeration during tests that construct
    Preview widgets, which call retrieve_cameras() in __init__.
    """
    monkeypatch.setattr(
        "obcd_pilot.capture.camera_worker.retrieve_cameras",
        lambda: [],
    )
    monkeypatch.setattr(
        "obcd_pilot.ui.components.preview.retrieve_cameras",
        lambda: [],
    )
