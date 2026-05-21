"""Unit tests for the _format_timestamp helper in playback_overlay."""

import pytest

from obcd_pilot.ui.components.playback_overlay import _format_timestamp


@pytest.mark.parametrize(
    ("ms", "expected"),
    [
        (0.0, "00:00"),
        (1000.0, "00:01"),
        (59000.0, "00:59"),
        (60000.0, "01:00"),
        (61000.0, "01:01"),
        (3599000.0, "59:59"),
        (3600000.0, "60:00"),
        (500.0, "00:00"),
        (1499.9, "00:01"),
    ],
)
def test_format_timestamp(ms: float, expected: str) -> None:
    """_format_timestamp converts milliseconds to a mm:ss string."""
    assert _format_timestamp(ms) == expected


def test_format_timestamp_zero_pads_minutes() -> None:
    """Single-digit minute values are left-padded with a zero."""
    assert _format_timestamp(120000.0).startswith("02:")


def test_format_timestamp_zero_pads_seconds() -> None:
    """Single-digit second values are left-padded with a zero."""
    result = _format_timestamp(5000.0)
    assert result.endswith(":05")


def test_format_timestamp_always_produces_colon_separated_pair() -> None:
    """Output always matches mm:ss — exactly two digits on each side of a colon."""
    import re

    result = _format_timestamp(75000.0)
    assert re.fullmatch(r"\d{2}:\d{2}", result)
