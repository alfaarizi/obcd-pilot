"""Alarm settings view.

Each control writes through to the store on change, and store side changes
sync back through sig_changed. New channels are added by extending AlarmSettings
and the store, appending an entry to _CHANNELS, and laying out the section.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot import alarm
from obcd_pilot.alarm import AlarmSettings, AlarmSettingsStore
from obcd_pilot.alarm.settings import (
    POPUP_TIMEOUT_MAX_S,
    POPUP_TIMEOUT_MIN_S,
    SOUND_PRESETS,
)

_CUSTOM_SOUND_LABEL = "Custom file..."
_SOUND_FILE_FILTER = "Wave Audio (*.wav)"
_SECTION_INDENT_PX = 36


@dataclass(frozen=True, slots=True)
class _Channel:
    """Static descriptor binding one checkbox to one store field."""

    label: str
    getter: Callable[[AlarmSettings], bool]
    setter: Callable[[AlarmSettingsStore, bool], None]


_POPUP_CHANNEL = _Channel(
    label="Show pop-up alert on change detection",
    getter=lambda settings: settings.popup_enabled,
    setter=AlarmSettingsStore.set_popup_enabled,
)

_SOUND_CHANNEL = _Channel(
    label="Play sound on change detection",
    getter=lambda settings: settings.sound_enabled,
    setter=AlarmSettingsStore.set_sound_enabled,
)

_CHANNELS: tuple[_Channel, ...] = (_POPUP_CHANNEL, _SOUND_CHANNEL)


class AlarmsView(QWidget):
    """One section per alarm channel: a toggle followed by its tunables."""

    def __init__(self) -> None:
        """Build channel sections and bind controls bidirectionally to the store."""
        super().__init__()
        self.setObjectName("alarms-view")

        self._store = alarm.store()
        self._popup_timeout_spin = self._create_popup_timeout_spin()
        self._sound_source_combo = self._create_sound_source_combo()
        self._checkboxes: tuple[tuple[_Channel, QCheckBox], ...] = tuple(
            (channel, self._create_checkbox(channel)) for channel in _CHANNELS
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(8)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addWidget(self._checkbox_for(_POPUP_CHANNEL))
        root.addWidget(
            self._create_row("Auto-dismiss pop-up after", self._popup_timeout_spin)
        )
        root.addWidget(self._checkbox_for(_SOUND_CHANNEL))
        root.addWidget(self._create_row("Sound effect", self._sound_source_combo))

        self._sync_sound_source_combo(self._store.settings)
        self._store.sig_changed.connect(self._sync_from_store)

    def _checkbox_for(self, channel: _Channel) -> QCheckBox:
        """Return the checkbox built for channel."""
        return next(box for owner, box in self._checkboxes if owner is channel)

    def _create_checkbox(self, channel: _Channel) -> QCheckBox:
        """Build one checkbox wired to channel in both directions."""
        checkbox = QCheckBox(channel.label)
        checkbox.setChecked(channel.getter(self._store.settings))
        checkbox.toggled.connect(partial(channel.setter, self._store))
        return checkbox

    def _create_popup_timeout_spin(self) -> QSpinBox:
        """Build the spin box for the pop-up auto-dismiss timeout in seconds."""
        spin = QSpinBox()
        spin.setObjectName("popup-timeout-spin")
        spin.setRange(POPUP_TIMEOUT_MIN_S, POPUP_TIMEOUT_MAX_S)
        spin.setSuffix(" s")
        spin.setValue(self._store.settings.popup_timeout_s)
        spin.valueChanged.connect(self._store.set_popup_timeout_s)
        return spin

    def _create_sound_source_combo(self) -> QComboBox:
        """Build the combo listing bundled presets plus a custom-file option."""
        combo = QComboBox()
        combo.setObjectName("sound-source-combo")
        for preset in SOUND_PRESETS:
            combo.addItem(preset.title(), preset)
        combo.addItem(_CUSTOM_SOUND_LABEL, "")
        combo.activated.connect(self._on_sound_source_activated)
        return combo

    @staticmethod
    def _create_row(label: str, control: QWidget) -> QWidget:
        """Lay a label and control on one row, indented under their channel."""
        row = QWidget()
        h_layout = QHBoxLayout(row)
        h_layout.setContentsMargins(_SECTION_INDENT_PX, 0, 0, 0)
        h_layout.addWidget(QLabel(label))
        h_layout.addStretch(1)
        h_layout.addWidget(control)
        return row

    @Slot(int)
    def _on_sound_source_activated(self, index: int) -> None:
        """Persist the picked preset, or prompt for a custom file path."""
        preset = self._sound_source_combo.itemData(index)
        if preset:
            self._store.set_sound_preset(preset)
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose alert sound", "", _SOUND_FILE_FILTER
        )
        if path:
            self._store.set_sound_path(path)
        else:
            self._sync_sound_source_combo(self._store.settings)

    @Slot(AlarmSettings)
    def _sync_from_store(self, settings: AlarmSettings) -> None:
        """Pull store side changes into every control without re-emitting."""
        for channel, checkbox in self._checkboxes:
            target = channel.getter(settings)
            if checkbox.isChecked() == target:
                continue
            checkbox.blockSignals(True)
            checkbox.setChecked(target)
            checkbox.blockSignals(False)

        if self._popup_timeout_spin.value() != settings.popup_timeout_s:
            self._popup_timeout_spin.blockSignals(True)
            self._popup_timeout_spin.setValue(settings.popup_timeout_s)
            self._popup_timeout_spin.blockSignals(False)

        self._sync_sound_source_combo(settings)

    def _sync_sound_source_combo(self, settings: AlarmSettings) -> None:
        """Reflect the active preset or custom file in the combo."""
        combo = self._sound_source_combo
        custom_index = combo.count() - 1
        if settings.sound_path:
            label = f"Custom: {Path(settings.sound_path).name}"
            target_index = custom_index
        else:
            label = _CUSTOM_SOUND_LABEL
            target_index = next(
                (
                    i
                    for i in range(custom_index)
                    if combo.itemData(i) == settings.sound_preset
                ),
                0,
            )
        combo.blockSignals(True)
        combo.setItemText(custom_index, label)
        combo.setCurrentIndex(target_index)
        combo.blockSignals(False)
