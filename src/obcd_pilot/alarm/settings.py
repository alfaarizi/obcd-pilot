"""Typed observable store for alarm channel settings.

The store reads the snapshot from QSettings at construction, exposes per channel
setter slots, and re-emits sig_changed on change. New channels are added by extending
the dataclass, adding a setter slot, and persisting the new key.
"""

from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, QSettings, Signal, Slot

POPUP_TIMEOUT_MS = 5_000


@dataclass(frozen=True, slots=True)
class AlarmSettings:
    """Snapshot of all alarm channel toggles."""

    popup_enabled: bool = True


class AlarmSettingsStore(QObject):
    """Observable source of truth for alarm toggles, backed by QSettings."""

    sig_changed = Signal(AlarmSettings)

    _KEY_GROUP = "alarms"
    _KEY_POPUP_ENABLED = f"{_KEY_GROUP}/popup_enabled"

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
                    self._KEY_POPUP_ENABLED, defaults.popup_enabled, type=bool
                )
            ),
        )

    def _persist(self, snapshot: AlarmSettings) -> None:
        """Write a snapshot through to QSettings."""
        self._qsettings.setValue(self._KEY_POPUP_ENABLED, snapshot.popup_enabled)


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
    QSettings().remove(AlarmSettingsStore._KEY_GROUP)
    _store = None
