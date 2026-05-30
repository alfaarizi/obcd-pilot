"""Typed observable store for alarm channel settings.

The store reads the snapshot from QSettings at construction, exposes per channel
setter slots, and re-emits sig_changed on change. New channels are added by extending
the dataclass, adding a setter slot, and persisting the new key.
"""

from dataclasses import dataclass, replace
from typing import cast

from PySide6.QtCore import QObject, QSettings, Signal, Slot

_KEY_GROUP = "alarms"
_KEY_POPUP_ENABLED = f"{_KEY_GROUP}/popup_enabled"
_KEY_POPUP_TIMEOUT_S = f"{_KEY_GROUP}/popup_timeout_s"


@dataclass(frozen=True, slots=True)
class AlarmSettings:
    """Snapshot of all alarm channel settings."""

    popup_enabled: bool = True
    popup_timeout_s: int = 3


class AlarmSettingsStore(QObject):
    """Observable source of truth for alarm settings, backed by QSettings."""

    sig_changed = Signal(AlarmSettings)

    def __init__(self, parent: QObject | None = None) -> None:
        """Load the persisted snapshot into memory."""
        super().__init__(parent)
        self._qsettings = QSettings()
        self._settings = self._load()

    @property
    def settings(self) -> AlarmSettings:
        """Return the current snapshot."""
        return self._settings

    @Slot(bool)
    def set_popup_enabled(self, value: bool) -> None:
        """Toggle the pop-up channel and persist the change."""
        self._apply(replace(self._settings, popup_enabled=value))

    @Slot(int)
    def set_popup_timeout_s(self, value: int) -> None:
        """Update the pop-up auto-dismiss timeout and persist the change."""
        self._apply(replace(self._settings, popup_timeout_s=value))

    def _apply(self, snapshot: AlarmSettings) -> None:
        """Commit a new snapshot, persist it, and notify observers."""
        if snapshot == self._settings:
            return
        self._settings = snapshot
        self._persist(snapshot)
        self.sig_changed.emit(snapshot)

    def _load(self) -> AlarmSettings:
        """Read persisted values, falling back to dataclass defaults."""
        defaults = AlarmSettings()
        return AlarmSettings(
            popup_enabled=bool(
                self._qsettings.value(
                    _KEY_POPUP_ENABLED, defaults.popup_enabled, type=bool
                )
            ),
            popup_timeout_s=cast(
                int,
                self._qsettings.value(
                    _KEY_POPUP_TIMEOUT_S, defaults.popup_timeout_s, type=int
                ),
            ),
        )

    def _persist(self, snapshot: AlarmSettings) -> None:
        """Write a snapshot through to QSettings."""
        self._qsettings.setValue(_KEY_POPUP_ENABLED, snapshot.popup_enabled)
        self._qsettings.setValue(_KEY_POPUP_TIMEOUT_S, snapshot.popup_timeout_s)


_store: AlarmSettingsStore | None = None


def store() -> AlarmSettingsStore:
    """Return the process wide store, build it on first use."""
    global _store
    if _store is None:
        _store = AlarmSettingsStore()
    return _store


def reset() -> None:
    """Clear persisted alarm settings and drop the store."""
    global _store
    qsettings = QSettings()
    qsettings.remove(_KEY_GROUP)
    qsettings.sync()
    _store = None
