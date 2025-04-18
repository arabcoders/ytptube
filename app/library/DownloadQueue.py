import asyncio
import functools
import glob
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from email.utils import formatdate
from pathlib import Path
from sqlite3 import Connection

import anyio
import yt_dlp
from aiohttp import web

from .AsyncPool import AsyncPool
from .config import Config
from .DataStore import DataStore
from .Download import Download
from .Events import EventBus, Events, info
from .ItemDTO import Item, ItemDTO
from .Presets import Presets
from .Scheduler import Scheduler
from .Singleton import Singleton
from .Utils import arg_converter, calc_download_path, extract_info, is_downloaded, load_cookies
from .YTDLPOpts import YTDLPOpts

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

    _active_downloads: dict[str, Download] = {}

    _instance = None
    """Instance of the DownloadQueue."""

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
            func=self.monitor_queue_for_stale_items,
            id=f"{__class__.__name__}.monitor_queue_for_stale_items",
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
        if self._active_downloads:
            self.pause()
            try:
                await self.cancel(list(self._active_downloads.keys()))
            except Exception as e:
                LOG.error(f"Failed to cancel downloads. {e!s}")

    async def __add_entry(self, entry: dict, item: Item, already=None):
        """
        Add an entry to the download queue.

        Args:
            entry (dict): The entry to add to the download queue.
            item (Item): The item to add to the download queue.
            already (set): The set of already downloaded items.

        Returns:
            dict: The status of the operation.

        """
        if item.has_extras():
            for key in item.extras.copy():
                if not self.keep_extra_key(key):
                    item.extras.pop(key)

        if not entry:
            return {"status": "error", "msg": "Invalid/empty data was given."}

        options: dict = {}

        error: str | None = None
        live_in: str | None = None

        eventType = entry.get("_type") or "video"

        if "playlist" == eventType:
            LOG.info("Processing playlist")
            entries = entry.get("entries", [])
            playlistCount = int(entry.get("playlist_count", len(entries)))
            results = []

            for i, etr in enumerate(entries, start=1):
                etr["playlist"] = entry.get("id")
                etr["playlist_index"] = f"{{0:0{len(str(playlistCount)):d}d}}".format(i)
                etr["playlist_autonumber"] = i

                for property in ("id", "title", "uploader", "uploader_id"):
                    if property in entry:
                        etr[f"playlist_{property}"] = entry.get(property)

                if "thumbnail" not in etr and "youtube:" in entry.get("extractor", ""):
                    etr["thumbnail"] = f"https://img.youtube.com/vi/{etr['id']}/maxresdefault.jpg"

                results.append(
                    await self.__add_entry(
                        entry=etr,
                        item=item.new_with(url=etr.get("url") or etr.get("webpage_url")),
                        already=already,
                    )
                )

            if any("error" == res["status"] for res in results):
                return {
                    "status": "error",
                    "msg": ", ".join(res["msg"] for res in results if res["status"] == "error" and "msg" in res),
                }

            return {"status": "ok"}

        if ("video" == eventType or eventType.startswith("url")) and "id" in entry and "title" in entry:
            # check if the video is live stream.
            if "live_status" in entry and "is_upcoming" == entry.get("live_status"):
                if "release_timestamp" in entry and entry.get("release_timestamp"):
                    live_in = formatdate(entry.get("release_timestamp"))
                else:
                    error = "Live stream not yet started. And no date is set."
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

            is_manifestless = entry.get("is_manifestless", False)
            options.update({"is_manifestless": is_manifestless})

            live_status: list = ["is_live", "is_upcoming"]
            is_live = bool(entry.get("is_live") or live_in or entry.get("live_status") in live_status)

            try:
                download_dir = calc_download_path(base_path=self.config.download_path, folder=item.folder)
            except Exception as e:
                LOG.exception(e)
                return {"status": "error", "msg": str(e)}

            for field in ("uploader", "channel", "thumbnail"):
                if entry.get(field):
                    item.extras[field] = entry.get(field)

            for key in entry:
                if isinstance(key, str) and key.startswith("playlist") and entry.get(key):
                    item.extras[key] = entry.get(key)

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
                live_in=live_in,
                options=options,
                cli=item.cli,
                extras=item.extras,
            )

            try:
                dlInfo: Download = Download(info=dl, info_dict=entry)

                if dlInfo.info.live_in or "is_upcoming" == entry.get("live_status"):
                    dlInfo.info.status = "not_live"
                    itemDownload = self.done.put(dlInfo)
                    NotifyEvent = Events.COMPLETED
                    log_message = f"{dl.title or dl.id or dl._id}: stream is not live yet."
                    if dlInfo.info.live_in:
                        log_message += f" Will start in {dlInfo.info.live_in}."

                    await self._notify.emit(
                        Events.LOG_INFO,
                        data=info(msg=log_message, data=itemDownload.info.serialize()),
                    )
                elif self.config.allow_manifestless is False and is_manifestless is True:
                    dlInfo.info.status = "error"
                    dlInfo.info.error = "Video is in post-live manifestless mode."
                    itemDownload = self.done.put(dlInfo)
                    NotifyEvent = Events.COMPLETED
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

        if eventType.startswith("url"):
            return await self.add(item=item.new_with(url=entry.get("url")), already=already)

        return {"status": "error", "msg": f'Unsupported resource "{eventType}"'}

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
        _preset = Presets.get_instance().get(item.preset)

        if item.has_cli():
            try:
                arg_converter(args=item.cli, level=True)
            except Exception as e:
                LOG.error(f"Invalid cli options '{item.cli}'. {e!s}")
                return {"status": "error", "msg": f"Invalid cli options '{item.cli}'. {e!s}"}

        if _preset:
            if _preset.folder and not item.folder:
                item.folder = _preset.folder

            if _preset.template and not item.template:
                item.template = _preset.template

        yt_conf = {}
        cookie_file = os.path.join(self.config.temp_path, f"c_{uuid.uuid4().hex}.txt")

        LOG.info(f"Adding '{item.__repr__()}'.")

        already = set() if already is None else already

        if item.url in already:
            LOG.warning(f"Recursion detected with url '{item.url}' skipping.")
            return {"status": "ok"}

        already.add(item.url)

        try:
            logs = []

            yt_conf = {
                "callback": {
                    "func": lambda _, msg: logs.append(msg),
                    "level": logging.WARNING,
                },
                **YTDLPOpts.get_instance()
                .preset(name=item.preset, with_cookies=not item.cookies)
                .add_cli(args=item.cli, from_user=True)
                .get_all(),
            }

            if yt_conf.get("external_downloader"):
                LOG.warning(f"Using external downloader '{yt_conf.get('external_downloader')}' for '{item.url}'.")
                item.extras.update({"external_downloader": True})

            downloaded, id_dict = self._is_downloaded(file=yt_conf.get("download_archive", None), url=item.url)
            if downloaded is True and id_dict:
                message = f"This url with ID '{id_dict.get('id')}' has been downloaded already and recorded in archive."
                LOG.info(message)
                return {"status": "error", "msg": message}

            started = time.perf_counter()

            if item.cookies:
                try:
                    async with await anyio.open_file(cookie_file, "w") as f:
                        await f.write(item.cookies)
                        yt_conf["cookiefile"] = f.name

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

            LOG.debug(
                f"extract_info: for 'URL: {item.url}' is done in '{time.perf_counter() - started}'. Length: '{len(entry)}/keys'."
            )
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
            if cookie_file and os.path.exists(cookie_file):
                try:
                    os.remove(yt_conf["cookiefile"])
                    del yt_conf["cookiefile"]
                except Exception as e:
                    LOG.error(f"Failed to remove cookie file '{yt_conf['cookiefile']}'. {e!s}")

        return await self.__add_entry(entry=entry, item=item, already=already)

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
                item = self.done.get(key=id)
            except KeyError as e:
                status[id] = str(e)
                status["status"] = "error"
                LOG.warning(f"Requested delete for non-existent download {id=}. {e!s}")
                continue

            itemRef: str = f"{id=} {item.info.id=} {item.info.title=}"
            removed_files = 0
            filename: str = ""

            if remove_file and self.config.remove_files and "finished" == item.info.status:
                filename = str(item.info.filename)
                if item.info.folder:
                    filename = f"{item.info.folder}/{item.info.filename}"

                try:
                    realFile: str = calc_download_path(
                        base_path=self.config.download_path,
                        folder=filename,
                        create_path=False,
                    )
                    rf = Path(realFile)
                    if rf.is_file() and rf.exists():
                        for f in rf.parent.glob(f"{glob.escape(rf.stem)}.*"):
                            if f.is_file() and f.exists() and not f.name.startswith("."):
                                removed_files += 1
                                LOG.debug(f"Removing '{itemRef}' local file '{f.name}'.")
                                os.remove(f)
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
            items["queue"][k] = v

        for k, v in self.done.saved_items():
            items["done"][k] = v

        for k, v in self.queue.items():
            if k not in items["queue"]:
                items["queue"][k] = v.info

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
        LOG.info(
            f"Downloading 'id: {id}', 'Title: {entry.info.title}', 'URL: {entry.info.url}' to 'Folder: {filePath}'."
        )

        try:
            self._active_downloads[entry.info._id] = entry
            await entry.start()

            if "finished" != entry.info.status:
                if entry.tmpfilename and os.path.isfile(entry.tmpfilename):
                    try:
                        os.remove(entry.tmpfilename)
                        entry.tmpfilename = None
                    except Exception:
                        pass

                entry.info.status = "error"
        finally:
            if entry.info._id in self._active_downloads:
                self._active_downloads.pop(entry.info._id, None)

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

    def keep_extra_key(self, key: str) -> bool:
        """
        Check if the extra key should be kept.

        Args:
            key (str): The extra key to check.

        Returns:
            bool: True if the extra key should be kept, False otherwise.

        """
        keys = ("playlist", "external_downloader")
        return any(key == k or key.startswith(k) for k in keys)

    async def monitor_queue_for_stale_items(self):
        """
        Monitor the queue for stale items and cancel them if needed.
        """
        if self.is_paused() or not self.queue.has_downloads():
            return

        LOG.debug("Checking for stale items in the download queue.")
        for id, item in list(self.queue.items()):
            item_ref = f"{id=} {item.info.id=} {item.info.title=}"
            if not item.is_stale():
                LOG.debug(f"Item '{item_ref}' is not stale.")
                continue

            LOG.warning(f"Cancelling staled item '{item_ref}' from download queue.")
            try:
                await self.cancel([id])
            except Exception as e:
                LOG.error(f"Failed to cancel staled item '{item_ref}'. {e!s}")
