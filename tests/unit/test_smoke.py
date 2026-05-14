"""Smoke tests that verify the package is importable."""

from obcd_pilot import __version__


def test_version_is_set() -> None:
    """Package exposes a version string."""
    assert isinstance(__version__, str)
    assert __version__


def test_submodules_importable() -> None:
    """Every module from the component view is importable."""
    import obcd_pilot.alarm
    import obcd_pilot.capture
    import obcd_pilot.config
    import obcd_pilot.pipeline
    import obcd_pilot.ui

    assert obcd_pilot.alarm.__doc__ is not None
    assert obcd_pilot.capture.__doc__ is not None
    assert obcd_pilot.config.__doc__ is not None
    assert obcd_pilot.pipeline.__doc__ is not None
    assert obcd_pilot.ui.__doc__ is not None
