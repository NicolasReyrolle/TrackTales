"""Logging configuration for TrackTales."""

import atexit
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import TextIO

# Module-level devnull stream cache.  Created on first use and closed on
# interpreter exit via atexit so callers never need to manage its lifetime.
_devnull_stream: TextIO | None = None


def _get_or_create_devnull() -> TextIO:
    """Return a module-level devnull stream, opening it on first call."""
    global _devnull_stream
    if _devnull_stream is None:
        _devnull_stream = open(os.devnull, "w", encoding="utf-8")
        atexit.register(_devnull_stream.close)
    return _devnull_stream


class _ImmediateFlushHandler(logging.handlers.RotatingFileHandler):
    """A RotatingFileHandler that flushes after every emit (for subprocess/reload scenarios)."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record and flush immediately."""
        super().emit(record)
        self.flush()


def ensure_standard_streams() -> None:
    """Ensure stdout/stderr are usable in windowed or frozen executions.

    Uvicorn's default formatter checks ``sys.stderr.isatty()`` during
    startup. In windowed executables, those streams can be ``None``.

    Prefers ``sys.__stdout__``/``sys.__stderr__`` when available to avoid
    creating extra file handles (and to reduce the chance of FD leaks in
    tests that monkeypatch stdout/stderr). Falls back to a module-level
    cached devnull stream (closed on interpreter exit via ``atexit``) only
    when the canonical streams are also ``None``.
    """
    if sys.stdout is None:
        sys.stdout = sys.__stdout__ if sys.__stdout__ is not None else _get_or_create_devnull()
    if sys.stderr is None:
        sys.stderr = sys.__stderr__ if sys.__stderr__ is not None else _get_or_create_devnull()


def setup_logging(log_level: str, enable_file_logging: bool = True) -> None:
    """Configure logging with both console and file handlers.

    Args:
        log_level: Logging level as string (DEBUG, INFO, WARNING, ERROR)
        enable_file_logging: Whether to write logs to a file
            (disabled in dev mode to avoid reload loops)
    """
    # Keep std streams available for formatters that probe TTY support.
    ensure_standard_streams()

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Remove any existing handlers to prevent duplicates and close resources.
    # Keep pytest log capture handlers so caplog continues to work in tests.
    for handler in logger.handlers[:]:
        if handler.__class__.__module__.startswith("_pytest."):
            continue
        try:
            handler.close()
        finally:
            logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler for persistence (in case console is captured)
    if enable_file_logging:
        # Allow overriding the log directory via environment variable
        log_dir_env = os.getenv("TRACKTALES_LOG_DIR")
        log_dir = Path(log_dir_env) if log_dir_env else Path("logs")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = _ImmediateFlushHandler(
                log_dir / "tracktales.log",
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=3,
            )
        except OSError as exc:
            logger.warning(
                "File logging disabled; failed to initialize log file in '%s': %s",
                log_dir,
                exc,
            )
        else:
            file_handler.setLevel(getattr(logging, log_level))
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
