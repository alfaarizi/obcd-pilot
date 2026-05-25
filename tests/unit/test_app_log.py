"""Unit tests for the application-wide file logger."""

import logging
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from obcd_pilot import app_log
from obcd_pilot.pipeline import Detection


def _read_log(path: Path) -> str:
    """Read the log file or return an empty string when it does not exist."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


class TestConfigure:
    """Tests for app_log.configure."""

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """AC-08.3: parent directory is auto-created."""
        target = tmp_path / "nested" / "deeper" / "app.log"
        app_log.configure(target)
        assert target.parent.is_dir()

    def test_attaches_handler_to_root_app_logger(self, tmp_path: Path) -> None:
        """The handler is attached to obcd_pilot, not Python's root logger."""
        logger = app_log.configure(tmp_path / "app.log")
        assert logger.name == app_log.ROOT_LOGGER_NAME
        assert logger is not logging.getLogger()

    def test_does_not_propagate_to_root(self, tmp_path: Path) -> None:
        """The app logger is detached from Python's root logger."""
        logger = app_log.configure(tmp_path / "app.log")
        assert logger.propagate is False

    def test_attaches_rotating_file_handler(self, tmp_path: Path) -> None:
        """The configured logger gets a RotatingFileHandler."""
        logger = app_log.configure(tmp_path / "app.log")
        assert any(isinstance(h, RotatingFileHandler) for h in logger.handlers)

    def test_is_idempotent(self, tmp_path: Path) -> None:
        """Re-calling configure() does not duplicate handlers."""
        path = tmp_path / "app.log"
        app_log.configure(path)
        first = len(logging.getLogger(app_log.ROOT_LOGGER_NAME).handlers)
        app_log.configure(path)
        second = len(logging.getLogger(app_log.ROOT_LOGGER_NAME).handlers)
        assert first == second


class TestResolveLogPath:
    """Tests for app_log.resolve_log_path."""

    def test_argument_wins(self, tmp_path: Path) -> None:
        """An explicit argument overrides env and default."""
        path = tmp_path / "custom.log"
        assert app_log.resolve_log_path(path) == path.resolve()

    def test_env_var_used_when_no_argument(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OBCD_LOG_PATH is honored when no argument is supplied."""
        target = tmp_path / "env.log"
        monkeypatch.setenv(app_log.ENV_LOG_PATH, str(target))
        assert app_log.resolve_log_path() == target.resolve()

    def test_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without argument or env, the path falls back to logs/obcd_pilot.log."""
        monkeypatch.delenv(app_log.ENV_LOG_PATH, raising=False)
        resolved = app_log.resolve_log_path()
        assert resolved.name == "obcd_pilot.log"
        assert resolved.parent.name == "logs"


class TestLogDetection:
    """Tests for app_log.log_detection."""

    def test_writes_when_change_detected(
        self, tmp_path: Path, make_detection: Callable[..., Detection]
    ) -> None:
        """AC-08.1: a change-positive detection writes one entry."""
        path = tmp_path / "app.log"
        app_log.configure(path)
        app_log.log_detection(make_detection())
        assert _read_log(path).count("\n") == 1

    def test_skips_when_no_change(
        self, tmp_path: Path, make_detection: Callable[..., Detection]
    ) -> None:
        """Negative detection events are intentionally not logged."""
        path = tmp_path / "app.log"
        app_log.configure(path)
        app_log.log_detection(make_detection(change_detected=False))
        assert _read_log(path) == ""

    def test_entry_contains_required_fields(
        self, tmp_path: Path, make_detection: Callable[..., Detection]
    ) -> None:
        """AC-08.2: entry has timestamp, frame, confidence, model, summary."""
        path = tmp_path / "app.log"
        app_log.configure(path)
        app_log.log_detection(make_detection(frame_id=142, confidence=0.873))
        line = _read_log(path).strip()
        assert "WARNING" in line
        assert app_log.DETECTION_LOGGER_NAME in line
        assert "frame 142" in line
        assert "confidence=0.87" in line
        assert "ConvOBCD" in line
        assert line[:4].isdigit() and line[4] == "-"


class TestPropagationFromChildLoggers:
    """A logger created via getLogger(__name__) reaches the file handler."""

    def test_child_logger_writes_to_file(self, tmp_path: Path) -> None:
        """A child of obcd_pilot propagates to the configured file handler."""
        path = tmp_path / "app.log"
        app_log.configure(path)
        logging.getLogger("obcd_pilot.capture.test").info("hello world")
        assert "hello world" in _read_log(path)


class TestBridge:
    """Tests for the Qt signal bridge."""

    def test_bridge_emits_record_on_change(
        self, tmp_path: Path, make_detection: Callable[..., Detection]
    ) -> None:
        """A change positive detection fires the bridge's record signal."""
        app_log.configure(tmp_path / "app.log")
        captured: list[logging.LogRecord] = []
        app_log.bridge().sig_record.connect(captured.append)
        app_log.log_detection(make_detection())
        assert len(captured) == 1
        assert captured[0].name == app_log.DETECTION_LOGGER_NAME

    def test_bridge_carries_child_logger_records(self, tmp_path: Path) -> None:
        """Child-logger records also reach the bridge via propagation."""
        app_log.configure(tmp_path / "app.log")
        captured: list[logging.LogRecord] = []
        app_log.bridge().sig_record.connect(captured.append)
        logging.getLogger("obcd_pilot.capture.test").info("startup")
        assert any(r.getMessage() == "startup" for r in captured)
