"""Logging configuration (RF-25, RNF-07).

Structured logging to console and to a rotating file. The format includes a
UTC timestamp, level, logger name, and message in key=value style to ease
later analysis. The file lives in the user's data directory.
"""

from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir

from vigia_eew.config import APP_NAME, LoggingCfg

_FORMAT = "%(asctime)sZ level=%(levelname)s logger=%(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class _UTCFormatter(logging.Formatter):
    """Formatter that emits timestamps in UTC (consistent with the data model)."""

    converter = staticmethod(time.gmtime)


def default_log_path(file_name: str) -> Path:
    """Returns the log file path in the user's log directory."""
    directory = Path(user_log_dir(APP_NAME))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / file_name


def configure_logging(cfg: LoggingCfg | None = None, *, to_file: bool = True) -> logging.Logger:
    """Configures the agent's root logger.

    Args:
        cfg: logging parameters (level, file, rotation). If None, defaults are used.
        to_file: if False, only logs to console (useful in tests).

    Returns:
        The package's root logger (`vigia_eew`).
    """
    cfg = cfg or LoggingCfg()
    level = getattr(logging, cfg.level.upper(), logging.INFO)

    logger = logging.getLogger("vigia_eew")
    logger.setLevel(level)
    logger.handlers.clear()  # idempotent: avoids duplicate handlers on reconfiguration
    logger.propagate = False

    formatter = _UTCFormatter(_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if to_file:
        path = default_log_path(cfg.file)
        file_handler = RotatingFileHandler(
            path, maxBytes=cfg.max_bytes, backupCount=cfg.backups, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.debug("logging_configured path=%s", path)

    return logger
