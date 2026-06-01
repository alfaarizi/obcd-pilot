"""Integration tests for AlarmsView."""

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from obcd_pilot import alarm
from obcd_pilot.alarm.settings import SOUND_PRESETS
from obcd_pilot.ui.alarms_view import AlarmsView


@pytest.fixture()
def view(qtbot: QtBot) -> AlarmsView:
    """An AlarmsView registered with qtbot for cleanup."""
    widget = AlarmsView()
    qtbot.addWidget(widget)
    return widget


def test_renders_one_checkbox_per_channel(view: AlarmsView) -> None:
    """The view builds one checkbox per declared channel."""
    assert len(view._checkboxes) == 2
    for channel, checkbox in view._checkboxes:
        assert channel.label in checkbox.text()


def test_checkbox_reflects_persisted_state(qtbot: QtBot) -> None:
    """The checkbox starts in the state previously written to QSettings."""
    alarm.store().set_popup_enabled(False)
    alarm.settings.clear_cache()
    view = AlarmsView()
    qtbot.addWidget(view)
    _, checkbox = view._checkboxes[0]
    assert checkbox.isChecked() is False


def test_toggle_writes_through_to_store(view: AlarmsView, qtbot: QtBot) -> None:
    """Toggling the checkbox emits sig_changed and updates the store."""
    store = alarm.store()
    _, checkbox = view._checkboxes[0]
    with qtbot.waitSignal(store.sig_changed, timeout=500):
        checkbox.setChecked(False)
    assert store.settings.popup_enabled is False


def test_store_change_syncs_into_view(view: AlarmsView) -> None:
    """A store side change propagates back into the checkbox state."""
    _, checkbox = view._checkboxes[0]
    alarm.store().set_popup_enabled(False)
    assert checkbox.isChecked() is False


def test_popup_timeout_spin_reflects_persisted_state(qtbot: QtBot) -> None:
    """The spin box opens at the value previously written to QSettings."""
    alarm.store().set_popup_timeout_s(9)
    alarm.settings.clear_cache()
    view = AlarmsView()
    qtbot.addWidget(view)
    assert view._popup_timeout_spin.value() == 9


def test_popup_timeout_spin_writes_through_to_store(
    view: AlarmsView, qtbot: QtBot
) -> None:
    """Changing the spin box value persists the new timeout in seconds."""
    store = alarm.store()
    with qtbot.waitSignal(store.sig_changed, timeout=500):
        view._popup_timeout_spin.setValue(12)
    assert store.settings.popup_timeout_s == 12


def test_store_timeout_change_syncs_into_spin(view: AlarmsView) -> None:
    """A store side timeout change propagates back into the spin box."""
    alarm.store().set_popup_timeout_s(7)
    assert view._popup_timeout_spin.value() == 7


def test_sound_combo_lists_every_preset_plus_custom(view: AlarmsView) -> None:
    """The combo offers each bundled preset followed by a custom file entry."""
    combo = view._sound_source_combo
    assert combo.count() == len(SOUND_PRESETS) + 1
    for index, preset in enumerate(SOUND_PRESETS):
        assert combo.itemData(index) == preset
    assert combo.itemData(combo.count() - 1) == ""


def test_sound_combo_reflects_persisted_preset(qtbot: QtBot) -> None:
    """The combo opens at the preset previously written to QSettings."""
    alarm.store().set_sound_preset(SOUND_PRESETS[-1])
    alarm.settings.clear_cache()
    view = AlarmsView()
    qtbot.addWidget(view)
    assert view._sound_source_combo.currentData() == SOUND_PRESETS[-1]


def test_sound_combo_writes_preset_through_to_store(
    view: AlarmsView, qtbot: QtBot
) -> None:
    """Activating a preset entry persists the new sound_preset."""
    store = alarm.store()
    with qtbot.waitSignal(store.sig_changed, timeout=500):
        view._sound_source_combo.activated.emit(len(SOUND_PRESETS) - 1)
    assert store.settings.sound_preset == SOUND_PRESETS[-1]


def test_sound_combo_reflects_custom_path(view: AlarmsView, tmp_path: Path) -> None:
    """A configured custom path is shown via the custom entry label."""
    custom = tmp_path / "alarm.wav"
    custom.write_bytes(b"RIFF0000WAVE")
    alarm.store().set_sound_path(str(custom))
    combo = view._sound_source_combo
    assert combo.currentIndex() == combo.count() - 1
    assert custom.name in combo.currentText()
