from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from .formatter import JsonLogFormatter

if TYPE_CHECKING:
    from collections.abc import Iterable

MANAGED_HANDLER_ATTRIBUTE = "ytptube_managed_json"


def setup_logging(
    level: str,
    log_path: Path | str | None = None,
    third_party_levels: Iterable[tuple[str, int]] = (),
) -> None:
    numeric_level = getattr(logging, level.strip().upper(), None)
    if not isinstance(numeric_level, int):
        msg = f"Unsupported log level '{level}'."
        raise ValueError(msg)

    try:
        import coloredlogs

        coloredlogs.install(
            level=numeric_level,
            fmt="%(asctime)s [%(name)s] [%(levelname)-5.5s] %(message)s",
            datefmt="%H:%M:%S",
            encoding="utf-8",
        )
    except Exception:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s [%(name)s] [%(levelname)-5.5s] %(message)s",
            datefmt="%H:%M:%S",
        )

    root = logging.getLogger()
    managed = [handler for handler in root.handlers if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False)]
    if log_path is not None:
        path = Path(log_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = next((item for item in managed if Path(getattr(item, "baseFilename", "")) == path), None)
        if handler is None:
            handler = TimedRotatingFileHandler(path, when="midnight", backupCount=3, encoding="utf-8")
            setattr(handler, MANAGED_HANDLER_ATTRIBUTE, True)
            handler.setFormatter(JsonLogFormatter())
            root.addHandler(handler)
        for item in managed:
            if item is not handler:
                root.removeHandler(item)
                item.close()
        handler.setLevel(numeric_level)
    else:
        for handler in managed:
            root.removeHandler(handler)
            handler.close()

    for logger_name, logger_level in third_party_levels:
        logging.getLogger(logger_name).setLevel(logger_level)
