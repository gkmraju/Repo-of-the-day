"""
services/logger.py — Loguru-based structured logging configuration.

Call `setup_logger()` once at startup.  Import `logger` anywhere else.
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger as logger  # explicit re-export for type checkers


def setup_logger(log_dir: str = "logs", level: str = "INFO") -> None:
    """Configure Loguru sinks: stderr (coloured) + rotating file."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Remove the default handler
    logger.remove()

    # ── Coloured stderr ────────────────────────────────────────────────────
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        backtrace=True,
        diagnose=True,
    )

    # ── Rotating file ──────────────────────────────────────────────────────
    logger.add(
        log_path / "repo_of_the_day_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",      # New file every midnight
        retention="7 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} — {message}",
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
    )

    logger.info("Logger initialised — level={}", level)


__all__ = ["logger", "setup_logger"]
