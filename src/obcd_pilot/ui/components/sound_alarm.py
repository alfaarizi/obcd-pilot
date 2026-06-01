"""Audio alert for change detections.

A single QSoundEffect plays every alert. play_alert stops in-flight playback and
restarts so rapid detections replace the sound rather than overlapping.
"""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtMultimedia import QSoundEffect

from obcd_pilot import alarm
from obcd_pilot.alarm import AlarmSettings
from obcd_pilot.alarm.settings import SOUND_DEFAULT_PRESET
from obcd_pilot.pipeline import Detection
from obcd_pilot.resources import resource_path

_SOUNDS_REL = "ui/sounds"

logger = logging.getLogger(__name__)


class SoundAlarm(QObject):
    """Plays a short audio cue when a change is detected."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Build the sound effect and bind it to the current alarm source."""
        super().__init__(parent)
        self._effect = QSoundEffect(self)
        self._store = alarm.store()
        settings = self._store.settings
        self._last_sound_path = settings.sound_path
        self._last_sound_preset = settings.sound_preset
        self._reload_source(settings)
        self._store.sig_changed.connect(self._on_settings_changed)

    @Slot(Detection)
    def play_alert(self, detection: Detection) -> None:
        """Play the alert if the sound channel is enabled.

        Stops any in-flight playback first so rapid detections replace the
        sound instead of overlapping.
        """
        if not self._store.settings.sound_enabled or not detection.change_detected:
            return
        self._effect.stop()
        self._effect.play()

    @Slot(AlarmSettings)
    def _on_settings_changed(self, settings: AlarmSettings) -> None:
        """Re-resolve the source only when sound fields change."""
        if (
            settings.sound_path == self._last_sound_path
            and settings.sound_preset == self._last_sound_preset
        ):
            return
        self._last_sound_path = settings.sound_path
        self._last_sound_preset = settings.sound_preset
        self._reload_source(settings)

    def _reload_source(self, settings: AlarmSettings) -> None:
        """Point the effect at the source resolved for these settings."""
        self._effect.setSource(QUrl.fromLocalFile(str(_resolve_source(settings))))


def _resolve_source(settings: AlarmSettings) -> Path:
    """Pick the user supplied file if present, else the configured preset.

    Falls back to the shipped default preset when a custom file is set but
    cannot be read.
    """
    if not settings.sound_path:
        return _preset_path(settings.sound_preset)
    custom = Path(settings.sound_path)
    if custom.is_file():
        return custom
    logger.warning(
        "Alarm sound file %s not found, falling back to default",
        settings.sound_path,
    )
    return _preset_path(SOUND_DEFAULT_PRESET)


def _preset_path(name: str) -> Path:
    """Resolve a bundled preset, falling back to the default preset on miss."""
    sounds_dir = resource_path(_SOUNDS_REL)
    candidate = sounds_dir / f"{name}.wav"
    if candidate.is_file():
        return candidate
    return sounds_dir / f"{SOUND_DEFAULT_PRESET}.wav"
