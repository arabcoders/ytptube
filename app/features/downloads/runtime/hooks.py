"""Hook handlers for download progress and postprocessing events."""

import logging
import re
from collections import deque
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from .utils import DEBUG_MESSAGE_PREFIXES, YTDLP_PROGRESS_FIELDS, create_debug_safe_dict

if TYPE_CHECKING:
    from multiprocessing import Queue

_MAX_WARNINGS = 5
_MAX_FAILURE_CHARS = 2000
_MAX_WARNING_CHARS: int = (_MAX_FAILURE_CHARS - (_MAX_WARNINGS - 1)) // _MAX_WARNINGS
_REPORT_PREFIX: re.Pattern[str] = re.compile(r"^(?:ERROR|WARNING):\s*", re.IGNORECASE)


def _report_body(message: str) -> str:
    return _REPORT_PREFIX.sub("", message).strip()


class HookHandlers:
    """Manages yt-dlp hook callbacks for progress tracking and postprocessing."""

    def __init__(self, download_id: str, status_queue: "Queue[Any]", logger: logging.Logger, debug: bool = False):
        """
        Initialize hook handlers.

        Args:
            download_id: Unique identifier for the download
            status_queue: Multiprocessing queue for status updates
            logger: Logger instance for this download
            debug: Whether to enable debug logging

        """
        self.id = download_id
        self.status_queue = status_queue
        self.logger = logger
        self.debug = debug

    def progress_hook(self, data: dict[str, Any]) -> None:
        if self.debug:
            try:
                d_safe = create_debug_safe_dict(data)
                self.logger.debug(
                    "Received a yt-dlp progress update for download '%s'.",
                    self.id,
                    extra={"download": {"download_id": self.id, "hook": "progress", "status": d_safe}},
                )
            except Exception as e:
                self.logger.exception(
                    "Failed to create progress hook debug info for download '%s'.",
                    self.id,
                    extra={
                        "download": {"download_id": self.id, "hook": "progress", "exception_type": type(e).__name__}
                    },
                )

        self.status_queue.put(
            {
                "id": self.id,
                "action": "progress",
                **{k: v for k, v in data.items() if k in YTDLP_PROGRESS_FIELDS},
            }
        )

    def postprocessor_hook(self, data: dict[str, Any]) -> None:
        info_dict = data.get("info_dict", {})
        filepath = info_dict.get("filepath")

        status: dict[str, Any] = {
            "id": self.id,
            "action": "postprocessing",
            **{k: v for k, v in data.items() if k in YTDLP_PROGRESS_FIELDS},
            "status": "postprocessing",
        }
        if filepath:
            status["filepath"] = filepath

        if self.debug:
            try:
                d_safe = create_debug_safe_dict(data)
                d_safe["postprocessor"] = data.get("postprocessor")
                self.logger.debug(
                    "Received a yt-dlp post-processing update for download '%s'.",
                    self.id,
                    extra={"download": {"download_id": self.id, "hook": "postprocessor", "status": d_safe}},
                )
            except Exception as e:
                self.logger.exception(
                    "Failed to create postprocessor hook debug info for download '%s'.",
                    self.id,
                    extra={
                        "download": {
                            "download_id": self.id,
                            "hook": "postprocessor",
                            "exception_type": type(e).__name__,
                        }
                    },
                )

        self.status_queue.put(status)

    def post_hook(self, filename: str) -> None:
        self.status_queue.put({"id": self.id, "status": "finished", "final_name": filename})


class NestedLogger:
    """
    Logger adapter for yt-dlp that adjusts log levels based on message prefixes.

    yt-dlp logs everything through a custom logger. This adapter maps certain
    message types to appropriate log levels and strips redundant prefixes.
    """

    def __init__(self, logger: logging.Logger, warnings: Iterable[str] = ()) -> None:
        self.logger: logging.Logger = logger
        self._warnings: deque[str] = deque(maxlen=_MAX_WARNINGS)
        self.retain(warnings)

    def _retain(self, msg: str) -> None:
        warning = str(msg).strip()[:_MAX_WARNING_CHARS]
        if warning and not any(_report_body(item) == _report_body(warning) for item in self._warnings):
            self._warnings.append(warning)

    def retain(self, warnings: Iterable[str]) -> None:
        for warning in warnings:
            self._retain(warning)

    def failure_message(self, error: str = "", filter_out: Iterable[str] = ()) -> str:
        error = error.strip()[:_MAX_FAILURE_CHARS]
        error_body: str = _report_body(error)
        filtered = {_report_body(message) for message in filter_out}
        warnings: list[str] = [
            warning
            for warning in self._warnings
            if _report_body(warning) != error_body and _report_body(warning) not in filtered
        ]
        remaining: int = _MAX_FAILURE_CHARS - len(error) - (1 if error and warnings else 0)
        selected: list[str] = []

        for warning in reversed(warnings):
            size: int = len(warning) + (1 if selected else 0)
            if size > remaining:
                continue
            selected.append(warning)
            remaining -= size

        lines: list[str] = [*reversed(selected)]
        if error:
            lines.append(error)
        return "\n".join(lines)

    def debug(self, msg: str) -> None:
        levelno: int = logging.DEBUG if any(msg.startswith(x) for x in DEBUG_MESSAGE_PREFIXES) else logging.INFO
        self.logger.log(level=levelno, msg=re.sub(r"^\[(debug|info)\] ", "", msg, flags=re.IGNORECASE))

    def error(self, msg: str) -> None:
        """Log an error message."""
        self.logger.error(msg)

    def warning(self, msg: str) -> None:
        """Log a warning message."""
        self._retain(msg)
        self.logger.warning(msg)
