"""Integration tests for PlaybackOverlay widget."""

import pytest
from pytestqt.qtbot import QtBot

from obcd_pilot.capture import Playback
from obcd_pilot.ui.components.playback_overlay import PlaybackOverlay


@pytest.fixture()
def overlay(qtbot: QtBot) -> PlaybackOverlay:
    """A PlaybackOverlay widget registered with qtbot for cleanup."""
    widget = PlaybackOverlay()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture()
def playback_30fps() -> Playback:
    """A representative Playback at one second into a thirty-second clip."""
    return Playback(
        position_ms=1000.0,
        duration_ms=30000.0,
        frame_index=30,
        frame_count=900,
    )


class TestPlaybackOverlayConstruction:
    """Verify the overlay's default state immediately after construction."""

    def test_is_not_seeking(self, overlay: PlaybackOverlay) -> None:
        """Overlay starts with _is_seeking False."""
        assert not overlay._is_seeking

    def test_is_playing_by_default(self, overlay: PlaybackOverlay) -> None:
        """Overlay assumes playback is active at construction."""
        assert overlay._is_playing

    def test_last_playback_is_none(self, overlay: PlaybackOverlay) -> None:
        """No playback data has arrived before the first update_position call."""
        assert overlay._last_playback is None

    def test_slider_range_starts_at_zero(self, overlay: PlaybackOverlay) -> None:
        """Slider minimum and maximum are both zero until a Playback is received."""
        assert overlay._playback_slider.minimum() == 0
        assert overlay._playback_slider.maximum() == 0


class TestUpdatePosition:
    """Tests for PlaybackOverlay.update_position."""

    def test_stores_playback(
        self, overlay: PlaybackOverlay, playback_30fps: Playback
    ) -> None:
        """update_position retains the Playback for slider move calculations."""
        overlay.update_position(playback_30fps)
        assert overlay._last_playback is playback_30fps

    def test_sets_slider_range(
        self, overlay: PlaybackOverlay, playback_30fps: Playback
    ) -> None:
        """update_position configures the slider's maximum to frame_count - 1."""
        overlay.update_position(playback_30fps)
        assert overlay._playback_slider.maximum() == playback_30fps.frame_count - 1

    def test_sets_slider_value_when_not_seeking(
        self, overlay: PlaybackOverlay, playback_30fps: Playback
    ) -> None:
        """update_position moves the slider thumb to the current frame_index."""
        overlay.update_position(playback_30fps)
        assert overlay._playback_slider.value() == playback_30fps.frame_index

    def test_does_not_update_slider_value_while_seeking(
        self, overlay: PlaybackOverlay, playback_30fps: Playback
    ) -> None:
        """update_position skips slider repositioning while the user is dragging."""
        overlay._is_seeking = True
        overlay.update_position(playback_30fps)
        assert overlay._playback_slider.value() == 0

    def test_time_label_shows_position_and_duration(
        self, overlay: PlaybackOverlay
    ) -> None:
        """update_position formats the label as 'mm:ss / mm:ss'."""
        playback = Playback(65000.0, 125000.0, 65 * 30, 125 * 30)
        overlay.update_position(playback)
        assert overlay._time_label.text() == "01:05 / 02:05"

    def test_handles_zero_frame_count_without_error(
        self, overlay: PlaybackOverlay
    ) -> None:
        """update_position does not raise when frame_count is zero."""
        empty = Playback(0.0, 0.0, 0, 0)
        overlay.update_position(empty)
        assert overlay._playback_slider.maximum() == 0


class TestSetPlaying:
    """Tests for PlaybackOverlay.set_playing."""

    def test_set_playing_true_stores_state(self, overlay: PlaybackOverlay) -> None:
        """set_playing(True) marks the overlay as actively playing."""
        overlay.set_playing(False)
        overlay.set_playing(True)
        assert overlay._is_playing

    def test_set_playing_false_stores_state(self, overlay: PlaybackOverlay) -> None:
        """set_playing(False) marks the overlay as paused."""
        overlay.set_playing(False)
        assert not overlay._is_playing


