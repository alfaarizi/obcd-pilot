"""Integration tests for SoundAlarm."""

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect
from pytestqt.qtbot import QtBot

from obcd_pilot import alarm
from obcd_pilot.alarm.settings import SOUND_DEFAULT_PRESET, SOUND_PRESETS
from obcd_pilot.pipeline import Detection
from obcd_pilot.ui.components import sound_alarm as sound_alarm_module
from obcd_pilot.ui.components.sound_alarm import SoundAlarm


@pytest.fixture()
def sound_alarm(qtbot: QtBot) -> SoundAlarm:
    """A SoundAlarm with its source primed against the default preset."""
    return SoundAlarm()


def test_default_source_points_to_bundled_preset(sound_alarm: SoundAlarm) -> None:
    """The effect loads the bundled default wav at construction."""
    source = sound_alarm._effect.source()
    assert source.isLocalFile()
    assert Path(source.toLocalFile()).is_file()
    assert Path(source.toLocalFile()).suffix == ".wav"


def test_plays_when_channel_enabled(
    sound_alarm: SoundAlarm,
    make_detection: Callable[..., Detection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """play_alert triggers the effect when the sound channel is enabled."""
    calls: list[str] = []
    monkeypatch.setattr(sound_alarm._effect, "stop", lambda: calls.append("stop"))
    monkeypatch.setattr(sound_alarm._effect, "play", lambda: calls.append("play"))
    sound_alarm.play_alert(make_detection(change_detected=True))
    assert calls == ["stop", "play"]


def test_suppressed_when_channel_disabled(
    sound_alarm: SoundAlarm,
    make_detection: Callable[..., Detection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """play_alert is a noop while the sound channel is off."""
    alarm.store().set_sound_enabled(False)
    calls: list[str] = []
    monkeypatch.setattr(sound_alarm._effect, "play", lambda: calls.append("play"))
    sound_alarm.play_alert(make_detection(change_detected=True))
    assert calls == []


def test_ignores_non_change_detection(
    sound_alarm: SoundAlarm,
    make_detection: Callable[..., Detection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A detection with change_detected False does not play the alert."""
    calls: list[str] = []
    monkeypatch.setattr(sound_alarm._effect, "play", lambda: calls.append("play"))
    sound_alarm.play_alert(make_detection(change_detected=False))
    assert calls == []


def test_rapid_alerts_restart_playback(
    sound_alarm: SoundAlarm,
    make_detection: Callable[..., Detection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Consecutive alerts stop the in-flight playback before restarting."""
    calls: list[str] = []
    monkeypatch.setattr(sound_alarm._effect, "stop", lambda: calls.append("stop"))
    monkeypatch.setattr(sound_alarm._effect, "play", lambda: calls.append("play"))
    sound_alarm.play_alert(make_detection(change_detected=True))
    sound_alarm.play_alert(make_detection(change_detected=True))
    assert calls == ["stop", "play", "stop", "play"]


def test_custom_path_overrides_default_source(qtbot: QtBot, tmp_path: Path) -> None:
    """Configuring a custom file routes the effect at that file."""
    custom = tmp_path / "custom.wav"
    custom.write_bytes(b"RIFF0000WAVE")
    alarm.store().set_sound_path(str(custom))
    sound_alarm = SoundAlarm()
    assert sound_alarm._effect.source() == QUrl.fromLocalFile(str(custom))


def test_missing_custom_path_falls_back_and_warns(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing custom file falls back to the shipped default preset and logs."""
    warnings: list[str] = []
    monkeypatch.setattr(
        sound_alarm_module.logger,
        "warning",
        lambda msg, *args: warnings.append(msg % args),
    )
    alarm.store().set_sound_path("/does/not/exist.wav")
    sound_alarm = SoundAlarm()
    source_path = Path(sound_alarm._effect.source().toLocalFile())
    assert source_path.name == f"{SOUND_DEFAULT_PRESET}.wav"
    assert any("/does/not/exist.wav" in entry for entry in warnings)


def test_missing_path_warns_only_once_per_value(
    qtbot: QtBot,
    make_detection: Callable[..., Detection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated play_alert calls do not re-log the same missing path."""
    warnings: list[str] = []
    monkeypatch.setattr(
        sound_alarm_module.logger,
        "warning",
        lambda msg, *args: warnings.append(msg % args),
    )
    alarm.store().set_sound_path("/does/not/exist.wav")
    sound_alarm = SoundAlarm()
    for _ in range(5):
        sound_alarm.play_alert(make_detection(change_detected=True))
    assert len(warnings) == 1


def test_missing_path_falls_back_to_shipped_default_not_selected_preset(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback ignores the selected preset and uses the shipped default."""
    monkeypatch.setattr(sound_alarm_module.logger, "warning", lambda *_: None)
    non_default = next(p for p in SOUND_PRESETS if p != SOUND_DEFAULT_PRESET)
    store = alarm.store()
    store.set_sound_preset(non_default)
    store.set_sound_path("/does/not/exist.wav")
    sound_alarm = SoundAlarm()
    source_path = Path(sound_alarm._effect.source().toLocalFile())
    assert source_path.name == f"{SOUND_DEFAULT_PRESET}.wav"


def test_settings_change_reloads_source(
    sound_alarm: SoundAlarm, tmp_path: Path
) -> None:
    """A store side path change refreshes the effect's source url."""
    custom = tmp_path / "later.wav"
    custom.write_bytes(b"RIFF0000WAVE")
    alarm.store().set_sound_path(str(custom))
    assert sound_alarm._effect.source() == QUrl.fromLocalFile(str(custom))


def test_source_loads_to_ready_status(sound_alarm: SoundAlarm, qtbot: QtBot) -> None:
    """The bundled preset reaches Ready quickly enough for sub-500 ms playback."""
    qtbot.waitUntil(
        lambda: sound_alarm._effect.status() == QSoundEffect.Status.Ready,
        timeout=500,
    )
