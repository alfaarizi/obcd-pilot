"""Alarm settings view.

Each checkbox writes through to the store on toggle, and store side changes
sync back through sig_changed. New channels are added by appending one entry
to the _CHANNELS tuple after extending AlarmSettings and the store.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from obcd_pilot import alarm
from obcd_pilot.alarm import AlarmSettings, AlarmSettingsStore


@dataclass(frozen=True, slots=True)
class _Channel:
    """Static descriptor binding one checkbox to one store field."""

    label: str
    getter: Callable[[AlarmSettings], bool]
    setter: Callable[[AlarmSettingsStore, bool], None]


_CHANNELS: tuple[_Channel, ...] = (
    _Channel(
        label="Show pop-up alert on change detection",
        getter=lambda settings: settings.popup_enabled,
        setter=AlarmSettingsStore.set_popup_enabled,
    ),
)


class AlarmsView(QWidget):
    """Stacked toggles, one per alarm channel."""

    def __init__(self) -> None:
        """Build a checkbox per channel and bind both directions to the store."""
        super().__init__()
        self.setObjectName("alarms-view")

        self._store = alarm.store()
        self._checkboxes: list[tuple[_Channel, QCheckBox]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(8)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        for channel in _CHANNELS:
            checkbox = self._create_checkbox(channel)
            root.addWidget(checkbox)
            self._checkboxes.append((channel, checkbox))

        self._store.sig_changed.connect(self._sync_from_store)

    def _create_checkbox(self, channel: _Channel) -> QCheckBox:
        """Build one checkbox wired to channel in both directions."""
        checkbox = QCheckBox(channel.label)
        checkbox.setChecked(channel.getter(self._store.settings))
        checkbox.toggled.connect(partial(channel.setter, self._store))
        return checkbox

    @Slot(AlarmSettings)
    def _sync_from_store(self, settings: AlarmSettings) -> None:
        """Pull store side changes into every checkbox without re-emitting."""
        for channel, checkbox in self._checkboxes:
            desired = channel.getter(settings)
            if checkbox.isChecked() == desired:
                continue
            checkbox.blockSignals(True)
            checkbox.setChecked(desired)
            checkbox.blockSignals(False)
