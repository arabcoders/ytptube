import asyncio
import functools
import glob
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from email.utils import formatdate
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

import yt_dlp
from aiohttp import web

from app.library.ag_utils import ag

from .AsyncPool import AsyncPool
from .conditions import Conditions
from .config import Config
from .DataStore import DataStore
from .Download import Download
from .Events import EventBus, Events
from .Events import info as event_info
from .Events import warning as event_warning
from .ItemDTO import Item, ItemDTO
from .Presets import Presets
from .Scheduler import Scheduler
from .Singleton import Singleton
from .Utils import (
    arg_converter,
    calc_download_path,
    dt_delta,
    extract_info,
    extract_ytdlp_logs,
    is_downloaded,
    load_cookies,
    str_to_dt,
)
from .YTDLPOpts import YTDLPOpts

if TYPE_CHECKING:
    from app.library.Presets import Preset

LOG = logging.getLogger("DownloadQueue")


class DownloadQueue(metaclass=Singleton):
    """
    DownloadQueue class is a singleton class that manages the download queue and the download history.
    """

    TYPE_DONE: str = "done"
    """Queue type for completed downloads."""

    TYPE_QUEUE: str = "queue"
    """Queue type for pending downloads."""

    paused: asyncio.Event
    """Event to pause the download queue."""

    event: asyncio.Event
    """Event to signal the download queue to start downloading."""

    pool: AsyncPool | None = None
    """Pool of workers to download the files."""

    _active: dict[str, Download] = {}
    """Dictionary of active downloads."""

    _instance = None
    """Instance of the DownloadQueue."""

    queue: DataStore
    """DataStore for the download queue."""

    done: DataStore
    """DataStore for the completed downloads."""

    def __init__(self, connection: Connection, config: Config | None = None):
        DownloadQueue._instance = self

        self.config = config or Config.get_instance()
        self._notify = EventBus.get_instance()
        self.done = DataStore(type=DownloadQueue.TYPE_DONE, connection=connection)
        self.queue = DataStore(type=DownloadQueue.TYPE_QUEUE, connection=connection)
        self.done.load()
        self.queue.load()
        self.paused = asyncio.Event()
        self.paused.set()
        self.event = asyncio.Event()

    @staticmethod
    def get_instance():
        """
        Get the instance of the DownloadQueue.

        Returns:
            DownloadQueue: The instance of the DownloadQueue

        """
        if not DownloadQueue._instance:
            DownloadQueue._instance = DownloadQueue()

        return DownloadQueue._instance

    def attach(self, app: web.Application):
        """
        Attach the download queue to the application.

        Args:
            app (web.Application): The application to attach the download queue to.

        """
        app.on_startup.append(lambda _: self.initialize())

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

        # async def close_pool(_: web.Application):
        #     try:
        #         await self.pool.on_shutdown(_)
        #     except Exception as e:
        #         LOG.error(f"Failed to cleanup download pool. {e!s}")

        # app.on_cleanup.append(close_pool)

    async def test(self) -> bool:
        """
        Test the datastore connection to the database.

        Returns:
            bool: True if the test is successful, False otherwise.

        """
        await self.done.test()
        return True

    async def initialize(self):
        """
        Initialize the download queue.
        """
        LOG.info(
            f"Using '{self.config.max_workers}' worker/s for downloading. Can be configured via `YTP_MAX_WORKERS` environment variable."
        )
        asyncio.create_task(self._download_pool(), name="download_pool")

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

    async def _process_playlist(self, entry: dict, item: Item, already=None):
        if 1 == self.config.playlist_items_concurrency:
            return await self._process_playlist_old(entry=entry, item=item, already=already)

        LOG.info(f"Playlist '{entry.get('id')}: {entry.get('title')}' processing.")
        entries = entry.get("entries", [])
        playlistCount = int(entry.get("playlist_count", len(entries)))
        results = []

        semaphore = asyncio.Semaphore(self.config.playlist_items_concurrency)

        async def process_entry(i, etr):
            extras = {
                "playlist": entry.get("id"),
                "playlist_index": f"{{0:0{len(str(playlistCount))}d}}".format(i),
                "playlist_autonumber": i,
            }

            for property in ("id", "title", "uploader", "uploader_id"):
                if property in entry:
                    extras[f"playlist_{property}"] = entry.get(property)

            LOG.debug(f"Processing entry {i}/{playlistCount} - ID: {etr.get('id')} - Title: {etr.get('title')}")

            if "thumbnail" not in etr and "youtube:" in entry.get("extractor", ""):
                extras["thumbnail"] = f"https://img.youtube.com/vi/{etr['id']}/maxresdefault.jpg"

            async with semaphore:
                return await self.add(
                    item=item.new_with(url=etr.get("url") or etr.get("webpage_url"), extras=extras),
                    already=already,
                )

        tasks = [process_entry(i, etr) for i, etr in enumerate(entries, start=1)]
        results = await asyncio.gather(*tasks)

        LOG.info(
            f"Playlist '{entry.get('id')}: {entry.get('title')}' processing completed with '{len(results)}' entries."
        )

        if any("error" == res["status"] for res in results):
            return {
                "status": "error",
                "msg": ", ".join(res["msg"] for res in results if res["status"] == "error" and "msg" in res),
            }

        return {"status": "ok"}

    async def _process_playlist_old(self, entry: dict, item: Item, already=None):
        LOG.info(f"Playlist '{entry.get('id')}: {entry.get('title')}' processing.")
        entries = entry.get("entries", [])
        playlistCount = int(entry.get("playlist_count", len(entries)))
        results = []

        for i, etr in enumerate(entries, start=1):
            extras = {
                "playlist": entry.get("id"),
                "playlist_index": f"{{0:0{len(str(playlistCount))}d}}".format(i),
                "playlist_autonumber": i,
            }

            for property in ("id", "title", "uploader", "uploader_id"):
                if property in entry:
                    extras[f"playlist_{property}"] = entry.get(property)

            if "thumbnail" not in etr and "youtube:" in entry.get("extractor", ""):
                extras["thumbnail"] = f"https://img.youtube.com/vi/{etr['id']}/maxresdefault.jpg"

            LOG.debug(f"Processing entry {i}/{playlistCount} - ID: {etr.get('id')} - Title: {etr.get('title')}")

            results.append(
                await self.add(
                    item=item.new_with(url=etr.get("url") or etr.get("webpage_url"), extras=extras),
                    already=already,
                )
            )

        LOG.info(
            f"Playlist '{entry.get('id')}: {entry.get('title')}' processing completed with '{len(results)}' entries."
        )

        if any("error" == res["status"] for res in results):
            return {
                "status": "error",
                "msg": ", ".join(res["msg"] for res in results if res["status"] == "error" and "msg" in res),
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
            _item = self.done.get(key=entry.get("id"), url=entry.get("webpage_url") or entry.get("url"))
            if _item is not None:
                err_msg = f"Item '{_item.info.id}' - '{_item.info.title}' already exists. Removing from history."
                LOG.warning(err_msg)
                await self.clear([_item.info._id], remove_file=False)
        except KeyError:
            pass

        try:
            _item = self.queue.get(key=str(entry.get("id")), url=str(entry.get("webpage_url") or entry.get("url")))
            if _item is not None:
                err_msg = f"Item ID '{_item.info.id}' - '{_item.info.title}' already in download queue."
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
            extras=item.extras,
        )

        try:
            dlInfo: Download = Download(info=dl, info_dict=entry, logs=logs)

            text_logs: str = ""
            if filtered_logs := extract_ytdlp_logs(logs):
                text_logs = f" Logs: {', '.join(filtered_logs)}"

            if "is_upcoming" == entry.get("live_status"):
                NotifyEvent = Events.COMPLETED
                dlInfo.info.status = "not_live"
                dlInfo.info.msg = f"{'Premiere video' if is_premiere else 'Stream' } is not available yet." + text_logs
                await self._notify.emit(Events.LOG_INFO, data=event_info(dlInfo.info.msg, {"lowPriority": True}))
                itemDownload: Download = self.done.put(dlInfo)
            elif len(entry.get("formats", [])) < 1:
                availability: str = entry.get("availability", "public")
                msg: str = "No formats found."
                if availability and availability not in ("public",):
                    msg += f" Availability is set for '{availability}'."

                dlInfo.info.error = msg + text_logs
                dlInfo.info.status = "error"
                itemDownload = self.done.put(dlInfo)
                NotifyEvent = Events.COMPLETED
                await self._notify.emit(Events.LOG_WARNING, data=event_warning(f"No formats found for '{dl.title}'."))
            elif is_premiere and self.config.prevent_live_premiere:
                dlInfo.info.error = "Premiering right now."

                _requeue = True
                if release_in:
                    try:
                        starts_in = str_to_dt(release_in)
                        starts_in = (
                            starts_in.replace(tzinfo=UTC) if starts_in.tzinfo is None else starts_in.astimezone(UTC)
                        )
                        starts_in = starts_in + timedelta(minutes=5, seconds=dl.extras.get("duration", 0))
                        dlInfo.info.error += f" Download will start at {starts_in.astimezone().isoformat()}."
                        _requeue = False
                    except Exception as e:
                        LOG.error(f"Failed to parse live_in date '{release_in}'. {e!s}")
                        dlInfo.info.error += f" Failed to parse live_in date '{release_in}'."
                else:
                    dlInfo.info.error += f" Delaying download by '{300+dl.extras.get('duration',0)}' seconds."

                if _requeue:
                    NotifyEvent = Events.ADDED
                    itemDownload = self.queue.put(dlInfo)
                    self.event.set()
                else:
                    dlInfo.info.status = "not_live"
                    itemDownload = self.done.put(dlInfo)
                    NotifyEvent = Events.COMPLETED
                    await self._notify.emit(
                        Events.LOG_INFO,
                        data=event_info(f"'{dl.title}' is {dlInfo.info.error}.", {"lowPriority": True}),
                    )
            else:
                NotifyEvent = Events.ADDED
                itemDownload = self.queue.put(dlInfo)
                self.event.set()

            await self._notify.emit(NotifyEvent, data=itemDownload.info.serialize())

            return {"status": "ok"}
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Failed to download item. '{e!s}'")
            return {"status": "error", "msg": str(e)}

    async def _add_item(self, entry: dict, item: Item, already=None, logs: list | None = None):
        """
        Add an entry to the download queue.

        Args:
            entry (dict): The entry to add to the download queue.
            item (Item): The item to add to the download queue.
            already (set): The set of already downloaded items.
            logs (list): The list of logs generated during information extraction.

        Returns:
            dict: The status of the operation.

        """
        if not entry:
            return {"status": "error", "msg": "Invalid/empty data was given."}

        event_type = entry.get("_type", "video")

        if event_type.startswith("playlist"):
            return await self._process_playlist(entry=entry, item=item, already=already)

        if event_type.startswith("url"):
            return await self.add(item=item.new_with(url=entry.get("url")), already=already)

        if not event_type.startswith("video"):
            return {"status": "error", "msg": f'Unsupported event type "{event_type}".'}

        return await self._add_video(entry=entry, item=item, logs=logs)

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
        cookie_file = Path(self.config.temp_path) / f"c_{uuid.uuid4().hex}.txt"

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
                **YTDLPOpts.get_instance().preset(name=item.preset).add_cli(args=item.cli, from_user=True).get_all(),
            }

            if yt_conf.get("external_downloader"):
                LOG.warning(f"Using external downloader '{yt_conf.get('external_downloader')}' for '{item.url}'.")
                item.extras.update({"external_downloader": True})

            downloaded, id_dict = self._is_downloaded(file=yt_conf.get("download_archive", None), url=item.url)
            if downloaded is True and id_dict:
                message = f"This url with ID '{id_dict.get('id')}' has been downloaded already and recorded in archive."
                LOG.info(message)
                await self._notify.emit(Events.LOG_WARNING, data=event_warning(message))
                return {"status": "error", "msg": message}

            started: float = time.perf_counter()

            if item.cookies:
                try:
                    cookie_file.write_text(item.cookies)
                    yt_conf["cookiefile"] = str(cookie_file.as_posix())
                    load_cookies(cookie_file)
                except Exception as e:
                    msg = f"Failed to create cookie file for '{item.url}'. '{e!s}'."
                    LOG.error(msg)
                    return {"status": "error", "msg": msg}

            LOG.info(f"Checking '{item.url}' with {'cookies' if yt_conf.get('cookiefile') else 'no cookies'}.")

            entry = await asyncio.wait_for(
                fut=asyncio.get_running_loop().run_in_executor(
                    None,
                    functools.partial(
                        extract_info,
                        config=yt_conf,
                        url=item.url,
                        debug=bool(self.config.ytdl_debug),
                        no_archive=False,
                        follow_redirect=True,
                    ),
                ),
                timeout=self.config.extract_info_timeout,
            )

            if not entry:
                return {"status": "error", "msg": "Unable to extract info." + "\n".join(logs)}

            if not item.requeued and (condition := Conditions.get_instance().match(info=entry)):
                already.pop()
                LOG.info(f"Condition '{condition.name}' matched for '{item.url}'.")
                return await self.add(item=item.new_with(requeued=True, cli=condition.cli), already=already)

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

        return await self._add_item(entry=entry, item=item, already=already, logs=logs)

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
                await self._notify.emit(Events.CANCELLED, data=item.info.serialize())
                item.info.status = "cancelled"
                item.info.error = "Cancelled by user."
                self.done.put(item)
                await self._notify.emit(Events.COMPLETED, data=item.info.serialize())
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
            await self._notify.emit(Events.CLEARED, data=item.info.serialize())

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
            items["done"][k] = v

        for k, v in self.queue.items():
            if k not in items["queue"]:
                items["queue"][k] = self._active[k].info if k in self._active else v

        for k, v in self.done.items():
            if k not in items["done"]:
                items["done"][k] = v.info

        return items

    async def _download_pool(self) -> None:
        """
        Create a pool of workers to download the files.

        Returns:
            None

        """
        self.pool = AsyncPool(
            loop=asyncio.get_running_loop(),
            num_workers=self.config.max_workers,
            worker_co=self._download_file,
            name="download_pool",
            logger=logging.getLogger("WorkerPool"),
        )

        self.pool.start()

        lastLog = time.time()

        while True:
            while True:
                if self.pool.has_open_workers() is True:
                    break
                if self.config.max_workers > 1 and time.time() - lastLog > 600:
                    lastLog = time.time()
                    LOG.info("Waiting for worker to be free.", extra={"workers": self.pool.get_available_workers()})
                await asyncio.sleep(1)

            while not self.queue.has_downloads():
                LOG.info(f"Waiting for item to download. '{self.pool.get_available_workers()}' free workers.")
                if self.event:
                    await self.event.wait()
                    self.event.clear()
                    LOG.debug("Cleared wait event.")

            if self.paused and isinstance(self.paused, asyncio.Event) and self.is_paused():
                LOG.info("Download pool is paused.")
                await self.paused.wait()
                LOG.info("Download pool resumed downloading.")

            entry = self.queue.get_next_download()
            await asyncio.sleep(0.2)

            if entry is None:
                continue

            LOG.debug(f"Pushing {entry=} to executor.")

            if entry.started() is False and entry.is_cancelled() is False:
                await self.pool.push(is_temp=entry.is_live, id=entry.info._id, entry=entry)
                LOG.debug(f"Pushed {entry=} to executor.")
                await asyncio.sleep(1)

    async def _download_file(self, id: str, entry: Download) -> None:
        """
        Download the file.

        Args:
            id (str): The id of the download.
            entry (Download): The download entry.

        Returns:
            None

        """
        filePath = calc_download_path(base_path=self.config.download_path, folder=entry.info.folder)
        LOG.info(f"Downloading 'id: {id}', 'Title: {entry.info.title}', 'URL: {entry.info.url}' To '{filePath}'.")

        try:
            self._active[entry.info._id] = entry
            await entry.start()

            if "finished" != entry.info.status:
                entry.info.status = "error"
        finally:
            if entry.info._id in self._active:
                self._active.pop(entry.info._id, None)

            await entry.close()

        if self.queue.exists(key=id):
            LOG.debug(f"Download '{id}' is done. Removing from queue.")
            self.queue.delete(key=id)

            if entry.is_cancelled() is True:
                await self._notify.emit(Events.CANCELLED, data=entry.info.serialize())
                entry.info.status = "cancelled"
                entry.info.error = "Cancelled by user."

            self.done.put(value=entry)
            await self._notify.emit(Events.COMPLETED, data=entry.info.serialize())
        else:
            LOG.warning(f"Download '{id}' not found in queue.")

        if self.event:
            self.event.set()

    def _is_downloaded(self, url: str, file: str | None = None) -> tuple[bool, dict | None]:
        """
        Check if the url has been downloaded already.

        Args:
            url (str): The url to check.
            file (str | None): The archive file to check.

        Returns:
            tuple: A tuple with the status of the operation and the id of the downloaded item.

        """
        if not url or not file:
            return False, None

        return is_downloaded(file, url)

    async def _check_for_stale(self):
        """
        Monitor pool for stale downloads and cancel them if needed.
        """
        if self.is_paused():
            return

        if not self.queue.empty():
            LOG.debug("Checking for stale items in the download queue.")
            for _id, item in list(self.queue.items()):
                item_ref = f"{_id=} {item.info.id=} {item.info.title=}"
                if not item.is_stale():
                    LOG.debug(f"Item '{item_ref}' is not stale.")
                    continue

                LOG.warning(f"Cancelling staled item '{item_ref}' from download queue.")
                try:
                    await self.cancel([_id])
                except Exception as e:
                    LOG.error(f"Failed to cancel staled item '{item_ref}'. {e!s}")
                    LOG.exception(e)

        if self.pool:
            time_now = datetime.now(tz=UTC)
            workers = self.pool.get_workers_status()
            if len(workers) > 0:
                LOG.debug(f"Checking for stale workers. {len(workers)} workers found.")

            for worker_id in workers:
                worker = workers.get(worker_id, {})
                if not worker:
                    continue

                started = worker.get("started", None)
                if not started:
                    LOG.debug(f"Worker '{worker_id}' not working yet.")
                    continue

                started = datetime.fromisoformat(started)

                if time_now - started < timedelta(minutes=5):
                    LOG.debug(f"Worker '{worker_id}' is not consider stale yet.")
                    continue

                data = worker.get("data", {})

                status = data.get("status", None)
                if "preparing" != status:
                    LOG.debug(f"Worker '{worker_id}' not stuck. Status '{status}'.")
                    continue

                _id = data.get("data._id", None)
                if not _id:
                    LOG.debug(f"Worker '{worker_id}' has no id.")
                    continue

                id = data.get("id", None)
                title = data.get("title", None)

                item_ref = f"{_id=} {id=} {title=}"

                LOG.warning(f"Cancelling staled item '{item_ref}' from worker pool.")
                try:
                    await self.cancel([_id])
                except Exception as e:
                    LOG.error(f"Failed to cancel staled item '{item_ref}' from worker pool. {e!s}")
                    LOG.exception(e)

    async def _check_live(self):
        """
        Monitor the queue for items marked as live events and queue them when time is reached.
        """
        if self.is_paused() or self.done.empty():
            return

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

            LOG.info(f"Re-queuing item '{item_ref} {item.info.extras=}' for download.")

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
                LOG.error(f"Failed to re-queue item '{item_ref}'. {e!s}")
