import asyncio
import functools
import glob
import logging
import os
import time
import traceback
import uuid
from datetime import UTC, datetime, timedelta
from email.utils import formatdate
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING, Any

import yt_dlp.utils
from aiohttp import web

from .ag_utils import ag
from .conditions import Conditions
from .config import Config
from .DataStore import DataStore, StoreType
from .Download import Download
from .Events import EventBus, Events
from .ItemDTO import Item, ItemDTO
from .Presets import Presets
from .Scheduler import Scheduler
from .Singleton import Singleton
from .Utils import (
    archive_add,
    arg_converter,
    calc_download_path,
    create_cookies_file,
    dt_delta,
    extract_info,
    extract_ytdlp_logs,
    merge_dict,
    str_to_dt,
    ytdlp_reject,
)

if TYPE_CHECKING:
    from app.library.Presets import Preset

LOG: logging.Logger = logging.getLogger("DownloadQueue")


class DownloadQueue(metaclass=Singleton):
    """
    DownloadQueue class is a singleton class that manages the download queue and the download history.
    """

    def __init__(self, connection: Connection, config: Config | None = None):
        self.config: Config = config or Config.get_instance()
        "Configuration instance."
        self._notify: EventBus = EventBus.get_instance()
        "Event bus instance."
        self.done = DataStore(type=StoreType.HISTORY, connection=connection)
        "DataStore for the completed downloads."
        self.queue = DataStore(type=StoreType.QUEUE, connection=connection)
        "DataStore for the download queue."
        self.workers = asyncio.Semaphore(self.config.max_workers)
        "Semaphore to limit the number of concurrent downloads."
        self.processors = asyncio.Semaphore(self.config.playlist_items_concurrency)
        "Semaphore to limit the number of concurrent processors."
        self.limits: dict[str, asyncio.Semaphore] = {}
        "Per-extractor semaphores to limit concurrent downloads per extractor."
        self.paused = asyncio.Event()
        "Event to pause the download queue."
        self.event = asyncio.Event()
        "Event to signal the download queue to start downloading."
        self._active: dict[str, Download] = {}
        """Dictionary of active downloads."""

        self.done.load()
        self.queue.load()
        self.paused.set()

    @staticmethod
    def get_instance() -> "DownloadQueue":
        """
        Get the instance of the DownloadQueue.

        Returns:
            DownloadQueue: The instance of the DownloadQueue

        """
        return DownloadQueue()

    def _get_limit(self, extractor: str) -> asyncio.Semaphore:
        """
        Get or create a semaphore for the given extractor.

        Args:
            extractor (str): The extractor name.

        Returns:
            asyncio.Semaphore: The semaphore for the extractor.

        """
        if extractor not in self.limits:
            env_limit: str | None = os.environ.get(f"YTP_MAX_WORKERS_FOR_{extractor.upper()}")

            # Determine effective limit
            if env_limit and env_limit.isdigit() and 1 <= int(env_limit):
                limit: int = min(int(env_limit), self.config.max_workers)
            else:
                if env_limit:
                    LOG.warning(f"Invalid extractor limit '{env_limit}' for '{extractor}', using default limit.")
                limit = self.config.max_workers_per_extractor

            limit = min(limit, self.config.max_workers)

            self.limits[extractor] = asyncio.Semaphore(limit)
            LOG.info(f"Created limits container for extractor '{extractor}': {limit}")

        return self.limits[extractor]

    def attach(self, _: web.Application) -> None:
        """
        Attach the download queue to the application.

        Args:
            _ (web.Application): The application to attach the download queue to.

        """

        async def event_handler(_, __):
            await self.initialize()

        self._notify.subscribe(Events.STARTED, event_handler, f"{__class__.__name__}.{__class__.initialize.__name__}")

        Scheduler.get_instance().add(
            timer="* * * * *",
            func=self._check_for_stale,
            id=f"{__class__.__name__}.{__class__._check_for_stale.__name__}",
        )

        Scheduler.get_instance().add(
            timer="* * * * *",
            func=self._check_live,
            id=f"{__class__.__name__}.{__class__._check_live.__name__}",
        )
        # app.on_shutdown.append(self.on_shutdown)

    async def test(self) -> bool:
        """
        Test the datastore connection to the database.

        Returns:
            bool: True if the test is successful, False otherwise.

        """
        await self.done.test()
        return True

    async def initialize(self) -> None:
        """
        Initialize the download queue.
        """
        LOG.info(
            f"Using '{self.config.max_workers}' workers for downloading and '{self.config.max_workers_per_extractor}' per extractor."
        )
        asyncio.create_task(self._download_pool(), name="download_pool")

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
                item: Download = self.queue.get(key=item_id)
            except KeyError as e:
                status[item_id] = f"not found: {e!s}"
                status["status"] = "error"
                LOG.warning(f"Start requested for non-existent item {item_id=}.")
                continue

            if item.info.auto_start:
                status[item_id] = "already started"
                continue

            item.info.auto_start = True
            updated: Download = self.queue.put(item)
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
            self.event.set()

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
                item: Download = self.queue.get(key=item_id)
            except KeyError as e:
                status[item_id] = f"not found: {e!s}"
                status["status"] = "error"
                LOG.warning(f"Start requested for non-existent item {item_id=}.")
                continue

            if item.started() or item.is_cancelled():
                status[item_id] = "already started"
                continue

            if item.info.auto_start is False:
                status[item_id] = "not started"
                continue

            item.info.auto_start = False
            updated: Download = self.queue.put(item)
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
        if self.paused.is_set():
            self.paused.clear()
            if not shutdown:
                LOG.warning(f"Download paused at. {datetime.now(tz=UTC).isoformat()}")
            return True

        return False

    def resume(self) -> bool:
        """
        Resume the download queue.

        Returns:
            bool: True if the download is resumed, False otherwise

        """
        if not self.paused.is_set():
            self.paused.set()
            LOG.warning(f"Downloading resumed at. {datetime.now(tz=UTC).isoformat()}")
            return True

        return False

    def is_paused(self) -> bool:
        """
        Check if the download queue is paused.

        Returns:
            bool: True if the download queue is paused, False otherwise

        """
        return not self.paused.is_set()

    async def on_shutdown(self, _: web.Application):
        LOG.debug("Canceling all active downloads.")
        if self._active:
            self.pause()
            try:
                await self.cancel(list(self._active.keys()))
            except Exception as e:
                LOG.error(f"Failed to cancel downloads. {e!s}")

    async def _process_playlist(self, entry: dict, item: Item, already=None, yt_params: dict | None = None):
        if not yt_params:
            yt_params = {}

        entries = entry.get("entries", [])

        playlist_name: str = f"{entry.get('id')}: {entry.get('title')}"

        LOG.info(f"Processing '{playlist_name} ({len(entries)})' Playlist.")

        playlistCount = entry.get("playlist_count")
        playlistCount: int = int(playlistCount) if playlistCount else len(entries)

        results = []

        playlist_keys: dict[str, Any] = {
            "playlist_count": playlistCount,
            "playlist": entry.get("title") or entry.get("id"),
            "playlist_id": entry.get("id"),
            "playlist_title": entry.get("title"),
            "playlist_uploader": entry.get("uploader"),
            "playlist_uploader_id": entry.get("uploader_id"),
            "playlist_channel": entry.get("channel"),
            "playlist_channel_id": entry.get("channel_id"),
            "playlist_webpage_url": entry.get("webpage_url"),
            "__last_playlist_index": playlistCount - 1,
            "n_entries": len(entries),
        }

        async def playlist_processor(i: int, etr: dict):
            try:
                item_name: str = (
                    f"'{entry.get('title')}: {i}/{playlist_keys['n_entries']}' - '{etr.get('id')}: {etr.get('title')}'"
                )
                LOG.debug(f"Waiting to acquire lock for {item_name}")
                await self.processors.acquire()
                LOG.debug(f"Acquired lock for {item_name}")

                if self.is_paused():
                    LOG.warning(f"Download is paused. Skipping processing of '{item_name}'.")
                    return {"status": "ok"}

                LOG.info(f"Processing '{item_name}'.")

                _status, _msg = ytdlp_reject(entry=etr, yt_params=yt_params)
                if not _status:
                    return {"status": "error", "msg": _msg}

                extras: dict[str, Any] = {
                    **playlist_keys,
                    "playlist_index": i,
                    "playlist_index_number": i,
                    "playlist_autonumber": i,
                }

                for property in ("id", "title", "uploader", "uploader_id"):
                    if property in entry:
                        extras[f"playlist_{property}"] = entry.get(property)

                if "thumbnail" not in etr and "youtube:" in entry.get("extractor", ""):
                    extras["thumbnail"] = f"https://img.youtube.com/vi/{etr['id']}/maxresdefault.jpg"

                newItem: Item = item.new_with(url=etr.get("url") or etr.get("webpage_url"), extras=extras)

                if "formats" in etr and isinstance(etr["formats"], list) and len(etr["formats"]) > 0:
                    LOG.warning(f"Unexpected formats entries in --flat-playlist for {item_name}, treating as video.")
                    return await self._add_video(
                        entry=merge_dict(merge_dict({"_type": "video"}, etr), entry), item=newItem, logs=[]
                    )

                return await self.add(item=newItem, already=already)
            finally:
                self.processors.release()

        max_downloads: int = -1
        ytdlp_opts: dict[str, Any] = item.get_ytdlp_opts().get_all()
        if ytdlp_opts.get("max_downloads") and isinstance(ytdlp_opts.get("max_downloads"), int):
            max_downloads: int = ytdlp_opts.get("max_downloads")

        tasks: list[asyncio.Task] = []
        for i, etr in enumerate(entries, start=1):
            if max_downloads > 0 and i > max_downloads:
                break

            task = asyncio.create_task(
                playlist_processor(i, etr),
                name=f"playlist_processor_{etr.get('id')}_{i}",
            )
            task.add_done_callback(self._handle_task_exception)
            tasks.append(task)

        results: list[dict] = await asyncio.gather(*tasks)

        log_msg: str = f"Playlist '{playlist_name}' processing completed with '{len(results)}' entries."
        if max_downloads > 0 and len(entries) > max_downloads:
            skipped: int = len(entries) - max_downloads
            log_msg += f" Limited to '{max_downloads}' items, skipped '{skipped}' remaining items."

        LOG.info(log_msg)

        if any("error" == res["status"] for res in results):
            return {
                "status": "error",
                "msg": ", ".join(res["msg"] for res in results if "error" == res["status"] and "msg" in res),
            }

        return {"status": "ok"}

    async def _add_video(self, entry: dict, item: Item, logs: list[str] | None = None):
        if not logs:
            logs: list[str] = []

        options: dict = {}
        error: str | None = None
        live_in: str | None = None
        is_premiere: bool = bool(entry.get("is_premiere", False))

        release_in: str | None = None
        if entry.get("release_timestamp"):
            release_in = formatdate(entry.get("release_timestamp"), usegmt=True)
            item.extras["release_in"] = release_in

        # check if the video is live stream.
        if "is_upcoming" == entry.get("live_status"):
            if release_in:
                live_in = release_in
                item.extras["live_in"] = live_in
            else:
                error = f"No start time is set for {'premiere' if is_premiere else 'live stream'}."
        else:
            error = entry.get("msg")

        LOG.debug(f"Entry id '{entry.get('id')}' url '{entry.get('webpage_url')} - {entry.get('url')}'.")

        try:
            _item: Download = self.done.get(key=entry.get("id"), url=entry.get("webpage_url") or entry.get("url"))
            err_msg: str = f"Removing {_item.info.name()} from history list."
            LOG.warning(err_msg)
            await self.clear([_item.info._id], remove_file=False)
        except KeyError:
            pass

        try:
            _item: Download = self.queue.get(
                key=str(entry.get("id")), url=str(entry.get("webpage_url") or entry.get("url"))
            )
            err_msg: str = f"Item {_item.info.name()} is already in download queue."
            LOG.info(err_msg)
            return {"status": "error", "msg": err_msg}
        except KeyError:
            pass

        live_status: list = ["is_live", "is_upcoming"]
        is_live = bool(entry.get("is_live") or live_in or entry.get("live_status") in live_status)

        try:
            download_dir: str = calc_download_path(base_path=self.config.download_path, folder=item.folder)
        except Exception as e:
            LOG.exception(e)
            return {"status": "error", "msg": str(e)}

        for field in ("uploader", "channel", "thumbnail"):
            if entry.get(field):
                item.extras[field] = entry.get(field)

        for key in entry:
            if isinstance(key, str) and key.startswith("playlist") and entry.get(key):
                item.extras[key] = entry.get(key)

        item.extras["duration"] = entry.get("duration", item.extras.get("duration"))

        if not item.extras.get("live_in") and live_in:
            item.extras["live_in"] = live_in

        if not item.extras.get("is_premiere") and is_premiere:
            item.extras["is_premiere"] = is_premiere

        dl = ItemDTO(
            id=str(entry.get("id")),
            title=str(entry.get("title")),
            description=str(entry.get("description", "")),
            url=str(entry.get("webpage_url") or entry.get("url")),
            preset=item.preset,
            folder=item.folder,
            download_dir=download_dir,
            temp_dir=self.config.temp_path,
            cookies=item.cookies,
            template=item.template if item.template else self.config.output_template,
            template_chapter=self.config.output_template_chapter,
            datetime=formatdate(time.time()),
            error=error,
            is_live=is_live,
            live_in=live_in if live_in else item.extras.get("live_in", None),
            options=options,
            cli=item.cli,
            auto_start=item.auto_start,
            extras=item.extras,
        )

        try:
            dlInfo: Download = Download(info=dl, info_dict=entry if item.auto_start else None, logs=logs)
            nEvent: str | None = None
            nTitle: str | None = None
            nMessage: str | None = None
            nStore: str = "queue"

            text_logs: str = ""
            if filtered_logs := extract_ytdlp_logs(logs):
                text_logs = " " + ", ".join(filtered_logs)

            if "is_upcoming" == entry.get("live_status"):
                nEvent = Events.ITEM_MOVED
                nStore = "history"
                nTitle = "Upcoming Premiere" if is_premiere else "Upcoming Live Stream"
                nMessage = f"{'Premiere video' if is_premiere else 'Stream'} '{dlInfo.info.title}' is not available yet. {text_logs}"

                dlInfo.info.status = "not_live"
                dlInfo.info.msg = nMessage.replace(f" '{dlInfo.info.title}'", "")
                self._notify.emit(
                    Events.LOG_INFO,
                    data={"preset": dlInfo.info.preset, "lowPriority": True},
                    title=nTitle,
                    message=nMessage,
                )

                itemDownload: Download = self.done.put(dlInfo)
            elif len(entry.get("formats", [])) < 1:
                ava: str = entry.get("availability", "public")
                nTitle = "Download Error"
                nMessage: str = f"No formats for '{dl.title}'."
                nEvent = Events.ITEM_MOVED
                nStore = "history"

                if ava and ava not in ("public",):
                    nMessage += f" Availability is set for '{ava}'."

                dlInfo.info.error = nMessage.replace(f" for '{dl.title}'.", ".") + text_logs
                dlInfo.info.status = "error"
                itemDownload = self.done.put(dlInfo)

                self._notify.emit(
                    Events.LOG_WARNING,
                    data={"preset": dlInfo.info.preset, "logs": text_logs},
                    title=nTitle,
                    message=nMessage,
                )
            elif is_premiere and self.config.prevent_live_premiere:
                nStore = "history"
                nTitle = "Premiere Video"
                dlInfo.info.error = "Premiering right now."

                _requeue = True
                if release_in:
                    try:
                        starts_in: datetime = str_to_dt(release_in)
                        starts_in: datetime = (
                            starts_in.replace(tzinfo=UTC) if starts_in.tzinfo is None else starts_in.astimezone(UTC)
                        )
                        starts_in = starts_in + timedelta(minutes=5, seconds=dl.extras.get("duration", 0))
                        dlInfo.info.error += f" Download will start at {starts_in.astimezone().isoformat()}."
                        _requeue = False
                    except Exception as e:
                        LOG.error(f"Failed to parse live_in date '{release_in}'. {e!s}")
                        dlInfo.info.error += f" Failed to parse live_in date '{release_in}'."
                else:
                    dlInfo.info.error += f" Delaying download by '{300 + dl.extras.get('duration', 0)}' seconds."

                nMessage = f"'{dlInfo.info.title}': '{dlInfo.info.error.strip()}'."

                if _requeue:
                    nEvent = Events.ITEM_ADDED
                    itemDownload = self.queue.put(dlInfo)
                    if item.auto_start:
                        self.event.set()
                else:
                    dlInfo.info.status = "not_live"
                    itemDownload = self.done.put(dlInfo)
                    nStore = "history"
                    nEvent = Events.ITEM_MOVED
                    nTitle = "Premiering right now"
                    self._notify.emit(
                        Events.LOG_INFO, data={"preset": dlInfo.info.preset}, title=nTitle, message=nMessage
                    )
            else:
                nEvent = Events.ITEM_ADDED
                nTitle = "Item Added"
                nMessage = f"Item '{dlInfo.info.title}' has been added to the download queue."
                itemDownload = self.queue.put(dlInfo)
                if item.auto_start:
                    self.event.set()
                else:
                    LOG.debug(f"Item {itemDownload.info.name()} is not set to auto-start.")

            self._notify.emit(
                nEvent,
                data={"to": nStore, "preset": itemDownload.info.preset, "item": itemDownload.info}
                if Events.ITEM_MOVED == nEvent
                else itemDownload.info,
                title=nTitle,
                message=nMessage,
            )

            return {"status": "ok"}
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Failed to download item. '{e!s}'")
            return {"status": "error", "msg": str(e)}

    async def _add_item(
        self, entry: dict, item: Item, already=None, logs: list | None = None, yt_params: dict | None = None
    ):
        """
        Add an entry to the download queue.

        Args:
            entry (dict): The entry to add to the download queue.
            item (Item): The item to add to the download queue.
            already (set): The set of already downloaded items.
            logs (list): The list of logs generated during information extraction.
            yt_params (dict): The parameters for yt-dlp.

        Returns:
            dict: The status of the operation.

        """
        if not entry:
            return {"status": "error", "msg": "Invalid/empty data was given."}

        event_type = entry.get("_type", "video")

        if event_type.startswith("playlist"):
            return await self._process_playlist(entry=entry, item=item, already=already, yt_params=yt_params)

        if event_type.startswith("url"):
            return await self.add(item=item.new_with(url=entry.get("url")), already=already)

        if event_type.startswith("video"):
            return await self._add_video(entry=entry, item=item, logs=logs)

        return {"status": "error", "msg": f'Unsupported event type "{event_type}".'}

    async def add(self, item: Item, already: set | None = None):
        """
        Add an item to the download queue.

        Args:
            item (Item): The item to be added to the queue.
            already (set): Set of already downloaded items.

        Returns:
            dict[str, str]: The status of the download.
            { "status": "text" }

        """
        _preset: Preset | None = Presets.get_instance().get(item.preset)

        if item.has_cli():
            try:
                arg_converter(args=item.cli, level=True)
            except Exception as e:
                LOG.error(f"Invalid command options for yt-dlp '{item.cli}'. {e!s}")
                return {"status": "error", "msg": f"Invalid command options for yt-dlp '{item.cli}'. {e!s}"}

        if _preset:
            if _preset.folder and not item.folder:
                item.folder = _preset.folder

            if _preset.template and not item.template:
                item.template = _preset.template

        yt_conf = {}
        cookie_file: Path = Path(self.config.temp_path) / f"c_{uuid.uuid4().hex}.txt"

        LOG.info(f"Adding '{item.__repr__()}'.")

        already = set() if already is None else already

        if item.url in already:
            LOG.warning(f"Recursion detected with url '{item.url}' skipping.")
            return {"status": "ok"}

        already.add(item.url)

        try:
            logs: list = []

            yt_conf: dict = {
                "callback": {
                    "func": lambda _, msg: logs.append(msg),
                    "level": logging.WARNING,
                    "name": "callback-logger",
                },
                **item.get_ytdlp_opts().get_all(),
            }

            if yt_conf.get("external_downloader"):
                LOG.warning(f"Using external downloader '{yt_conf.get('external_downloader')}' for '{item.url}'.")
                item.extras.update({"external_downloader": True})

            archive_id = item.get_archive_id()

            if item.is_archived():
                if archive_id:
                    store_type, _ = self.get_item(archive_id=archive_id)
                    if not store_type:
                        dlInfo = Download(
                            info=ItemDTO(
                                id=archive_id.split()[1],
                                title=archive_id,
                                url=item.url,
                                preset=item.preset,
                                folder=item.folder,
                                status="skip",
                                cookies=item.cookies,
                                template=item.template,
                                msg="URL is already downloaded.",
                                extras=item.extras,
                            )
                        )

                        if archive_file := dlInfo.info.get_ytdlp_opts().get_all().get("download_archive"):
                            dlInfo.info.msg += f" Found in archive '{archive_file}'."

                        self.done.put(dlInfo)

                        self._notify.emit(
                            Events.ITEM_MOVED,
                            data={"to": "history", "preset": dlInfo.info.preset, "item": dlInfo.info},
                            title="Download History Update",
                            message=f"Download history updated with '{item.url}'.",
                        )
                        return {"status": "ok"}

                message: str = f"The URL '{item.url}' is already downloaded and recorded in archive."
                LOG.error(message)
                self._notify.emit(
                    Events.LOG_INFO, data={"preset": item.preset}, title="Already Downloaded", message=message
                )

                return {"status": "error", "msg": message}

            started: float = time.perf_counter()

            if item.cookies:
                try:
                    yt_conf["cookiefile"] = str(create_cookies_file(item.cookies, cookie_file).as_posix())
                except Exception as e:
                    msg = f"Failed to create cookie file for '{item.url}'. '{e!s}'."
                    LOG.error(msg)
                    return {"status": "error", "msg": msg}

            LOG.info(f"Checking '{item.url}' with {'cookies' if yt_conf.get('cookiefile') else 'no cookies'}.")

            entry: dict | None = await asyncio.wait_for(
                fut=asyncio.get_running_loop().run_in_executor(
                    None,
                    functools.partial(
                        extract_info,
                        config=yt_conf,
                        url=item.url,
                        debug=bool(self.config.ytdlp_debug),
                        no_archive=False,
                        follow_redirect=True,
                    ),
                ),
                timeout=self.config.extract_info_timeout,
            )

            if not entry:
                LOG.error(f"Unable to extract info for '{item.url}'. Logs: {logs}")
                return {"status": "error", "msg": "Unable to extract info." + "\n".join(logs)}

            if not item.requeued and (condition := Conditions.get_instance().match(info=entry)):
                already.pop()

                item_title = entry.get("title") or entry.get("id") or item.url
                message = f"Condition '{condition.name}' matched for '{item_title}'."

                if condition.cli:
                    message += f" Re-queuing with '{condition.cli}'."

                LOG.info(message)

                if condition.extras.get("ignore_download", False):
                    extra_msg: str = ""
                    if yt_conf.get("download_archive") and not condition.extras.get("no_archive", False):
                        archive_add(yt_conf.get("download_archive"), [archive_id])
                        extra_msg = f" and added to archive '{yt_conf.get('download_archive')}'"

                    log_message = f"Ignoring download of '{item_title}' as per condition '{condition.name}'{extra_msg}."

                    store_type, _ = self.get_item(archive_id=archive_id)
                    if not store_type:
                        dlInfo = Download(
                            info=ItemDTO(
                                id=entry.get("id"),
                                title=item_title,
                                url=item.url,
                                preset=item.preset,
                                folder=item.folder,
                                status="skip",
                                cookies=item.cookies,
                                template=item.template,
                                msg=log_message,
                                extras=item.extras,
                            )
                        )
                        self.done.put(dlInfo)

                    LOG.info(log_message)
                    self._notify.emit(Events.LOG_INFO, data={}, title="Ignored Download", message=log_message)
                    self._notify.emit(
                        Events.ITEM_MOVED,
                        data={"to": "history", "preset": dlInfo.info.preset, "item": dlInfo.info},
                        title="Download History Update",
                        message=f"Download history updated with '{item.url}'.",
                    )
                    return {"status": "ok"}

                return await self.add(item=item.new_with(requeued=True, cli=condition.cli), already=already)

            _status, _msg = ytdlp_reject(entry=entry, yt_params=yt_conf)
            if not _status:
                LOG.debug(_msg)
                return {"status": "error", "msg": _msg}

            end_time = time.perf_counter() - started
            LOG.debug(f"extract_info: for 'URL: {item.url}' is done in '{end_time:.3f}'. Length: '{len(entry)}/keys'.")
        except yt_dlp.utils.ExistingVideoReached as exc:
            LOG.error(f"Video has been downloaded already and recorded in archive.log file. '{exc!s}'.")
            return {"status": "error", "msg": "Video has been downloaded already and recorded in archive.log file."}
        except yt_dlp.utils.YoutubeDLError as exc:
            LOG.error(f"YoutubeDLError: Unable to extract info. '{exc!s}'.")
            return {"status": "error", "msg": str(exc)}
        except asyncio.exceptions.TimeoutError as exc:
            LOG.error(f"TimeoutError: Unable to extract info. '{exc!s}'.")
            return {
                "status": "error",
                "msg": f"TimeoutError: {self.config.extract_info_timeout}s reached Unable to extract info.",
            }
        finally:
            if cookie_file and cookie_file.exists():
                try:
                    cookie_file.unlink(missing_ok=True)
                    yt_conf.pop("cookiefile", None)
                except Exception as e:
                    LOG.error(f"Failed to remove cookie file '{yt_conf['cookiefile']}'. {e!s}")

        return await self._add_item(entry=entry, item=item, already=already, logs=logs, yt_params=yt_conf)

    async def cancel(self, ids: list[str]) -> dict[str, str]:
        """
        Cancel the download.

        Args:
            ids (list): The list of ids to cancel.

        Returns:
            dict: The status of the operation.

        """
        status: dict[str, str] = {"status": "ok"}

        for id in ids:
            try:
                item = self.queue.get(key=id)
            except KeyError as e:
                status[id] = str(e)
                status["status"] = "error"
                LOG.warning(f"Requested cancel for non-existent download {id=}. {e!s}")
                continue

            item_ref = f"{id=} {item.info.id=} {item.info.title=}"

            if item.running():
                LOG.debug(f"Canceling {item_ref}")
                item.cancel()
                LOG.info(f"Cancelled {item_ref}")
                await item.close()
            else:
                await item.close()
                LOG.debug(f"Deleting from queue {item_ref}")
                self.queue.delete(id)
                self._notify.emit(
                    Events.ITEM_CANCELLED,
                    data=item.info,
                    title="Download Cancelled",
                    message=f"Download '{item.info.title}' has been cancelled.",
                )
                item.info.status = "cancelled"
                self.done.put(item)
                self._notify.emit(
                    Events.ITEM_MOVED,
                    data={"to": "history", "preset": item.info.preset, "item": item.info},
                    title="Download Cancelled",
                    message=f"Download '{item.info.title}' has been cancelled.",
                )
                LOG.info(f"Deleted from queue {item_ref}")

            status[id] = "ok"

        return status

    async def clear(self, ids: list[str], remove_file: bool = False) -> dict[str, str]:
        """
        Clear the download history.

        Args:
            ids (list): The list of ids to clear.
            remove_file (bool): True to remove the file, False otherwise. Default is False.

        Returns:
            dict: The status of the operation.

        """
        status: dict[str, str] = {"status": "ok"}

        for id in ids:
            try:
                item: Download = self.done.get(key=id)
            except KeyError as e:
                status[id] = str(e)
                status["status"] = "error"
                LOG.warning(f"Requested delete for non-existent download {id=}. {e!s}")
                continue

            itemRef: str = f"{id=} {item.info.id=} {item.info.title=}"
            removed_files = 0
            filename: str = ""

            LOG.debug(
                f"{remove_file=} {itemRef} - Removing local files: {self.config.remove_files}, {item.info.status=}"
            )

            if remove_file and self.config.remove_files and "finished" == item.info.status:
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
                                    LOG.debug(f"Removing '{itemRef}' local file '{f.name}'.")
                                    f.unlink(missing_ok=True)
                        else:
                            LOG.debug(f"Removing '{itemRef}' local file '{rf.name}'.")
                            rf.unlink(missing_ok=True)
                            removed_files += 1
                    else:
                        LOG.warning(f"Failed to remove '{itemRef}' local file '{filename}'. File not found.")
                except Exception as e:
                    LOG.error(f"Unable to remove '{itemRef}' local file '{filename}'. {e!s}")

            self.done.delete(id)

            _status: str = "Removed" if removed_files > 0 else "Cleared"
            self._notify.emit(
                Events.ITEM_DELETED,
                data=item.info,
                title=f"Download {_status}",
                message=f"{_status} '{item.info.title}' from history.",
            )

            msg = f"Deleted completed download '{itemRef}'."
            if removed_files > 0:
                msg += f" and removed '{removed_files}' local files."

            LOG.info(msg=msg)
            status[id] = "ok"

        return status

    def get(self) -> dict[str, list[dict[str, ItemDTO]]]:
        """
        Get the download queue and the download history.

        Returns:
            dict: The download queue and the download history.

        """
        items = {"queue": {}, "done": {}}

        for k, v in self.queue.saved_items():
            items["queue"][k] = self._active[k].info if k in self._active else v

        for k, v in self.done.saved_items():
            v.get_file_sidecar()
            items["done"][k] = v

        for k, v in self.queue.items():
            if k not in items["queue"]:
                items["queue"][k] = self._active[k].info if k in self._active else v

        for k, v in self.done.items():
            if k in items["done"]:
                continue

            v.info.get_file_sidecar()
            items["done"][k] = v.info

        return items

    def get_item(self, **kwargs) -> tuple[StoreType, Download] | tuple[None, None]:
        """
        Get a specific item from the download queue or history.

        Args:
            **kwargs: The key-value pair to search for. Supported keys are 'id', 'url'.

        Returns:
            (StoreType, Download) | None: The requested item if found, otherwise None.

        """
        if item := self.queue.get_item(**kwargs):
            return (StoreType.QUEUE, item)

        if item := self.done.get_item(**kwargs):
            return (StoreType.HISTORY, item)

        return (None, None)

    async def _download_pool(self) -> None:
        """
        Create a pool of workers to download the files.
        """
        adaptive_sleep = 0.2  # Start with base sleep
        max_sleep = 5.0  # Maximum sleep to avoid excessive delays

        while True:
            while not self.queue.has_downloads():
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

            for _id, entry in list(self.queue.items()):
                if entry.started() or entry.is_cancelled() or entry.info.auto_start is False:
                    continue

                extractor: str = entry.info.get_extractor() or "unknown"

                # Live downloads bypass all limits.
                if entry.is_live:
                    task: asyncio.Task[None] = asyncio.create_task(
                        self._download_live(_id, entry), name=f"download_live_{extractor}_{_id}"
                    )
                    task.add_done_callback(self._handle_task_exception)
                    items_processed += 1
                else:
                    _limit: asyncio.Semaphore = self._get_limit(extractor)

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
                        self._handle_task_exception(t)

                    task.add_done_callback(_release)
                    items_processed += 1

            # No items could be processed, back off a bit to avoid busy-waiting.
            if 0 == items_processed:
                adaptive_sleep: float = min(adaptive_sleep * 1.5, max_sleep)
                LOG.debug(f"No download slots available. Backing off for {adaptive_sleep:.2f}s before next attempt.")
            else:
                adaptive_sleep = 0.2

            await asyncio.sleep(adaptive_sleep)

    async def _download_live(self, _id: str, entry: Download) -> None:
        LOG.debug(f"Creating temporary worker for entry '{entry.info.name()}'.")

        try:
            await self._download_file(_id, entry)
        finally:
            LOG.debug(f"Temporary worker for '{entry.info.name()}' completed.")

    async def _download_file(self, id: str, entry: Download) -> None:
        """
        Download the file.

        Args:
            id (str): The id of the download.
            entry (Download): The download entry.

        Returns:
            None

        """
        filePath: str = calc_download_path(base_path=self.config.download_path, folder=entry.info.folder)
        LOG.info(f"Downloading 'id: {id}', 'Title: {entry.info.title}', 'URL: {entry.info.url}' To '{filePath}'.")

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

        if self.queue.exists(key=id):
            LOG.debug(f"Download Task '{id}' is completed. Removing from queue.")
            self.queue.delete(key=id)

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

            self.done.put(entry)
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

    async def _check_for_stale(self):
        """
        Monitor pool for stale downloads and cancel them if needed.
        """
        if self.is_paused() or self.queue.empty():
            return

        for _id, item in list(self.queue.items()):
            item_ref = f"{_id=} {item.info.id=} {item.info.title=}"
            if not item.is_stale():
                continue

            try:
                LOG.warning(f"Cancelling staled item '{item_ref}' from download queue.")
                await self.cancel([_id])
            except Exception as e:
                LOG.error(f"Failed to cancel staled item '{item_ref}'. {e!s}")
                LOG.exception(e)

    async def _check_live(self):
        """
        Monitor the queue for items marked as live events and queue them when time is reached.
        """
        if self.is_paused() or self.done.empty():
            return

        if self.config.debug:
            LOG.debug("Checking history queue for queued live stream links.")

        time_now = datetime.now(tz=UTC)

        status: list[str] = ["not_live", "is_upcoming", "is_live"]

        for id, item in list(self.done.items()):
            if item.info.status not in status:
                continue

            item_ref: str = f"{id=} {item.info.id=} {item.info.title=}"
            if not item.is_live:
                LOG.debug(f"Item '{item_ref}' is not a live stream.")
                continue

            duration: int | None = item.info.extras.get("duration", None)
            is_premiere: bool = item.info.extras.get("is_premiere", False)

            live_in: str | None = item.info.live_in or ag(item.info.extras, ["live_in", "release_in"], None)
            if not live_in:
                LOG.debug(
                    f"Item '{item_ref}' marked as {'premiere video' if is_premiere else 'live stream'}, but no date is set."
                )
                continue

            starts_in = str_to_dt(live_in)
            starts_in = starts_in.replace(tzinfo=UTC) if starts_in.tzinfo is None else starts_in.astimezone(UTC)

            if time_now < (starts_in + timedelta(minutes=1)):
                LOG.debug(f"Item '{item_ref}' is not yet live. will start at '{dt_delta(starts_in - time_now)}'.")
                continue

            if self.config.prevent_live_premiere and is_premiere and duration:
                premiere_ends: datetime = starts_in + timedelta(minutes=5, seconds=duration)
                if time_now < premiere_ends:
                    LOG.debug(
                        f"Item '{item_ref}' is premiering, download will start in '{(starts_in + timedelta(minutes=5, seconds=duration)).astimezone().isoformat()}'"
                    )
                    continue

            LOG.info(f"Retrying item '{item_ref} {item.info.extras=}' for download.")

            try:
                await self.clear([item.info._id], remove_file=False)
            except Exception as e:
                LOG.error(f"Failed to clear item '{item_ref}'. {e!s}")
                continue

            try:
                await self.add(
                    item=Item(
                        url=item.info.url,
                        preset=item.info.preset,
                        folder=item.info.folder,
                        cookies=item.info.cookies,
                        template=item.info.template,
                        cli=item.info.cli,
                        extras=item.info.extras,
                    )
                )
            except Exception as e:
                self.done.put(item)
                LOG.exception(e)
                LOG.error(f"Failed to retry item '{item_ref}'. {e!s}")

    def _handle_task_exception(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return

        if not (exc := task.exception()):
            return

        task_name: str = task.get_name() if task.get_name() else "unknown_task"
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        LOG.error(f"Unhandled exception in background task '{task_name}': {exc!s}. {tb}")
