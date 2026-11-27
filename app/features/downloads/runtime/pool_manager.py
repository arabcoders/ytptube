"""Download pool management - worker coordination and execution."""

import asyncio
from collections import Counter
from typing import TYPE_CHECKING

from app.library.Events import EventBus, Events
from app.library.logging import get_logger
from app.library.Utils import calc_download_path

from .core import Download
from .utils import get_extractor_limit, handle_task_exception

if TYPE_CHECKING:
    from app.library.config import Config

    from .queue_manager import DownloadQueue

LOG = get_logger()


class PoolManager:
    """
    Manages download worker pool and execution.

    Coordinates concurrent downloads with worker limits:
    - Global worker limit (max_workers)
    - Per-extractor limits (max_workers_per_extractor)
    - Optional per-preset limits across extractors
    - Live streams and force-started downloads bypass all limits

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
        self._requeue: dict[str, asyncio.Task[None] | None] = {}

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

    def is_requeueing(self, id: str) -> bool:
        return id in self._requeue

    def requeue_active(self, id: str) -> bool:
        if (entry := self._active.get(id)) is None:
            return False

        if id not in self._requeue:
            self._requeue[id] = (
                asyncio.create_task(self._stop_for_requeue(id, entry), name=f"requeue-{id}")
                if entry.running()
                else None
            )
        return True

    async def _stop_for_requeue(self, id: str, entry: Download) -> None:
        try:
            if await asyncio.to_thread(entry.cancel) or not entry.running():
                return
        except Exception:
            LOG.exception("Failed to stop download '%s' for requeue.", id)

        self._requeue.pop(id, None)
        self._notify.emit(
            Events.LOG_ERROR,
            data={"download_id": id},
            title="Requeue Failed",
            message=f"Could not stop '{entry.info.title}' to requeue it.",
        )

    async def start_pool(self) -> None:
        asyncio.create_task(self._download_pool(), name="download_pool")

    async def shutdown(self) -> None:
        if self._active:
            LOG.info(
                "Cancelling active downloads (%s item(s)).",
                len(self._active),
                extra={"active_count": len(self._active), "download_ids": list(self._active)},
            )
            await self.queue.cancel(list(self._active.keys()))

    async def _download_pool(self) -> None:
        adaptive_sleep = 0.2
        max_sleep = 5.0
        preset_workers: Counter[int] = Counter()

        while True:
            while not self.queue.queue.has_downloads():
                LOG.info("Waiting for queued downloads.")
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

                # Live and explicitly forced downloads bypass worker limits, but
                # still wait above for the global queue pause to be released.
                if entry.is_live or entry.info.force_start:
                    if entry.info.force_start:
                        entry.info.force_start = False
                        await self.queue.queue.put(entry)
                    task: asyncio.Task[None] = asyncio.create_task(
                        self._download_file(_id, entry), name=f"download_hot_{extractor}_{_id}"
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

                    preset = entry.info.get_preset()
                    preset_id = preset.id if preset else None
                    cap = preset.max_workers if preset else 0
                    if preset_id is not None and cap and preset_workers[preset_id] >= cap:
                        continue

                    await self.workers.acquire()
                    await _limit.acquire()
                    # Count uncapped jobs too, so a cap added mid-download includes them.
                    if preset_id is not None:
                        preset_workers[preset_id] += 1

                    task: asyncio.Task[None] = asyncio.create_task(
                        self._download_file(_id, entry), name=f"download_file_{extractor}_{_id}"
                    )

                    def _release(
                        t: asyncio.Task[None],
                        sem: asyncio.Semaphore = _limit,
                        preset_id: int | None = preset_id,
                    ) -> None:
                        sem.release()
                        self.workers.release()
                        if preset_id is not None:
                            preset_workers[preset_id] -= 1
                            if not preset_workers[preset_id]:
                                del preset_workers[preset_id]
                        handle_task_exception(t, LOG)

                    task.add_done_callback(_release)
                    items_processed += 1

            # No items could be processed, back off a bit to avoid busy-waiting.
            if 0 == items_processed:
                adaptive_sleep: float = min(adaptive_sleep * 1.5, max_sleep)
                LOG.debug(
                    "No download slots available; backing off for %.2f seconds.",
                    adaptive_sleep,
                    extra={"backoff_s": round(adaptive_sleep, 2), "active_count": len(self._active)},
                )
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
        if not entry.info.auto_start or id in self._active:
            return

        filePath: str = calc_download_path(base_path=self.config.download_path, folder=entry.info.folder)
        LOG.info(
            "Started download for '%s' to '%s'.",
            entry.info.title,
            filePath,
            extra={
                "download": {
                    "download_id": entry.id,
                    "item_id": entry.info.id,
                    "title": entry.info.title,
                    "url": entry.info.url,
                    "download_dir": filePath,
                    "preset": entry.info.preset,
                    "is_live": entry.is_live,
                }
            },
        )

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
            try:
                # The stop request can still be using the process handle when the worker exits.
                if stop := self._requeue.get(id):
                    await stop
                await entry.close()
            finally:
                self._active.pop(id, None)
                requeue = id in self._requeue
                self._requeue.pop(id, None)

        if await self.queue.queue.exists(key=id):
            finished = entry.info.status == "finished" and bool(entry.info.filename)
            if requeue and not finished:
                await self.queue.finish_requeue(entry)
                return

            LOG.debug(
                "Removing completed download '%s' from queue.",
                entry.info.title,
                extra={
                    "download": {
                        "download_id": id,
                        "item_id": entry.info.id,
                        "title": entry.info.title,
                        "status": entry.info.status,
                    }
                },
            )
            await self.queue.queue.delete(key=id)

            nTitle: str | None = None
            nMessage: str | None = None
            keep_file = finished and (entry.is_live or requeue)
            if not keep_file and entry.is_cancelled() is True:
                nTitle = "Download Cancelled"
                nMessage = f"Cancelled '{entry.info.title}' download."
                self._notify.emit(Events.ITEM_CANCELLED, data=entry.info, title=nTitle, message=nMessage)
                entry.info.status = "cancelled"
            elif finished:
                nTitle = "Download Completed"
                nMessage = f"Completed '{entry.info.title}' download."
                if entry.info.is_archivable and not entry.info.is_archived:
                    entry.info.is_archived = True

                self._notify.emit(Events.ITEM_COMPLETED, data=entry.info, title=nTitle, message=nMessage)

            await self.queue.done.put(entry)
            self._notify.emit(
                Events.ITEM_MOVED,
                data={"from": "queue", "to": "history", "preset": entry.info.preset, "item": entry.info},
                title=nTitle,
                message=nMessage,
            )
            if requeue:
                await self.queue.finish_requeue(entry, keep_history=True)
        else:
            LOG.warning(
                "Completed download '%s' was not found in the queue.",
                entry.info.title or id,
                extra={"download_id": id, "title": entry.info.title},
            )

        if self.event:
            self.event.set()
