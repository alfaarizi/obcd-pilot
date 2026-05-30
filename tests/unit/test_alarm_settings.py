"""Unit tests for the AlarmSettingsStore."""

from pytestqt.qtbot import QtBot

from obcd_pilot import alarm
from obcd_pilot.alarm import AlarmSettings, AlarmSettingsStore


class TestDefaults:
    """The store falls back to dataclass defaults when QSettings is empty."""

    def test_default_snapshot(self) -> None:
        """A fresh store starts in the AlarmSettings() default state."""
        assert AlarmSettingsStore().settings == AlarmSettings()

    def test_module_store_is_a_singleton(self) -> None:
        """alarm.store() returns the same store across calls."""
        assert alarm.store() is alarm.store()

    def test_popup_timeout_constant(self) -> None:
        """The default pop-up timeout is 5 seconds."""
        assert alarm.POPUP_TIMEOUT_MS == 5_000


class TestMutations:
    """Setters update the snapshot and fan out sig_changed exactly once."""

    def test_set_popup_enabled_flips_and_emits(self, qtbot: QtBot) -> None:
        """set_popup_enabled flips the field and emits the new snapshot."""
        store = AlarmSettingsStore()
        with qtbot.waitSignal(store.sig_changed, timeout=500) as blocker:
            store.set_popup_enabled(False)
        snapshot = blocker.args[0]
        assert isinstance(snapshot, AlarmSettings)
        assert snapshot.popup_enabled is False
        assert store.settings.popup_enabled is False

    def test_setter_is_noop_when_value_unchanged(self, qtbot: QtBot) -> None:
        """Setting the same value does not reemit sig_changed."""
        store = AlarmSettingsStore()
        with qtbot.assertNotEmitted(store.sig_changed, wait=100):
            store.set_popup_enabled(store.settings.popup_enabled)


class TestPersistence:
    """Changes survive store reconstruction by way of QSettings."""

    def test_changes_persist_across_stores(self) -> None:
        """A second store reads back the value the first one wrote."""
        first = AlarmSettingsStore()
        first.set_popup_enabled(False)
        assert AlarmSettingsStore().settings.popup_enabled is False
