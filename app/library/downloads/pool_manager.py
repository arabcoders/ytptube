"""Download pool management - worker coordination and execution."""

import asyncio
import logging
from typing import TYPE_CHECKING

from app.library.Events import EventBus, Events
from app.library.Utils import calc_download_path

from .core import Download
from .utils import get_extractor_limit, handle_task_exception

if TYPE_CHECKING:
    from app.library.config import Config

    from .queue_manager import DownloadQueue

LOG: logging.Logger = logging.getLogger("downloads.pool")


class PoolManager:
    """
    Manages download worker pool and execution.

    Coordinates concurrent downloads with semaphore-based limits:
    - Global worker limit (max_workers)
    - Per-extractor limits (max_workers_per_extractor)
    - Live streams bypass all limits

    Integrates with DownloadQueue for queue access and configuration.
    """

    def __init__(self, queue: "DownloadQueue", config: "Config"):
        self.queue = queue
        self.config = config
        self._notify: EventBus = EventBus.get_instance()

        self.workers = asyncio.Semaphore(config.max_workers)
        "Semaphore to limit the number of concurrent downloads."

        self.paused = asyncio.Event()
        "Event to pause the download queue."

        self.event = asyncio.Event()
        "Event to signal the download queue to start downloading."

        self._active: dict[str, Download] = {}
        "Dictionary of active downloads."

        self.paused.set()

    def is_paused(self) -> bool:
        return not self.paused.is_set()

    def pause(self) -> None:
        if self.paused.is_set():
            self.paused.clear()
            LOG.info("Download pool paused.")

    def resume(self) -> None:
        if not self.paused.is_set():
            self.paused.set()
            LOG.info("Download pool resumed.")

    def trigger_download(self) -> None:
        """Trigger the download pool to check for new items."""
        if self.event:
            self.event.set()

    def get_active_downloads(self) -> dict[str, Download]:
        return self._active.copy()

    def get_active_download(self, download_id: str) -> Download | None:
        return self._active.get(download_id)

    async def start_pool(self) -> None:
        asyncio.create_task(self._download_pool(), name="download_pool")

    async def shutdown(self) -> None:
        if self._active:
            LOG.info(f"Cancelling '{len(self._active)}' active downloads.")
            await self.queue.cancel(list(self._active.keys()))

    async def _download_pool(self) -> None:
        adaptive_sleep = 0.2
        max_sleep = 5.0

        while True:
            while not self.queue.queue.has_downloads():
                LOG.info("Waiting for item to download.")
                await self.event.wait()
                self.event.clear()
                adaptive_sleep = 0.2

            if self.is_paused():
                LOG.warning("Download pool is paused.")
                await self.paused.wait()
                LOG.info("Download pool resumed downloading.")
                adaptive_sleep = 0.2

            items_processed = 0

            for _id, entry in list(self.queue.queue.items()):
                if entry.started() or entry.is_cancelled() or entry.info.auto_start is False:
                    continue

                extractor: str = entry.info.get_extractor() or "unknown"

                # Live downloads bypass all limits.
                if entry.is_live:
                    task: asyncio.Task[None] = asyncio.create_task(
                        self._download_file(_id, entry), name=f"download_live_{extractor}_{_id}"
                    )
                    task.add_done_callback(lambda t: handle_task_exception(t, LOG))
                    items_processed += 1
                else:
                    _limit: asyncio.Semaphore = get_extractor_limit(
                        extractor, self.config.max_workers, self.config.max_workers_per_extractor, LOG
                    )

                    # Skip this item in this iteration if no slots are available.
                    if self.workers.locked() or _limit.locked():
                        continue

                    await self.workers.acquire()
                    await _limit.acquire()

                    task: asyncio.Task[None] = asyncio.create_task(
                        self._download_file(_id, entry), name=f"download_file_{extractor}_{_id}"
                    )

                    def _release(t: asyncio.Task, sem=_limit) -> None:
                        sem.release()
                        self.workers.release()
                        handle_task_exception(t, LOG)

                    task.add_done_callback(_release)
                    items_processed += 1

            # No items could be processed, back off a bit to avoid busy-waiting.
            if 0 == items_processed:
                adaptive_sleep: float = min(adaptive_sleep * 1.5, max_sleep)
                LOG.debug(f"No download slots available. Backing off for {adaptive_sleep:.2f}s before next attempt.")
            else:
                adaptive_sleep = 0.2

            await asyncio.sleep(adaptive_sleep)

    async def _download_file(self, id: str, entry: Download) -> None:
        """
        Download the file.

        Args:
            id: The id of the download
            entry: The download entry

        """
        filePath: str = calc_download_path(base_path=self.config.download_path, folder=entry.info.folder)
        LOG.info(f"Downloading 'id: {entry.id}', 'Title: {entry.info.title}', 'URL: {entry.info.url}' To '{filePath}'.")

        try:
            self._active[entry.info._id] = entry
            await entry.start()

            if entry.info.status not in ("finished", "skip", "cancelled"):
                if not entry.info.error:
                    entry.info.error = f"Download ended with unexpected status '{entry.info.status}'."
                entry.info.status = "error"
        except Exception as e:
            entry.info.status = "error"
            entry.info.error = str(e)
        finally:
            if entry.info._id in self._active:
                self._active.pop(entry.info._id, None)

            await entry.close()

        if await self.queue.queue.exists(key=id):
            LOG.debug(f"Download Task '{id}' is completed. Removing from queue.")
            await self.queue.queue.delete(key=id)

            nTitle: str | None = None
            nMessage: str | None = None

            if entry.is_cancelled() is True:
                nTitle = "Download Cancelled"
                nMessage = f"Cancelled '{entry.info.title}' download."
                self._notify.emit(Events.ITEM_CANCELLED, data=entry.info, title=nTitle, message=nMessage)
                entry.info.status = "cancelled"

            if entry.info.status == "finished" and entry.info.filename:
                nTitle = "Download Completed"
                nMessage = f"Completed '{entry.info.title}' download."
                if entry.info.is_archivable and not entry.info.is_archived:
                    entry.info.is_archived = True

                self._notify.emit(Events.ITEM_COMPLETED, data=entry.info, title=nTitle, message=nMessage)

            await self.queue.done.put(entry)
            self._notify.emit(
                Events.ITEM_MOVED,
                data={"to": "history", "preset": entry.info.preset, "item": entry.info},
                title=nTitle,
                message=nMessage,
            )
        else:
            LOG.warning(f"Download '{id}' not found in queue.")

        if self.event:
            self.event.set()
