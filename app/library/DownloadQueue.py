import asyncio
import functools
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from email.utils import formatdate
from sqlite3 import Connection

import anyio
import yt_dlp
from aiohttp import web

from .AsyncPool import AsyncPool
from .config import Config
from .DataStore import DataStore
from .Download import Download
from .Events import EventBus, Events
from .ItemDTO import ItemDTO
from .Presets import Presets
from .Singleton import Singleton
from .Utils import calc_download_path, extract_info, is_downloaded
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

    async def __add_entry(
        self,
        entry: dict,
        preset: str,
        folder: str,
        config: dict | None = None,
        cookies: str = "",
        template: str = "",
        already=None,
    ):
        """
        Add an entry to the download queue.

        Args:
            entry (dict): The entry to add to the download queue.
            preset (str): The preset to use for the download.
            folder (str): The folder to save the download to.
            config (dict): The yt-dlp configuration to use for the download.
            cookies (str): The cookies to use for the download.
            template (str): The output template to use for the download.
            already (set): The set of already downloaded items.

        Returns:
            dict: The status of the operation.

        """
        if not config:
            config = {}

        if not entry:
            return {"status": "error", "msg": "Invalid/empty data was given."}

        options: dict = {}

        error: str | None = None
        live_in: str | None = None

        eventType = entry.get("_type") or "video"

        if "playlist" == eventType:
            entries = entry.get("entries", [])
            playlist_index_digits = len(str(len(entries)))
            results = []
            for i, etr in enumerate(entries, start=1):
                etr["playlist"] = entry.get("id")
                etr["playlist_index"] = f"{{0:0{playlist_index_digits:d}d}}".format(i)
                for property in ("id", "title", "uploader", "uploader_id"):
                    if property in entry:
                        etr[f"playlist_{property}"] = entry.get(property)

                if "thumbnail" not in etr and "youtube:" in entry.get("extractor", ""):
                    etr["thumbnail"] = f"https://img.youtube.com/vi/{etr['id']}/maxresdefault.jpg"

                results.append(
                    await self.__add_entry(
                        entry=etr,
                        preset=preset,
                        folder=folder,
                        config=config,
                        cookies=cookies,
                        template=template,
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

            if self.done.exists(key=entry["id"], url=str(entry.get("webpage_url") or entry.get("url"))):
                item = self.done.get(key=entry["id"], url=entry.get("webpage_url") or entry["url"])
                LOG.warning(f"Item '{item.info.id}' - '{item.info.title}' already downloaded. Removing from history.")
                await self.clear([item.info._id], remove_file=False)

            try:
                item = self.queue.get(key=str(entry.get("id")), url=str(entry.get("webpage_url") or entry.get("url")))
                if item is not None:
                    err_message = f"Item ID '{item.info.id}' - '{item.info.title}' already in download queue."
                    LOG.info(err_message)
                    return {"status": "error", "msg": err_message}
            except KeyError:
                pass

            is_manifestless = entry.get("is_manifestless", False)
            options.update({"is_manifestless": is_manifestless})

            live_status: list = ["is_live", "is_upcoming"]
            is_live = bool(entry.get("is_live") or live_in or entry.get("live_status") in live_status)

            try:
                download_dir = calc_download_path(base_path=self.config.download_path, folder=folder)
            except Exception as e:
                LOG.exception(e)
                return {"status": "error", "msg": str(e)}

            extras: dict = {}
            fields: tuple = ("uploader", "channel", "thumbnail")
            for field in fields:
                if entry.get(field):
                    extras[field] = entry.get(field)

            dl = ItemDTO(
                id=str(entry.get("id")),
                title=str(entry.get("title")),
                url=str(entry.get("webpage_url") or entry.get("url")),
                preset=preset,
                folder=folder,
                download_dir=download_dir,
                temp_dir=self.config.temp_path,
                cookies=cookies,
                config=config,
                template=template if template else self.config.output_template,
                template_chapter=self.config.output_template_chapter,
                datetime=formatdate(time.time()),
                error=error,
                is_live=is_live,
                live_in=live_in,
                options=options,
                extras=extras,
            )

            for property, value in entry.items():
                if property.startswith("playlist"):
                    dl.template = str(dl.template).replace(f"%({property})s", str(value))

            dlInfo: Download = Download(info=dl, info_dict=entry)

            if dlInfo.info.live_in or "is_upcoming" == entry.get("live_status"):
                dlInfo.info.status = "not_live"
                itemDownload = self.done.put(dlInfo)
                NotifyEvent = Events.COMPLETED
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

        if eventType.startswith("url"):
            return await self.add(
                url=str(entry.get("url")),
                preset=preset,
                folder=folder,
                config=config,
                cookies=cookies,
                template=template,
                already=already,
            )

        return {"status": "error", "msg": f'Unsupported resource "{eventType}"'}

    async def add(
        self,
        url: str,
        preset: str,
        folder: str,
        config: dict | None = None,
        cookies: str = "",
        template: str = "",
        already=None,
    ):
        _preset = Presets.get_instance().get(name=preset)

        config = config if config else {}
        folder = str(folder) if folder else ""

        if _preset:
            if _preset.folder and not folder:
                folder = _preset.folder

            if _preset.template and not template:
                template = _preset.template

            if _preset.cookies and not cookies:
                cookies = _preset.cookies

        filePath = calc_download_path(base_path=self.config.download_path, folder=folder)
        yt_conf = {}
        cookie_file = os.path.join(self.config.temp_path, f"c_{uuid.uuid4().hex}.txt")

        LOG.info(
            f"Adding 'URL: {url}' to 'Folder: {filePath}' with 'Preset: {preset}' 'Naming: {template}', 'Cookies: {len(cookies)}/chars' 'YTConfig: {config}'."
        )

        if isinstance(config, str):
            try:
                config = json.loads(config)
            except Exception as e:
                LOG.error(f"Unable to load '{config=}'. {e!s}")
                return {"status": "error", "msg": f"Failed to parse json yt-dlp config. {e!s}"}

        already = set() if already is None else already

        if url in already:
            LOG.warning(f"Recursion detected with url '{url}' skipping.")
            return {"status": "ok"}

        already.add(url)

        try:
            downloaded, id_dict = self._is_downloaded(url)
            if downloaded is True and id_dict:
                message = f"This url with ID '{id_dict.get('id')}' has been downloaded already and recorded in archive."
                LOG.info(message)
                return {"status": "error", "msg": message}

            started = time.perf_counter()
            LOG.debug(f"extract_info: checking {url=}")

            logs = []

            yt_conf = {
                "callback": {
                    "func": lambda _, msg: logs.append(msg),
                    "level": logging.WARNING,
                },
                **YTDLPOpts.get_instance().preset(name=preset).add(config=config, from_user=True).get_all(),
            }

            if cookies:
                try:
                    async with await anyio.open_file(cookie_file, "w") as f:
                        await f.write(cookies)
                        yt_conf["cookiefile"] = f.name
                except ValueError as e:
                    LOG.error(f"Failed to create cookie file for '{self.info.id}: {self.info.title}'. '{e!s}'.")

            entry = await asyncio.wait_for(
                fut=asyncio.get_running_loop().run_in_executor(
                    None,
                    functools.partial(
                        extract_info,
                        config=yt_conf,
                        url=url,
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
                f"extract_info: for 'URL: {url}' is done in '{time.perf_counter() - started}'. Length: '{len(entry)}'."
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

        return await self.__add_entry(
            entry=entry,
            preset=preset,
            folder=folder,
            config=config,
            cookies=cookies,
            template=template,
            already=already,
        )

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
                await self._notify.emit(Events.CANCELLED, info=item.info.serialize())
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
            fileDeleted: bool = False
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
                    if realFile and os.path.exists(realFile):
                        os.remove(realFile)
                        fileDeleted = True
                    else:
                        LOG.warning(f"Failed to remove '{itemRef}' local file '{filename}'. File not found.")
                except Exception as e:
                    LOG.error(f"Unable to remove '{itemRef}' local file '{filename}'. {e!s}")

            self.done.delete(id)
            await self._notify.emit(Events.CLEARED, data=item.info.serialize())

            msg = f"Deleted completed download '{itemRef}'."
            if fileDeleted and filename:
                msg += f" and removed local file '{filename}'."

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

    def _is_downloaded(self, url: str) -> tuple[bool, dict | None]:
        """
        Check if the url has been downloaded already.

        Args:
            url (str): The url to check.

        Returns:
            tuple: A tuple with the status of the operation and the id of the downloaded item.

        """
        if not url or not self.config.keep_archive:
            return False, None

        return is_downloaded(self.config.ytdl_options.get("download_archive", None), url)