class TestReset:
    """Tests for PlaybackOverlay.reset."""

    def test_reset_clears_last_playback(
        self, overlay: PlaybackOverlay, playback_30fps: Playback
    ) -> None:
        """reset() discards any stored Playback."""
        overlay.update_position(playback_30fps)
        overlay.reset()
        assert overlay._last_playback is None

    def test_reset_clears_seeking_flag(self, overlay: PlaybackOverlay) -> None:
        """reset() exits seek mode."""
        overlay._is_seeking = True
        overlay.reset()
        assert not overlay._is_seeking

    def test_reset_restores_playing_flag(self, overlay: PlaybackOverlay) -> None:
        """reset() treats the widget as playing after a reset."""
        overlay.set_playing(False)
        overlay.reset()
        assert overlay._is_playing

    def test_reset_zeroes_slider(
        self, overlay: PlaybackOverlay, playback_30fps: Playback
    ) -> None:
        """reset() moves the slider back to position 0."""
        overlay.update_position(playback_30fps)
        overlay.reset()
        assert overlay._playback_slider.value() == 0
        assert overlay._playback_slider.maximum() == 0

    def test_reset_restores_time_label(
        self, overlay: PlaybackOverlay, playback_30fps: Playback
    ) -> None:
        """reset() restores the time label to the zero timestamp."""
        overlay.update_position(playback_30fps)
        overlay.reset()
        assert overlay._time_label.text() == "00:00 / 00:00"


class TestSignals:
    """Tests for signals emitted by PlaybackOverlay in response to user actions."""

    def test_play_clicked_emits_sig_video_played(
        self, overlay: PlaybackOverlay, qtbot: QtBot
    ) -> None:
        """Clicking the play button emits sig_video_played."""
        with qtbot.waitSignal(overlay.sig_video_played, timeout=500):
            overlay._play_button.click()

    def test_play_clicked_toggles_playing_state(self, overlay: PlaybackOverlay) -> None:
        """Clicking the play button flips _is_playing."""
        was_playing = overlay._is_playing
        overlay._play_button.click()
        assert overlay._is_playing == (not was_playing)

    def test_close_button_emits_sig_video_closed(
        self, overlay: PlaybackOverlay, qtbot: QtBot
    ) -> None:
        """Clicking the close button emits sig_video_closed."""
        with qtbot.waitSignal(overlay.sig_video_closed, timeout=500):
            overlay._close_button.click()

    def test_slider_pressed_sets_seeking(self, overlay: PlaybackOverlay) -> None:
        """_on_slider_pressed enables seek mode and emits sig_video_seek_started."""
        overlay._on_slider_pressed()
        assert overlay._is_seeking

    def test_slider_pressed_emits_seek_started(
        self, overlay: PlaybackOverlay, qtbot: QtBot
    ) -> None:
        """_on_slider_pressed emits sig_video_seek_started."""
        with qtbot.waitSignal(overlay.sig_video_seek_started, timeout=500):
            overlay._on_slider_pressed()

    def test_slider_released_clears_seeking(self, overlay: PlaybackOverlay) -> None:
        """_on_slider_released exits seek mode."""
        overlay._is_seeking = True
        overlay._on_slider_released()
        assert not overlay._is_seeking

    def test_slider_released_emits_seek_ended_with_value(
        self, overlay: PlaybackOverlay, qtbot: QtBot, playback_30fps: Playback
    ) -> None:
        """_on_slider_released emits sig_video_seek_ended carrying the slider value."""
        overlay.update_position(playback_30fps)
        overlay._playback_slider.setValue(50)

        with qtbot.waitSignal(overlay.sig_video_seek_ended, timeout=500) as blocker:
            overlay._on_slider_released()

        assert blocker.args == [50]

    def test_slider_moved_updates_time_label(
        self, overlay: PlaybackOverlay, playback_30fps: Playback
    ) -> None:
        """_on_slider_moved refreshes the time label without updating _last_playback."""
        overlay.update_position(playback_30fps)
        overlay._on_slider_moved(450)
        assert "00:15" in overlay._time_label.text()

    def test_slider_moved_with_no_playback_does_nothing(
        self, overlay: PlaybackOverlay
    ) -> None:
        """_on_slider_moved is a no-op when no Playback has been received yet."""
        overlay._on_slider_moved(100)

    def test_slider_moved_with_zero_frame_count_does_nothing(
        self, overlay: PlaybackOverlay
    ) -> None:
        """_on_slider_moved skips update when frame_count is zero."""
        overlay._last_playback = Playback(0.0, 0.0, 0, 0)
        overlay._on_slider_moved(0)
