from __future__ import annotations

import logging
from typing import Literal

APP_LOGGER_NAME = "ytptube"
HTTP_LOGGER_NAME = "http_api"

LoggerKind = Literal["app", "http"]


def get_logger(kind: LoggerKind = "app") -> logging.Logger:
    return logging.getLogger(HTTP_LOGGER_NAME if kind == "http" else APP_LOGGER_NAME)
