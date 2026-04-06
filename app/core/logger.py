"""Central logger configuration for the project."""

from __future__ import annotations

import io
import logging
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import LOG_DIR

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5


def _get_utf8_stream():
    """Return a UTF-8 console stream on Windows terminals."""
    if hasattr(sys.stdout, "buffer"):
        return io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    return sys.stdout


def get_logger(name: str = "ai_job_agent") -> logging.Logger:
    """Return a configured logger. Same-name loggers are initialized only once."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    console_handler = logging.StreamHandler(_get_utf8_stream())
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    app_file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    app_file_handler.setLevel(logging.DEBUG)
    app_file_handler.setFormatter(formatter)
    logger.addHandler(app_file_handler)

    error_file_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    logger.addHandler(error_file_handler)

    return logger
