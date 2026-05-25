"""Application file logging.

Each module calls logging.getLogger(__name__) and its records propagate to the
dedicated obcd_pilot root logger, where one rotating file handler captures
everything. The same records are republished on a Qt signal so the UI can
tail them live.

Detection events route through log_detection at WARNING level so they surface
as alerts in the viewer.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, Signal

from obcd_pilot.pipeline import Detection

ROOT_LOGGER_NAME = "obcd_pilot"
DETECTION_LOGGER_NAME = f"{ROOT_LOGGER_NAME}.detection"
ENV_LOG_PATH = "OBCD_LOG_PATH"
DEFAULT_LOG_PATH = Path("logs") / "obcd_pilot.log"

_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5
_LOG_FORMAT = "%(asctime)s.%(msecs)03d  %(levelname)-7s  %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class _QtLogBridge(QObject):
    """Republishes log records as a Qt signal for cross thread UI delivery."""

    sig_record = Signal(logging.LogRecord)


class _SignalHandler(logging.Handler):
    """Logging handler that forwards each record onto the Qt bridge."""

    def __init__(self, bridge: _QtLogBridge) -> None:
        """Wrap the bridge that records will be forwarded to."""
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        """Overloaded stdlib method.

        Republish the record on the Qt bridge for cross thread UI delivery.
        """
        self._bridge.sig_record.emit(record)


_bridge: _QtLogBridge | None = None
_active_path: Path | None = None


def bridge() -> _QtLogBridge:
    """Return the Qt bridge singleton. configure() must run first."""
    if _bridge is None:
        raise RuntimeError("app_log.configure() has not been called yet.")
    return _bridge


def current_log_path() -> Path:
    """Return the path that configure() attached the file handler to."""
    if _active_path is None:
        raise RuntimeError("app_log.configure() has not been called yet.")
    return _active_path


def resolve_log_path(override: Path | None = None) -> Path:
    """Pick a log path. Priority: argument, OBCD_LOG_PATH env, then cwd if
    writable (dev mode), then the platform's AppDataLocation (bundled mode).
    """
    if override is not None:
        return override.expanduser().resolve()
    env = os.environ.get(ENV_LOG_PATH)
    if env:
        return Path(env).expanduser().resolve()
    cwd = Path.cwd()
    if os.access(cwd, os.W_OK):
        return (cwd / DEFAULT_LOG_PATH).resolve()
    base = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    )
    return (base / DEFAULT_LOG_PATH).resolve()


def configure(
    log_path: Path | None = None, level: int = logging.INFO
) -> logging.Logger:
    """Attach the rotating file handler and Qt bridge to the app root logger.

    Idempotent so re-entry during tests does not duplicate writes.
    """
    global _bridge, _active_path

    path = resolve_log_path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    _active_path = path

    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(level)
    # Detached from Python's root logger,
    # so basicConfig() cannot hijack us.
    logger.propagate = False

    if _bridge is None:
        _bridge = _QtLogBridge()

    # Drop any stale file handler pointing at a different path so reconfigure
    # to a new location does not duplicate writes across files.
    has_matching_file_handler = False
    for handler in list(logger.handlers):
        if isinstance(handler, RotatingFileHandler):
            if Path(handler.baseFilename) == path:
                has_matching_file_handler = True
            else:
                logger.removeHandler(handler)
                handler.close()

    if not has_matching_file_handler:
        file_handler = RotatingFileHandler(
            path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
            delay=True,
        )
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        logger.addHandler(file_handler)

    if not any(isinstance(h, _SignalHandler) for h in logger.handlers):
        logger.addHandler(_SignalHandler(_bridge))

    return logger


def log_detection(detection: Detection) -> None:
    """Emit a detection entry at WARNING level for change positive frames."""
    if not detection.change_detected:
        return

    logging.getLogger(DETECTION_LOGGER_NAME).warning(
        "Change detected in frame %d (confidence=%.2f, model=%s)",
        detection.frame_id,
        detection.confidence,
        detection.model_name,
    )
