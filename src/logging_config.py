"""Logging configuration for TrackTales."""

import logging
import logging.handlers
import os
import sys
from pathlib import Path


class _ImmediateFlushHandler(logging.handlers.RotatingFileHandler):
    """A RotatingFileHandler that flushes after every emit (for subprocess/reload scenarios)."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record and flush immediately."""
        super().emit(record)
        self.flush()


def setup_logging(log_level: str, enable_file_logging: bool = True) -> None:
    """Configure logging with both console and file handlers.

    Args:
        log_level: Logging level as string (DEBUG, INFO, WARNING, ERROR)
        enable_file_logging: Whether to write logs to a file
            (disabled in dev mode to avoid reload loops)
    """
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

