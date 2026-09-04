"""Console + file logging with a single configuration entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_CONFIGURED = False


def get_logger(name: str = "onebigjump") -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> logging.Logger:
    """Idempotently configure the package logger."""
    global _CONFIGURED
    logger = logging.getLogger("onebigjump")
    if _CONFIGURED:
        if log_file is not None:
            _attach_file(logger, log_file)
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_file is not None:
        _attach_file(logger, log_file)
    _CONFIGURED = True
    return logger


def _attach_file(logger: logging.Logger, log_file: Path) -> None:
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    existing = {getattr(h, "baseFilename", None) for h in logger.handlers}
    if str(log_file.resolve()) in existing:
        return
    fh = logging.FileHandler(log_file)
    fh.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(fh)
