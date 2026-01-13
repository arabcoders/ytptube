"""Status tracking and update processing for downloads."""

import asyncio
import logging
import time
from email.utils import formatdate
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.library.Events import EventBus, Events
from app.library.ffprobe import ffprobe

from .types import StatusDict, Terminator
from .utils import safe_relative_path

if TYPE_CHECKING:
    from multiprocessing import Queue

    from app.library.ItemDTO import ItemDTO


class StatusTracker:
    def __init__(
        self,
        info: "ItemDTO",
        download_id: str,
        download_dir: str,
        temp_path: Path | None,
        status_queue: "Queue[Any]",
        logger: logging.Logger,
        debug: bool = False,
    ):
        """
        Initialize status tracker.

        Args:
            info: Download information object
            download_id: Unique download identifier
            download_dir: Base download directory
            temp_path: Temporary directory for this download
            status_queue: Multiprocessing queue for status updates
            logger: Logger instance
            debug: Enable debug logging

        """
        self.info = info
        self.id = download_id
        self.download_dir = download_dir
        self.temp_path = temp_path
        self.status_queue = status_queue
        self.logger = logger
        self.debug = debug
        self._notify: EventBus = EventBus.get_instance()
        self.tmpfilename: str | None = None
        self.final_update = False
        self.update_task: asyncio.Task | None = None

    async def process_status_update(self, status: StatusDict) -> None:
        """
        Process a single status update from the download subprocess.

        Updates the ItemDTO with progress information, file paths, errors,
        and completion status.

        Args:
            status: Status dictionary from yt-dlp hooks

        """
        if status.get("id") != self.id or len(status) < 2:
            self.logger.warning(f"Received invalid status update. {status}")
            return

        if self.debug:
            self.logger.debug(f"Status Update: _id={self.info._id} status={status}")

        if isinstance(status, str):
            self._notify.emit(Events.ITEM_UPDATED, data=self.info)
            return

        self.tmpfilename = status.get("tmpfilename")

        fl = None
        if "final_name" in status:
            fl = Path(status.get("final_name"))
            self.info.filename = safe_relative_path(fl, Path(self.download_dir), self.temp_path)

            if fl.is_file() and fl.exists():
                self.final_update = True
                self.logger.debug(f"Final file name: '{fl}'.")

                try:
                    self.info.file_size = fl.stat().st_size
                except FileNotFoundError:
                    self.info.file_size = 0

        self.info.status = status.get("status", self.info.status)
        self.info.msg = status.get("msg")

        if "error" == self.info.status and "error" in status:
            self.info.error = status.get("error")
            self._notify.emit(
                Events.LOG_ERROR,
                data=self.info,
                title="Download Error",
                message=f"'{self.info.title}' failed to download. {self.info.error}",
            )

        if "downloaded_bytes" in status and status.get("downloaded_bytes", 0) > 0:
            self.info.downloaded_bytes = status.get("downloaded_bytes")
            total: float | None = status.get("total_bytes") or status.get("total_bytes_estimate")
            if total:
                try:
                    self.info.percent = status["downloaded_bytes"] / total * 100
                except ZeroDivisionError:
                    self.info.percent = 0
                self.info.total_bytes = total

        self.info.speed = status.get("speed")
        self.info.eta = status.get("eta")

        if "finished" == self.info.status and fl and fl.is_file() and fl.exists():
            self.info.file_size = fl.stat().st_size
            self.info.datetime = str(formatdate(time.time()))

            try:
                ff = await ffprobe(str(fl))
                self.info.extras["is_video"] = ff.has_video()
                self.info.extras["is_audio"] = ff.has_audio()
                if (ff.has_video() or ff.has_audio()) and not self.info.extras.get("duration"):
                    self.info.extras["duration"] = int(float(ff.metadata.get("duration", 0.0)))
            except Exception as e:
                self.info.extras["is_video"] = True
                self.info.extras["is_audio"] = True
                self.logger.exception(e)
                self.logger.error(f"Failed to run ffprobe. {e}")

        if not self.final_update or fl:
            self._notify.emit(Events.ITEM_UPDATED, data=self.info)

    async def progress_update(self) -> None:
        """
        Continuous loop that processes status updates from the queue.

        Runs until a Terminator sentinel is received or the task is cancelled.
        """
        while True:
            try:
                self.update_task = asyncio.get_running_loop().run_in_executor(None, self.status_queue.get)
                status = await self.update_task
                if status is None or isinstance(status, Terminator):
                    return
                await self.process_status_update(status)
            except (asyncio.CancelledError, OSError, FileNotFoundError):
                return

    async def drain_queue(self, max_iterations: int = 50) -> None:
        """
        Drain remaining status updates from the queue.

        Called after download completion to ensure all status updates are processed.

        Args:
            max_iterations: Maximum number of items to drain

        """
        self.logger.debug("Draining status queue.")
        try:
            drain_count: int = max_iterations + (
                self.status_queue.qsize() if hasattr(self.status_queue, "qsize") else 5
            )
        except Exception:
            drain_count = max_iterations + 5

        for i in range(drain_count):
            try:
                if self.debug:
                    self.logger.debug(f"({max_iterations}/{i}) Draining the status queue...")
                if self.final_update:
                    if self.debug:
                        self.logger.debug(f"({max_iterations}/{i}) Draining stopped. Final update received.")
                    break
                next_status = self.status_queue.get(timeout=0.1)
                if next_status is None or isinstance(next_status, Terminator):
                    continue
                await self.process_status_update(next_status)
            except Exception as e:
                self.logger.warning(f"Error processing status update during drain: {e}")
                continue

    def cancel_update_task(self) -> None:
        """Cancel the progress update task if it's running."""
        try:
            if self.update_task and not self.update_task.done():
                self.update_task.cancel()
        except Exception as e:
            self.logger.error(f"Failed to cancel update task. {e}")

    def put_terminator(self) -> None:
        """Put a terminator sentinel in the status queue."""
        if self.status_queue:
            self.status_queue.put(Terminator())
