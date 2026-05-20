"""Shared pytest fixtures for the obcd-pilot test suite."""

import sys

import pytest


@pytest.fixture(scope="session")
def qapp_args() -> list[str]:
    """Override pytest-qt default args to suppress platform warnings."""
    return [sys.argv[0]]


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
