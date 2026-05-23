"""Shared fixtures for integration tests."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def stub_pipeline() -> Iterator[tuple[MagicMock, MagicMock]]:
    """Replace the OBCD worker and its thread with mocks in widget tests."""
    target = "obcd_pilot.ui.components.preview"
    with (
        patch(f"{target}.OBCDWorker") as worker_cls,
        patch(f"{target}.QThread") as thread_cls,
    ):
        yield worker_cls, thread_cls
