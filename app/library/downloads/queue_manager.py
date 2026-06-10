import functools
import glob
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web

from app.library.config import Config
from app.library.Events import EventBus, Events
from app.library.ItemDTO import Item, ItemDTO
from app.library.log import get_logger
from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.Singleton import Singleton
from app.library.sqlite_store import SqliteStore
from app.library.Utils import calc_download_path

from .core import Download
from .item_adder import add as add_impl
from .monitors import check_for_stale, check_live, cleanup_thumbnails, delete_old_history
from .pool_manager import PoolManager

if TYPE_CHECKING:
    from app.library.DataStore import StoreType

LOG = get_logger()


class DownloadQueue(metaclass=Singleton):
    def __init__(self, config: Config | None = None):
        # Import here to avoid circular import with DataStore
        from app.library.DataStore import DataStore, StoreType

        self.config: Config = config or Config.get_instance()
        "Configuration instance."
        self._notify: EventBus = EventBus.get_instance()
        "Event bus instance."
        self.done = DataStore(type=StoreType.HISTORY, connection=SqliteStore.get_instance(), max_history=self.config.max_history)
        "DataStore for the completed downloads."
        self.queue = DataStore(type=StoreType.QUEUE, connection=SqliteStore.get_instance())
        "DataStore for the download queue."
        self.pool = PoolManager(queue=self, config=self.config)
        "Pool manager for coordinating download execution."

    @staticmethod
    def get_instance(config: Config | None = None) -> "DownloadQueue":
        return DownloadQueue(config=config)

    def attach(self, _: web.Application) -> None:
        Services.get_instance().add("queue", self)

        async def event_handler(_, __):
            await self.initialize()

        self._notify.subscribe(Events.STARTED, event_handler, f"{__class__.__name__}.{__class__.initialize.__name__}")

        Scheduler.get_instance().add(
            timer="* * * * *",
            func=functools.partial(check_for_stale, self),
            id=check_for_stale.__name__,
        )

        Scheduler.get_instance().add(
            timer="* * * * *",
            func=functools.partial(check_live, self),
            id=check_live.__name__,
        )

        Scheduler.get_instance().add(
            timer="10 */1 * * *",
            func=functools.partial(cleanup_thumbnails, self),
            id=cleanup_thumbnails.__name__,
        )

        if self.config.auto_clear_history_days > 0:
            Scheduler.get_instance().add(
                timer="8 */1 * * *",
                func=functools.partial(delete_old_history, self),
                id=delete_old_history.__name__,
            )

        # app.on_shutdown.append(self.on_shutdown)

    async def test(self) -> bool:
        await self.done.test()
        return True

    async def initialize(self) -> None:
        await self.queue.load()
        LOG.info(
            f"Using '{self.config.max_workers}' workers for downloading and '{self.config.max_workers_per_extractor}' per extractor."
        )
        await self.pool.start_pool()

    async def start_items(self, ids: list[str]) -> dict[str, str]:
        """
        Start one or more queued downloads that were added with auto_started=False.

        Args:
            ids (list[str]): List of item IDs to start.

        Returns:
            dict[str, str]: Dictionary of per-ID results and overall status.

        """
        status: dict[str, str] = {"status": "ok"}
        started = False

        for item_id in ids:
            try:
                item: Download = await self.queue.get(key=item_id)
            except KeyError as e:
                status[item_id] = f"not found: {e!s}"
                status["status"] = "error"
                LOG.warning(
                    "Start requested for missing queued download '%s'.", item_id, extra={"download_id": item_id}
                )
                continue

            if item.info.auto_start:
                status[item_id] = "already started"
                continue

            item.info.auto_start = True
            updated: Download = await self.queue.put(item)
            self._notify.emit(Events.ITEM_UPDATED, data=updated.info)
            self._notify.emit(
                Events.ITEM_RESUMED,
                data=item.info,
                title="Download Resumed",
                message=f"Download '{item.info.title}' has been resumed.",
            )
            status[item_id] = "started"
            started = True

        if started:
            self.pool.trigger_download()

        return status

    async def pause_items(self, ids: list[str]) -> dict[str, str]:
        """
        Pause one or more queued downloads that were added with auto_started=True.

        Args:
            ids (list[str]): List of item IDs to pause.

        Returns:
            dict[str, str]: Dictionary of per-ID results and overall status.

        """
        status: dict[str, str] = {"status": "ok"}

        for item_id in ids:
            try:
                item: Download = await self.queue.get(key=item_id)
            except KeyError as e:
                status[item_id] = f"not found: {e!s}"
                status["status"] = "error"
                LOG.warning(
                    "Pause requested for missing queued download '%s'.", item_id, extra={"download_id": item_id}
                )
                continue

            if item.started() or item.is_cancelled():
                status[item_id] = "already started"
                continue

            if item.info.auto_start is False:
                status[item_id] = "not started"
                continue

            item.info.auto_start = False
            updated: Download = await self.queue.put(item)
            self._notify.emit(Events.ITEM_UPDATED, data=updated.info)
            self._notify.emit(
                Events.ITEM_PAUSED,
                data=item.info,
                title="Download Paused",
                message=f"Download '{item.info.title}' has been paused.",
            )
            status[item_id] = "paused"

        return status

    def pause(self, shutdown: bool = False) -> bool:
        """
        Pause the download queue.

        Returns:
            bool: True if the download is paused, False otherwise

        """
        if not self.pool.is_paused():
            self.pool.pause()
            if not shutdown:
                paused_at = datetime.now(tz=UTC).isoformat()
                LOG.warning("Paused the download queue.", extra={"paused_at": paused_at})
            return True

        return False

    def resume(self) -> bool:
        """
        Resume the download queue.

        Returns:
            bool: True if the download is resumed, False otherwise

        """
        if self.pool.is_paused():
            self.pool.resume()
            resumed_at = datetime.now(tz=UTC).isoformat()
            LOG.warning("Resumed the download queue.", extra={"resumed_at": resumed_at})
            return True

        return False

    def is_paused(self) -> bool:
        """
        Check if the download queue is paused.

        Returns:
            bool: True if the download queue is paused, False otherwise

        """
        return self.pool.is_paused()

    async def on_shutdown(self, _: web.Application):
        await self.pool.shutdown()

    async def add(self, item: Item, already: set | None = None, entry: dict | None = None) -> dict[str, str]:
        """
        Add an item to the download queue.

        Args:
            item: Item to be added to the queue
            already: Set of already downloaded items
            entry: Entry associated with the item (if already extracted)

        Returns:
            dict[str, str]: Status dict with "status" and optional "msg" keys

        """
        return await add_impl(queue=self, item=item, already=already, entry=entry)

    async def cancel(self, ids: list[str]) -> dict[str, str]:
        """
        Cancel the download.

        Args:
            ids (list): The list of ids to cancel.

        Returns:
            dict: The status of the operation.

        """
        status: dict[str, str] = {}

        for id in ids:
            try:
                item = await self.queue.get(key=id)
            except KeyError as e:
                status[id] = str(e)
                status["status"] = "error"
                LOG.warning("Cancel requested for missing queued download '%s'.", id, extra={"download_id": id})
                continue

            if item.running():
                LOG.debug(
                    "Cancelling running download '%s'.",
                    item.info.title,
                    extra={
                        "download": {
                            "download_id": id,
                            "item_id": item.info.id,
                            "title": item.info.title,
                            "url": item.info.url,
                        }
                    },
                )
                item.cancel()
                LOG.info(
                    "Cancelled running download '%s'.",
                    item.info.title,
                    extra={
                        "download": {
                            "download_id": id,
                            "item_id": item.info.id,
                            "title": item.info.title,
                            "url": item.info.url,
                        }
                    },
                )
                if not item.is_live:
                    await item.close()
            else:
                await item.close()
                LOG.debug(
                    "Removing cancelled download '%s' from queue.",
                    item.info.title,
                    extra={
                        "download": {
                            "download_id": id,
                            "item_id": item.info.id,
                            "title": item.info.title,
                            "url": item.info.url,
                        }
                    },
                )
                await self.queue.delete(id)
                self._notify.emit(
                    Events.ITEM_CANCELLED,
                    data=item.info,
                    title="Download Cancelled",
                    message=f"Download '{item.info.title}' has been cancelled.",
                )
                item.info.status = "cancelled"
                await self.done.put(item)
                self._notify.emit(
                    Events.ITEM_MOVED,
                    data={"to": "history", "preset": item.info.preset, "item": item.info},
                    title="Download Cancelled",
                    message=f"Download '{item.info.title}' has been cancelled.",
                )
                LOG.info(
                    "Moved cancelled download '%s' from queue to history.",
                    item.info.title,
                    extra={
                        "download": {
                            "download_id": id,
                            "item_id": item.info.id,
                            "title": item.info.title,
                            "url": item.info.url,
                            "status": item.info.status,
                        }
                    },
                )

            status[id] = "ok"

        return status

    async def clear(self, ids: list[str], remove_file: bool = False) -> dict[str, str]:
        """
        Clear the download history.

        Args:
            ids (list): The list of ids to clear.
            remove_file (bool): Only considered if config.remove_files is True.

        Returns:
            dict: The status of the operation.

        """
        status: dict[str, str] = {}
        deleted_ids: list[str] = []

        for id in ids:
            try:
                item: Download = await self.done.get(key=id)
            except KeyError as e:
                status[id] = str(e)
                status["status"] = "error"
                LOG.warning("Delete requested for missing history download '%s'.", id, extra={"download_id": id})
                continue

            removed_files = 0
            filename: str = ""

            if self.config.remove_files is not True:
                remove_file = False

            LOG.debug(
                "Clearing history download '%s'.",
                item.info.title,
                extra={
                    "download": {
                        "download_id": id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "status": item.info.status,
                        "remove_file": remove_file,
                    }
                },
            )

            if remove_file and "finished" == item.info.status and item.info.filename:
                filename = str(item.info.filename)
                if item.info.folder:
                    filename = f"{item.info.folder}/{item.info.filename}"

                try:
                    rf = Path(
                        calc_download_path(
                            base_path=Path(self.config.download_path),
                            folder=filename,
                            create_path=False,
                        )
                    )
                    if rf.is_file() and rf.exists():
                        if rf.stem and rf.suffix:
                            for f in rf.parent.glob(f"{glob.escape(rf.stem)}.*"):
                                if f.is_file() and f.exists() and not f.name.startswith("."):
                                    removed_files += 1
                                    LOG.debug(
                                        "Removing local file '%s' for '%s'.",
                                        f.name,
                                        item.info.title,
                                        extra={
                                            "download": {
                                                "download_id": id,
                                                "item_id": item.info.id,
                                                "title": item.info.title,
                                                "filename": f.name,
                                            }
                                        },
                                    )
                                    f.unlink(missing_ok=True)
                        else:
                            LOG.debug(
                                "Removing local file '%s' for '%s'.",
                                rf.name,
                                item.info.title,
                                extra={
                                    "download": {
                                        "download_id": id,
                                        "item_id": item.info.id,
                                        "title": item.info.title,
                                        "filename": rf.name,
                                    }
                                },
                            )
                            rf.unlink(missing_ok=True)
                            removed_files += 1
                    else:
                        LOG.warning(
                            "Could not remove local file '%s' for '%s' because it was not found.",
                            filename,
                            item.info.title,
                            extra={
                                "download": {
                                    "download_id": id,
                                    "item_id": item.info.id,
                                    "title": item.info.title,
                                    "filename": filename,
                                }
                            },
                        )
                except Exception as e:
                    LOG.exception(
                        "Failed to remove local file '%s' for '%s'.",
                        filename,
                        item.info.title,
                        extra={
                            "download": {
                                "download_id": id,
                                "item_id": item.info.id,
                                "title": item.info.title,
                                "filename": filename,
                                "remove_file": remove_file,
                                "exception_type": type(e).__name__,
                            }
                        },
                    )

            await self.done.delete(id)
            deleted_ids.append(id)

            _status: str = "Removed" if removed_files > 0 else "Cleared"
            self._notify.emit(
                Events.ITEM_DELETED,
                data=item.info,
                title=f"Download {_status}",
                message=f"{_status} '{item.info.title}' from history.",
            )

            LOG.info(
                "Deleted completed download '%s' from history%s.",
                item.info.title,
                f" and removed {removed_files} local file(s)" if removed_files > 0 else "",
                extra={
                    "download": {
                        "download_id": id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "removed_files": removed_files,
                    }
                },
            )
            status[id] = "ok"

        if deleted_ids:
            await self.done._connection.flush()

        return status

    async def clear_bulk(self, ids: list[str], remove_file: bool = False) -> dict[str, int | str]:
        if not ids:
            return {"deleted": 0}

        items = await self.done.get_many_by_ids(ids)
        if not items:
            return {"deleted": 0}

        if self.config.remove_files is not True:
            remove_file = False

        removed_files = 0
        deleted_ids: list[str] = []
        deleted_titles: list[str] = []

        for item_id, item in items:
            filename: str = ""

            LOG.debug(
                "Clearing history download '%s'.",
                item.info.title,
                extra={
                    "download": {
                        "download_id": item_id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "status": item.info.status,
                        "remove_file": remove_file,
                    }
                },
            )

            if remove_file and "finished" == item.info.status and item.info.filename:
                filename = str(item.info.filename)
                if item.info.folder:
                    filename = f"{item.info.folder}/{item.info.filename}"

                try:
                    rf = Path(
                        calc_download_path(
                            base_path=Path(self.config.download_path),
                            folder=filename,
                            create_path=False,
                        )
                    )
                    if rf.is_file() and rf.exists():
                        if rf.stem and rf.suffix:
                            for file_ref in rf.parent.glob(f"{glob.escape(rf.stem)}.*"):
                                if file_ref.is_file() and file_ref.exists() and not file_ref.name.startswith("."):
                                    removed_files += 1
                                    LOG.debug(
                                        "Removing local file '%s' for '%s'.",
                                        file_ref.name,
                                        item.info.title,
                                        extra={
                                            "download": {
                                                "download_id": item_id,
                                                "item_id": item.info.id,
                                                "title": item.info.title,
                                                "filename": file_ref.name,
                                            }
                                        },
                                    )
                                    file_ref.unlink(missing_ok=True)
                        else:
                            LOG.debug(
                                "Removing local file '%s' for '%s'.",
                                rf.name,
                                item.info.title,
                                extra={
                                    "download": {
                                        "download_id": item_id,
                                        "item_id": item.info.id,
                                        "title": item.info.title,
                                        "filename": rf.name,
                                    }
                                },
                            )
                            rf.unlink(missing_ok=True)
                            removed_files += 1
                    else:
                        LOG.warning(
                            "Could not remove local file '%s' for '%s' because it was not found.",
                            filename,
                            item.info.title,
                            extra={
                                "download": {
                                    "download_id": item_id,
                                    "item_id": item.info.id,
                                    "title": item.info.title,
                                    "filename": filename,
                                }
                            },
                        )
                except Exception as e:
                    LOG.exception(
                        "Failed to remove local file '%s' for '%s'.",
                        filename,
                        item.info.title,
                        extra={
                            "download": {
                                "download_id": item_id,
                                "item_id": item.info.id,
                                "title": item.info.title,
                                "filename": filename,
                                "remove_file": remove_file,
                                "exception_type": type(e).__name__,
                            }
                        },
                    )

            deleted_ids.append(item_id)
            deleted_titles.append(item.info.title or item.info.id or item_id)

        deleted_count = await self.done.bulk_delete(deleted_ids)
        if deleted_count < 1:
            return {"deleted": 0}

        title = "History Removed" if removed_files > 0 else "History Cleared"
        message = f"Removed {deleted_count} item{'s' if deleted_count != 1 else ''} from history."
        if removed_files > 0:
            message += f" Also removed {removed_files} local file{'s' if removed_files != 1 else ''}."

        self._notify.emit(
            Events.ITEM_BULK_DELETED,
            data={"ids": deleted_ids, "count": deleted_count},
            title=title,
            message=message,
        )

        summary = ", ".join(deleted_titles[:5])
        if deleted_count > 5:
            summary += ", ..."
        LOG.info(
            "Cleared %s history item(s), including %s.",
            deleted_count,
            summary,
            extra={"deleted_count": deleted_count, "removed_files": removed_files, "titles": deleted_titles[:5]},
        )

        return {"deleted": deleted_count}

    async def clear_by_status(self, status_filter: str, remove_file: bool = False) -> dict[str, int | str]:
        if self.config.remove_files is not True:
            remove_file = False

        if not remove_file:
            deleted_count = await self.done.bulk_delete_by_status(status_filter)
            if deleted_count < 1:
                return {"deleted": 0}

            self._notify.emit(
                Events.ITEM_BULK_DELETED,
                data={"count": deleted_count, "status": status_filter},
                title="History Cleared",
                message=f"Cleared {deleted_count} item{'s' if deleted_count != 1 else ''} from history.",
            )
            LOG.info(
                "Cleared %s history item(s) with status '%s'.",
                deleted_count,
                status_filter,
                extra={"deleted_count": deleted_count, "status_filter": status_filter},
            )
            return {"deleted": deleted_count}

        items = await self.done.get_many_by_status(status_filter)
        return await self.clear_bulk([item_id for item_id, _ in items], remove_file=remove_file)

    async def get(self, mode: str = "all") -> dict[str, list[dict[str, ItemDTO]]]:
        """
        Get the download queue and the download history.

        Args:
            mode (str): The mode to get the items. Supported modes are 'all', 'queue', 'done'.

        Returns:
            dict: The download queue and the download history.

        """
        items = {"queue": {}, "done": {}}
        active = self.pool.get_active_downloads()

        if mode in ("all", "queue"):
            for k, v in await self.queue.saved_items():
                items["queue"][k] = active[k].info if k in active else v

        if mode in ("all", "done"):
            for k, v in await self.done.saved_items():
                items["done"][k] = v

        if mode in ("all", "queue"):
            for k, v in self.queue.items():
                if k not in items["queue"]:
                    items["queue"][k] = active[k].info if k in active else v

        if mode in ("all", "done"):
            for k, v in self.done.items():
                if k in items["done"]:
                    continue

                items["done"][k] = v.info

        return items

    async def get_item(self, **kwargs) -> tuple["StoreType", Download] | tuple[None, None]:
        """
        Get a specific item from the download queue or history.

        Args:
            **kwargs: The key-value pair to search for. Supported keys are 'id', 'url'.

        Returns:
            (StoreType, Download) | None: The requested item if found, otherwise None.

        """
        from app.library.DataStore import StoreType

        if item := await self.queue.get_item(**kwargs):
            return (StoreType.QUEUE, item)

        if item := await self.done.get_item(**kwargs):
            return (StoreType.HISTORY, item)

        return (None, None)
