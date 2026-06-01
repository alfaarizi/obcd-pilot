"""Typed observable store for alarm channel settings.

The store reads the snapshot from QSettings at construction, exposes per channel
setter slots, and re-emits sig_changed on change. New channels are added by extending
the dataclass, adding a setter slot, and persisting the new key.
"""

from dataclasses import dataclass, replace
from typing import cast

from PySide6.QtCore import QObject, QSettings, Signal, Slot

POPUP_TIMEOUT_MIN_S = 1
POPUP_TIMEOUT_MAX_S = 60

SOUND_PRESETS: tuple[str, ...] = ("chime", "beep", "alert")
SOUND_DEFAULT_PRESET = "chime"

_KEY_GROUP = "alarms"
_KEY_POPUP_ENABLED = f"{_KEY_GROUP}/popup_enabled"
_KEY_POPUP_TIMEOUT_S = f"{_KEY_GROUP}/popup_timeout_s"
_KEY_SOUND_ENABLED = f"{_KEY_GROUP}/sound_enabled"
_KEY_SOUND_PRESET = f"{_KEY_GROUP}/sound_preset"
_KEY_SOUND_PATH = f"{_KEY_GROUP}/sound_path"


def _clamp_timeout_s(value: int) -> int:
    """Constrain the pop-up auto-dismiss timeout to the supported range."""
    return max(POPUP_TIMEOUT_MIN_S, min(POPUP_TIMEOUT_MAX_S, value))


def _normalize_preset(value: str) -> str:
    """Fall back to the default preset when value is not a known selection."""
    return value if value in SOUND_PRESETS else SOUND_DEFAULT_PRESET


@dataclass(frozen=True, slots=True)
class AlarmSettings:
    """Snapshot of all alarm channel settings."""

    popup_enabled: bool = True
    popup_timeout_s: int = 3
    sound_enabled: bool = True
    sound_preset: str = SOUND_DEFAULT_PRESET
    sound_path: str = ""


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
        self._apply(replace(self._settings, popup_timeout_s=_clamp_timeout_s(value)))

    @Slot(bool)
    def set_sound_enabled(self, value: bool) -> None:
        """Toggle the sound channel and persist the change."""
        self._apply(replace(self._settings, sound_enabled=value))

    @Slot(str)
    def set_sound_preset(self, value: str) -> None:
        """Select a bundled preset and clear any custom file override."""
        self._apply(
            replace(
                self._settings,
                sound_preset=_normalize_preset(value),
                sound_path="",
            )
        )

    @Slot(str)
    def set_sound_path(self, value: str) -> None:
        """Override the preset with a custom file path."""
        self._apply(replace(self._settings, sound_path=value))

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
            popup_timeout_s=_clamp_timeout_s(
                cast(
                    int,
                    self._qsettings.value(
                        _KEY_POPUP_TIMEOUT_S, defaults.popup_timeout_s, type=int
                    ),
                )
            ),
            sound_enabled=bool(
                self._qsettings.value(
                    _KEY_SOUND_ENABLED, defaults.sound_enabled, type=bool
                )
            ),
            sound_preset=_normalize_preset(
                cast(
                    str,
                    self._qsettings.value(
                        _KEY_SOUND_PRESET, defaults.sound_preset, type=str
                    ),
                )
            ),
            sound_path=cast(
                str,
                self._qsettings.value(_KEY_SOUND_PATH, defaults.sound_path, type=str),
            ),
        )

    def _persist(self, snapshot: AlarmSettings) -> None:
        """Write a snapshot through to QSettings."""
        self._qsettings.setValue(_KEY_POPUP_ENABLED, snapshot.popup_enabled)
        self._qsettings.setValue(_KEY_POPUP_TIMEOUT_S, snapshot.popup_timeout_s)
        self._qsettings.setValue(_KEY_SOUND_ENABLED, snapshot.sound_enabled)
        self._qsettings.setValue(_KEY_SOUND_PRESET, snapshot.sound_preset)
        self._qsettings.setValue(_KEY_SOUND_PATH, snapshot.sound_path)


_store: AlarmSettingsStore | None = None


def store() -> AlarmSettingsStore:
    """Return the process wide store, build it on first use."""
    global _store
    if _store is None:
        _store = AlarmSettingsStore()
    return _store


def clear_cache() -> None:
    """Drop the cached singleton store, leaving persisted values intact."""
    global _store
    _store = None


def reset() -> None:
    """Clear persisted alarm settings and drop the store."""
    global _store
    qsettings = QSettings()
    qsettings.remove(_KEY_GROUP)
    qsettings.sync()
    _store = None
