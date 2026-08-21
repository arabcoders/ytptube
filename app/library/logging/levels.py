from __future__ import annotations

import logging

from .names import get_logger, get_logger_name

SUPPORTED_LOG_LEVELS: tuple[str, ...] = ("debug", "info", "warning", "error")


def normalize_log_level(level: str) -> str:
    value = level.strip().lower()
    if value not in SUPPORTED_LOG_LEVELS:
        msg = f"Unsupported log level '{level}'."
        raise ValueError(msg)
    return value


def get_runtime_log_level() -> str:
    return logging.getLevelName(logging.getLogger(get_logger_name()).getEffectiveLevel()).lower()


def set_runtime_log_level(level: str) -> str:
    normalized = normalize_log_level(level)
    numeric_level = getattr(logging, normalized.upper(), None)
    if not isinstance(numeric_level, int):
        msg = f"Unsupported log level '{level}'."
        raise ValueError(msg)
    get_logger().setLevel(numeric_level)
    for handler in logging.getLogger().handlers:
        if getattr(handler, "ytptube_managed_json", False):
            handler.setLevel(numeric_level)
    return normalized
