"""Smoke tests that verify the package is importable."""

from obcd_pilot import __version__


def test_version_is_set() -> None:
    """Package exposes a non-empty version string."""
    assert isinstance(__version__, str)
    assert __version__


def test_subpackages_are_importable() -> None:
    """Every sub-package is importable and carries a module docstring."""
    import obcd_pilot.alarm
    import obcd_pilot.capture
    import obcd_pilot.config
    import obcd_pilot.pipeline
    import obcd_pilot.ui
    import obcd_pilot.ui.components

    assert obcd_pilot.alarm.__doc__ is not None
    assert obcd_pilot.capture.__doc__ is not None
    assert obcd_pilot.config.__doc__ is not None
    assert obcd_pilot.pipeline.__doc__ is not None
    assert obcd_pilot.ui.__doc__ is not None
    assert obcd_pilot.ui.components.__doc__ is not None


def test_worker_modules_are_importable() -> None:
    """Worker modules import cleanly without starting threads or opening devices."""
    import obcd_pilot.capture.camera_worker
    import obcd_pilot.capture.video_worker

    assert obcd_pilot.capture.camera_worker.__doc__ is not None
    assert obcd_pilot.capture.video_worker.__doc__ is not None
