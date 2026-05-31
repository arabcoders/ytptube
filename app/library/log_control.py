from __future__ import annotations

import logging

from app.library.log import get_logger, get_logger_name

SUPPORTED_LOG_LEVELS: tuple[str, ...] = ("debug", "info", "warning", "error")


def normalize_log_level(level: str) -> str:
    value: str = level.strip().lower()
    if value not in SUPPORTED_LOG_LEVELS:
        msg: str = f"Unsupported log level '{level}'."
        raise ValueError(msg)

    return value


def get_runtime_log_level() -> str:
    return logging.getLevelName(logging.getLogger(get_logger_name()).getEffectiveLevel()).lower()


def set_runtime_log_level(level: str) -> str:
    normalized: str = normalize_log_level(level)
    numeric_level: int | None = getattr(logging, normalized.upper(), None)
    if not isinstance(numeric_level, int):
        msg: str = f"Unsupported log level '{level}'."
        raise ValueError(msg)

    for _logger in (get_logger(),):
        _logger.setLevel(numeric_level)

    return normalized
