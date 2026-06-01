"""Locate packaged assets across dev installs and frozen PyInstaller builds."""

import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent


def resource_path(rel: str) -> Path:
    """Return the absolute path of a packaged asset under obcd_pilot/."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / rel  # type: ignore[attr-defined]
    return _PACKAGE_ROOT / rel
