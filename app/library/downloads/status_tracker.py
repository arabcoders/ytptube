"""Status tracking and update processing for downloads."""

import asyncio
import logging
import queue
import time
from email.utils import formatdate
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.library.Events import EventBus, Events

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
        self._terminator_sent: bool = False
        self._candidate_filepath: Path | None = None
        self.update_task: asyncio.Task | None = None
        self._last_progress_time: float = 0.0
        self._pending_progress: bool = False
        self._progress_interval: float = 0.5

    def _progress_payload(self) -> dict:
        return {
            "_id": self.info._id,
            "status": self.info.status,
            "percent": self.info.percent,
            "speed": self.info.speed,
            "eta": self.info.eta,
            "downloaded_bytes": self.info.downloaded_bytes,
            "total_bytes": self.info.total_bytes,
            "msg": self.info.msg,
        }

    def _emit_progress(self) -> None:
        now = time.monotonic()
        if (now - self._last_progress_time) >= self._progress_interval:
            self._notify.emit(Events.ITEM_PROGRESS, data=self._progress_payload())
            self._last_progress_time = now
            self._pending_progress = False
        else:
            self._pending_progress = True

    def _flush_progress(self) -> None:
        if self._pending_progress:
            self._notify.emit(Events.ITEM_PROGRESS, data=self._progress_payload())
            self._pending_progress = False
            self._last_progress_time = time.monotonic()

    async def _finalize_file(self, filepath: Path) -> None:
        """
        Set filename, file_size, and run ffprobe on completed file.

        Args:
            filepath: Path to the finalized download file

        """
        self.info.datetime = str(formatdate(time.time()))
        self.info.filename = safe_relative_path(filepath, Path(self.download_dir))
        self.final_update = True
        self.logger.debug(
            "Final download file for '%s' is '%s'.",
            self.info.title,
            filepath,
            extra={
                "download": {
                    "download_id": self.id,
                    "item_id": self.info.id,
                    "title": self.info.title,
                    "file_path": str(filepath),
                }
            },
        )
        try:
            filepath.relative_to(self.download_dir)
        except ValueError:
            self.logger.warning(
                "Final file '%s' for '%s' is outside download directory '%s'.",
                filepath,
                self.info.title,
                self.download_dir,
                extra={
                    "download": {
                        "download_id": self.id,
                        "item_id": self.info.id,
                        "title": self.info.title,
                        "file_path": str(filepath),
                        "download_dir": self.download_dir,
                    }
                },
            )
            self.info.filename = None
            return

        if filepath.is_file() and filepath.exists():
            try:
                self.info.file_size = filepath.stat().st_size
            except FileNotFoundError:
                self.info.file_size = 0

            try:
                from app.features.streaming.library.ffprobe import ffprobe

                ff = await ffprobe(filepath)
                self.info.extras["is_video"] = ff.has_video()
                self.info.extras["is_audio"] = ff.has_audio()
                if ff.has_video() or ff.has_audio():
                    self.info.extras["duration"] = int(
                        float(ff.metadata.get("duration", self.info.extras.get("duration", 0.0)))
                    )
            except Exception as e:
                self.info.extras["is_video"] = True
                self.info.extras["is_audio"] = True
                self.logger.exception(
                    "Failed to inspect completed file '%s' with ffprobe.",
                    filepath,
                    extra={
                        "download": {
                            "download_id": self.id,
                            "item_id": self.info.id,
                            "title": self.info.title,
                            "file_path": str(filepath),
                            "exception_type": type(e).__name__,
                        }
                    },
                )

    async def process_status_update(self, status: StatusDict) -> None:
        """
        Process a single status update from the download subprocess.

        Updates the ItemDTO with progress information, file paths, errors,
        and completion status.

        Args:
            status: Status dictionary from yt-dlp hooks

        """
        if self.final_update:
            return

        if status.get("id") != self.id or len(status) < 2:
            self.logger.warning(
                "Received invalid status update for '%s'.",
                self.info.title,
                extra={
                    "download": {
                        "download_id": self.id,
                        "item_id": self.info.id,
                        "title": self.info.title,
                        "status": status,
                    }
                },
            )
            return

        if self.debug:
            self.logger.debug(
                "Received a download status update for '%s'.",
                self.info.title,
                extra={
                    "download": {
                        "download_id": self.id,
                        "item_id": self.info.id,
                        "title": self.info.title,
                        "status": status,
                    }
                },
            )

        if isinstance(status, str):
            self._notify.emit(Events.ITEM_UPDATED, data=self.info)
            return

        self.tmpfilename = status.get("tmpfilename")

        old_status = self.info.status
        self.info.status = status.get("status", self.info.status)
        if "download_skipped" in status:
            self.info.download_skipped = bool(status.get("download_skipped"))
        self.info.msg = status.get("msg")
        self.info.postprocessor = status.get("postprocessor", None)

        if filepath := status.get("filepath"):
            self._candidate_filepath = Path(filepath)

        if self.info.status == "error" and "error" in status:
            self.info.error = status.get("error")
            if self._candidate_filepath and self._candidate_filepath.exists():
                self.logger.debug(
                    "Cleaning up partial file '%s' for '%s'.",
                    self._candidate_filepath,
                    self.info.title,
                    extra={
                        "download": {
                            "download_id": self.id,
                            "item_id": self.info.id,
                            "title": self.info.title,
                            "file_path": str(self._candidate_filepath),
                        }
                    },
                )
                await self._finalize_file(self._candidate_filepath)

            self._notify.emit(
                Events.LOG_ERROR,
                data=self.info,
                title="Download Error",
                message=f"'{self.info.title}' failed to download. {self.info.error}",
            )
        elif "downloaded_bytes" in status and status.get("downloaded_bytes", 0) > 0:
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

        if final_name := status.get("final_name", None):
            self._candidate_filepath = None
            await self._finalize_file(Path(final_name))
            self.info.status = "finished"

        if self.info.status != old_status or self.final_update:
            self._flush_progress()
            self._notify.emit(Events.ITEM_UPDATED, data=self.info)
        else:
            self._emit_progress()

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
                    self._flush_progress()
                    return
                await self.process_status_update(status)
            except (asyncio.CancelledError, OSError, FileNotFoundError, EOFError, BrokenPipeError, ConnectionError):
                self._flush_progress()
                return

    async def drain_queue(self, max_iterations: int = 50) -> None:
        """
        Drain remaining status updates from the queue.

        Called after download completion to ensure all status updates are processed.

        Args:
            max_iterations: Maximum number of items to drain

        """
        try:
            drain_count: int = max_iterations + (
                self.status_queue.qsize() if hasattr(self.status_queue, "qsize") else 5
            )
        except Exception:
            drain_count = max_iterations + 5

        for i in range(drain_count):
            if self.final_update:
                self.logger.info(
                    "Stopped draining status queue for '%s' after final update.",
                    self.info.title,
                    extra={
                        "download": {
                            "download_id": self.id,
                            "item_id": self.info.id,
                            "title": self.info.title,
                            "max_iterations": max_iterations,
                            "iteration": i,
                        }
                    },
                )
                break

            try:
                next_status = self.status_queue.get(timeout=0.1)
                if next_status is None or isinstance(next_status, Terminator):
                    continue
                await self.process_status_update(next_status)
            except (queue.Empty, BrokenPipeError, ConnectionRefusedError, EOFError, OSError):
                continue

        self._flush_progress()

    def cancel_update_task(self) -> None:
        """Cancel the progress update task if it's running."""
        try:
            if self.update_task and not self.update_task.done():
                self.update_task.cancel()
        except Exception as e:
            self.logger.exception(
                "Failed to cancel the progress update task for '%s' because %s.",
                self.info.title,
                e,
                extra={
                    "download": {
                        "download_id": self.id,
                        "item_id": self.info.id,
                        "title": self.info.title,
                        "exception_type": type(e).__name__,
                    }
                },
            )

    def put_terminator(self) -> None:
        """Put a terminator sentinel in the status queue."""
        if not self.status_queue or self._terminator_sent:
            return
        try:
            self.status_queue.put(Terminator())
            self._terminator_sent = True
        except (BrokenPipeError, ConnectionRefusedError, ConnectionResetError, EOFError, OSError):
            if self.debug:
                self.logger.debug("Status queue closed, could not send terminator.")
