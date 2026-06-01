"""Unit tests for the AlarmSettingsStore."""

from pytestqt.qtbot import QtBot

from obcd_pilot import alarm
from obcd_pilot.alarm import AlarmSettings, AlarmSettingsStore
from obcd_pilot.alarm.settings import (
    POPUP_TIMEOUT_MAX_S,
    POPUP_TIMEOUT_MIN_S,
    SOUND_DEFAULT_PRESET,
    SOUND_PRESETS,
)


class TestDefaults:
    """The store falls back to dataclass defaults when QSettings is empty."""

    def test_default_snapshot(self) -> None:
        """A fresh store starts in the AlarmSettings() default state."""
        assert AlarmSettingsStore().settings == AlarmSettings()

    def test_module_store_is_a_singleton(self) -> None:
        """alarm.store() returns the same store across calls."""
        assert alarm.store() is alarm.store()

    def test_default_popup_timeout_is_three_seconds(self) -> None:
        """The default pop-up auto-dismiss timeout is 3 seconds."""
        assert AlarmSettings().popup_timeout_s == 3

    def test_default_sound_channel_is_enabled(self) -> None:
        """The sound channel ships enabled with the default preset selected."""
        snapshot = AlarmSettings()
        assert snapshot.sound_enabled is True
        assert snapshot.sound_preset == SOUND_DEFAULT_PRESET
        assert snapshot.sound_path == ""


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

    def test_set_popup_timeout_s_updates_and_emits(self, qtbot: QtBot) -> None:
        """set_popup_timeout_s writes the new value and emits the snapshot."""
        store = AlarmSettingsStore()
        with qtbot.waitSignal(store.sig_changed, timeout=500) as blocker:
            store.set_popup_timeout_s(8)
        snapshot = blocker.args[0]
        assert isinstance(snapshot, AlarmSettings)
        assert snapshot.popup_timeout_s == 8
        assert store.settings.popup_timeout_s == 8

    def test_set_popup_timeout_s_clamps_to_range(self) -> None:
        """Out-of-range timeouts are clamped to the supported window."""
        store = AlarmSettingsStore()
        store.set_popup_timeout_s(0)
        assert store.settings.popup_timeout_s == POPUP_TIMEOUT_MIN_S
        store.set_popup_timeout_s(10_000)
        assert store.settings.popup_timeout_s == POPUP_TIMEOUT_MAX_S
        store.set_popup_timeout_s(-5)
        assert store.settings.popup_timeout_s == POPUP_TIMEOUT_MIN_S

    def test_setter_is_noop_when_value_unchanged(self, qtbot: QtBot) -> None:
        """Setting the same value does not reemit sig_changed."""
        store = AlarmSettingsStore()
        with qtbot.assertNotEmitted(store.sig_changed, wait=100):
            store.set_popup_enabled(store.settings.popup_enabled)

    def test_set_sound_enabled_flips_and_emits(self, qtbot: QtBot) -> None:
        """set_sound_enabled flips the field and emits the new snapshot."""
        store = AlarmSettingsStore()
        with qtbot.waitSignal(store.sig_changed, timeout=500) as blocker:
            store.set_sound_enabled(False)
        assert blocker.args[0].sound_enabled is False
        assert store.settings.sound_enabled is False

    def test_set_sound_preset_normalizes_unknown(self) -> None:
        """An unrecognized preset falls back to the default selection."""
        store = AlarmSettingsStore()
        store.set_sound_preset("does-not-exist")
        assert store.settings.sound_preset == SOUND_DEFAULT_PRESET

    def test_set_sound_preset_clears_custom_path(self) -> None:
        """Picking a preset drops any previously configured custom path."""
        store = AlarmSettingsStore()
        store.set_sound_path("/tmp/custom.wav")
        store.set_sound_preset(SOUND_PRESETS[-1])
        assert store.settings.sound_preset == SOUND_PRESETS[-1]
        assert store.settings.sound_path == ""

    def test_set_sound_path_overrides_preset_selection(self) -> None:
        """A custom path is stored independently of the preset selection."""
        store = AlarmSettingsStore()
        store.set_sound_path("/tmp/custom.wav")
        assert store.settings.sound_path == "/tmp/custom.wav"


class TestPersistence:
    """Changes survive store reconstruction by way of QSettings."""

    def test_popup_enabled_persists_across_stores(self) -> None:
        """A second store reads back the toggle the first one wrote."""
        first = AlarmSettingsStore()
        first.set_popup_enabled(False)
        assert AlarmSettingsStore().settings.popup_enabled is False

    def test_popup_timeout_persists_across_stores(self) -> None:
        """A second store reads back the timeout the first one wrote."""
        first = AlarmSettingsStore()
        first.set_popup_timeout_s(12)
        assert AlarmSettingsStore().settings.popup_timeout_s == 12

    def test_sound_fields_persist_across_stores(self) -> None:
        """Sound settings round-trip through QSettings."""
        first = AlarmSettingsStore()
        first.set_sound_enabled(False)
        first.set_sound_path("/tmp/custom.wav")
        reopened = AlarmSettingsStore()
        assert reopened.settings.sound_enabled is False
        assert reopened.settings.sound_path == "/tmp/custom.wav"


class TestCache:
    """clear_cache drops the singleton without touching persisted state."""

    def test_clear_cache_forces_fresh_store_on_next_call(self) -> None:
        """The next alarm.store() rebuilds the singleton after clear_cache."""
        first = alarm.store()
        alarm.settings.clear_cache()
        assert alarm.store() is not first
