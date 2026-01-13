"""Hook handlers for download progress and postprocessing events."""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .utils import DEBUG_MESSAGE_PREFIXES, YTDLP_PROGRESS_FIELDS, create_debug_safe_dict

if TYPE_CHECKING:
    from multiprocessing import Queue


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
                self.logger.debug(f"PG Hook: {d_safe}")
            except Exception as e:
                self.logger.debug(f"PG Hook: Error creating debug info: {e}")

        self.status_queue.put(
            {
                "id": self.id,
                "action": "progress",
                **{k: v for k, v in data.items() if k in YTDLP_PROGRESS_FIELDS},
            }
        )

    def postprocessor_hook(self, data: dict[str, Any]) -> None:
        if self.debug:
            try:
                d_safe = create_debug_safe_dict(data)
                d_safe["postprocessor"] = data.get("postprocessor")
                self.logger.debug(f"PP Hook: {d_safe}")
            except Exception as e:
                self.logger.debug(f"PP Hook: Error creating debug info: {e}")

        if "MoveFiles" == data.get("postprocessor") and "finished" == data.get("status"):
            if "__finaldir" in data.get("info_dict", {}) and "filepath" in data.get("info_dict", {}):
                filename = str(Path(data["info_dict"]["__finaldir"]) / Path(data["info_dict"]["filepath"]).name)
            else:
                filename: str | None = data.get("info_dict", {}).get("filepath", data.get("filename"))

            self.logger.debug(f"Final filename: '{filename}'.")
            self.status_queue.put({"id": self.id, "action": "moved", "status": "finished", "final_name": filename})
            return

        dataDict = {k: v for k, v in data.items() if k in YTDLP_PROGRESS_FIELDS}
        self.status_queue.put({"id": self.id, "action": "postprocessing", **dataDict, "status": "postprocessing"})

    def post_hook(self, filename: str | None = None) -> None:
        if not filename:
            return

        self.status_queue.put({"id": self.id, "filename": filename})


class NestedLogger:
    """
    Logger adapter for yt-dlp that adjusts log levels based on message prefixes.

    yt-dlp logs everything through a custom logger. This adapter maps certain
    message types to appropriate log levels and strips redundant prefixes.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self.logger: logging.Logger = logger

    def debug(self, msg: str) -> None:
        levelno: int = logging.DEBUG if any(msg.startswith(x) for x in DEBUG_MESSAGE_PREFIXES) else logging.INFO
        self.logger.log(level=levelno, msg=re.sub(r"^\[(debug|info)\] ", "", msg, flags=re.IGNORECASE))

    def error(self, msg: str) -> None:
        """Log an error message."""
        self.logger.error(msg)

    def warning(self, msg: str) -> None:
        """Log a warning message."""
        self.logger.warning(msg)
