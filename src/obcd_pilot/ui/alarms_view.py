"""Alarm settings view.

Each control writes through to the store on change, and store side changes
sync back through sig_changed. New channels are added by appending one entry
to the _CHANNELS tuple after extending AlarmSettings and the store.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from obcd_pilot import alarm
from obcd_pilot.alarm import AlarmSettings, AlarmSettingsStore
from obcd_pilot.alarm.settings import POPUP_TIMEOUT_MAX_S, POPUP_TIMEOUT_MIN_S


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
    """Stacked toggles, one per alarm channel, plus pop-up tunables."""

    def __init__(self) -> None:
        """Build a checkbox per channel and bind both directions to the store."""
        super().__init__()
        self.setObjectName("alarms-view")

        self._store = alarm.store()
        self._checkboxes: list[tuple[_Channel, QCheckBox]] = []
        self._popup_timeout_spin = self._create_popup_timeout_spin()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(8)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        for channel in _CHANNELS:
            checkbox = self._create_checkbox(channel)
            root.addWidget(checkbox)
            self._checkboxes.append((channel, checkbox))
        root.addWidget(self._create_popup_timeout_row(self._popup_timeout_spin))

        self._store.sig_changed.connect(self._sync_from_store)

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

    @staticmethod
    def _create_popup_timeout_row(spin: QSpinBox) -> QWidget:
        """Lay the timeout label and spin box on a single row."""
        row = QWidget()
        h_layout = QHBoxLayout(row)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.addWidget(QLabel("Auto-dismiss pop-up after"))
        h_layout.addStretch(1)
        h_layout.addWidget(spin)
        return row

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
