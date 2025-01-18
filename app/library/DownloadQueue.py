import asyncio
import datetime
import json
import logging
import os
import time
from email.utils import formatdate
from sqlite3 import Connection

import yt_dlp

from .AsyncPool import AsyncPool
from .config import Config
from .DataStore import DataStore
from .Download import Download
from .Emitter import Emitter
from .ItemDTO import ItemDTO
from .Utils import ExtractInfo, get_opts, calcDownloadPath, isDownloaded, mergeConfig

LOG = logging.getLogger("DownloadQueue")
TYPE_DONE: str = "done"
TYPE_QUEUE: str = "queue"


class DownloadQueue:
    paused: asyncio.Event
    event: asyncio.Event | None = None
    pool: AsyncPool | None = None

    def __init__(self, emitter: Emitter, connection: Connection):
        self.config = Config.get_instance()
        self.emitter = emitter
        self.done = DataStore(type=TYPE_DONE, connection=connection)
        self.queue = DataStore(type=TYPE_QUEUE, connection=connection)
        self.done.load()
        self.queue.load()
        self.paused = asyncio.Event()
        self.paused.set()

    async def test(self) -> bool:
        await self.done.test()
        return True

    async def initialize(self):
        self.event = asyncio.Event()
        LOG.info(
            f"Using '{self.config.max_workers}' worker/s for downloading. Can be configured via `YTP_MAX_WORKERS` environment variable."
        )
        asyncio.create_task(self.__download_pool(), name="download_pool")

    def pause(self):
        if self.paused.is_set():
            self.paused.clear()
            LOG.warning(f"Download paused at. {datetime.datetime.now().isoformat()}")

    def resume(self):
        if not self.paused.is_set():
            self.paused.set()
            LOG.warning(f"Downloading resumed at. {datetime.datetime.now().isoformat()}")

    def isPaused(self) -> bool:
        return False if self.paused.is_set() else True

    async def __add_entry(
        self,
        entry: dict,
        preset: str,
        folder: str,
        ytdlp_config: dict = {},
        ytdlp_cookies: str = "",
        output_template: str = "",
        already=None,
    ):
        if not entry:
            return {"status": "error", "msg": "Invalid/empty data was given."}

        options: dict = {}

        error: str | None = None
        live_in: str | None = None

        eventType = entry.get("_type") or "video"
        if eventType == "playlist":
            entries = entry["entries"]
            playlist_index_digits = len(str(len(entries)))
            results = []
            for i, etr in enumerate(entries, start=1):
                etr["playlist"] = entry.get("id")
                etr["playlist_index"] = "{{0:0{0:d}d}}".format(playlist_index_digits).format(i)
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
                        ytdlp_config=ytdlp_config,
                        ytdlp_cookies=ytdlp_cookies,
                        output_template=output_template,
                        already=already,
                    )
                )

            if any(res["status"] == "error" for res in results):
                return {
                    "status": "error",
                    "msg": ", ".join(res["msg"] for res in results if res["status"] == "error" and "msg" in res),
                }

            return {"status": "ok"}
        elif (eventType == "video" or eventType.startswith("url")) and "id" in entry and "title" in entry:
            # check if the video is live stream.
            if "live_status" in entry and entry.get("live_status") == "is_upcoming":
                if "release_timestamp" in entry and entry.get("release_timestamp"):
                    live_in = formatdate(entry.get("release_timestamp"))
                else:
                    error = "Live stream not yet started. And no date is set."
            else:
                error = entry.get("msg", None)

            LOG.debug(
                f"Entry id '{entry.get('id', None)}' url '{entry.get('webpage_url', None)} - {entry.get('url', None)}'."
            )

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
            is_live = bool(entry.get("is_live", None) or live_in or entry.get("live_status", None) in live_status)

            try:
                download_dir = calcDownloadPath(basePath=self.config.download_path, folder=folder)
            except Exception as e:
                LOG.exception(e)
                return {"status": "error", "msg": str(e)}

            extras: dict = {}
            fields: tuple = ("uploader", "channel", "thumbnail")
            for field in fields:
                if entry.get(field, None):
                    extras[field] = entry.get(field)

            dl = ItemDTO(
                id=str(entry.get("id")),
                title=str(entry.get("title")),
                url=str(entry.get("webpage_url") or entry.get("url")),
                preset=preset,
                thumbnail=entry.get("thumbnail", None),
                folder=folder,
                download_dir=download_dir,
                temp_dir=self.config.temp_path,
                ytdlp_cookies=ytdlp_cookies,
                ytdlp_config=ytdlp_config,
                output_template=output_template if output_template else self.config.output_template,
                output_template_chapter=self.config.output_template_chapter,
                datetime=formatdate(time.time()),
                error=error,
                is_live=is_live,
                live_in=live_in,
                options=options,
                extras=extras,
            )

            for property, value in entry.items():
                if property.startswith("playlist"):
                    dl.output_template = str(dl.output_template).replace(f"%({property})s", str(value))

            dlInfo: Download = Download(info=dl, info_dict=entry, debug=bool(self.config.ytdl_debug))

            if dlInfo.info.live_in or "is_upcoming" == entry.get("live_status", None):
                dlInfo.info.status = "not_live"
                itemDownload = self.done.put(dlInfo)
                NotifyEvent = "completed"
            elif self.config.allow_manifestless is False and is_manifestless is True:
                dlInfo.info.status = "error"
                dlInfo.info.error = "Video is in post-live manifestless mode."
                itemDownload = self.done.put(dlInfo)
                NotifyEvent = "completed"
            else:
                NotifyEvent = "added"
                itemDownload = self.queue.put(dlInfo)
                if self.event:
                    self.event.set()

            asyncio.create_task(
                self.emitter.emit(NotifyEvent, itemDownload.info), name=f"notifier-{NotifyEvent}-{itemDownload.info.id}"
            )

            return {"status": "ok"}
        elif eventType.startswith("url"):
            return await self.add(
                url=str(entry.get("url")),
                preset=preset,
                folder=folder,
                ytdlp_config=ytdlp_config,
                ytdlp_cookies=ytdlp_cookies,
                output_template=output_template,
                already=already,
            )

        return {"status": "error", "msg": f'Unsupported resource "{eventType}"'}

    async def add(
        self,
        url: str,
        preset: str,
        folder: str,
        ytdlp_config: dict = {},
        ytdlp_cookies: str = "",
        output_template: str = "",
        already=None,
    ):
        ytdlp_config = ytdlp_config if ytdlp_config else {}
        folder = str(folder)

        LOG.info(
            f"Adding url '{url}' to folder '{folder}' with the following options 'Preset: {preset}' 'Naming: {output_template}', 'Cookies: {ytdlp_cookies}' 'YTConfig: {ytdlp_config}'."
        )

        if isinstance(ytdlp_config, str):
            try:
                ytdlp_config = json.loads(ytdlp_config)
            except Exception as e:
                LOG.error(f"Unable to load '{ytdlp_config=}'. {str(e)}")
                return {"status": "error", "msg": f"Failed to parse json yt-dlp config. {str(e)}"}

        already = set() if already is None else already

        if url in already:
            LOG.warning(f"Recursion detected with url '{url}' skipping.")
            return {"status": "ok"}

        already.add(url)

        try:
            downloaded, id_dict = self.isDownloaded(url)
            if downloaded is True and id_dict:
                message = f"This url with ID '{id_dict.get('id')}' has been downloaded already and recorded in archive."
                LOG.info(message)
                return {"status": "error", "msg": message}

            started = time.perf_counter()
            LOG.debug(f"extract_info: checking {url=}")

            entry = await asyncio.wait_for(
                fut=asyncio.get_running_loop().run_in_executor(
                    None,
                    ExtractInfo,
                    get_opts(preset, mergeConfig(self.config.ytdl_options, ytdlp_config)),
                    url,
                    bool(self.config.ytdl_debug),
                ),
                timeout=self.config.extract_info_timeout,
            )

            if not entry:
                return {"status": "error", "msg": "Unable to extract info check logs."}

            LOG.debug(
                f"extract_info: for 'URL: {url}' is done in '{time.perf_counter() - started}'. Length: '{len(entry)}'."
            )
        except yt_dlp.utils.ExistingVideoReached as exc:
            LOG.error(f"Video has been downloaded already and recorded in archive.log file. {str(exc)}")
            return {"status": "error", "msg": "Video has been downloaded already and recorded in archive.log file."}
        except yt_dlp.utils.YoutubeDLError as exc:
            LOG.error(f"YoutubeDLError: Unable to extract info. {str(exc)}")
            return {"status": "error", "msg": str(exc)}
        except asyncio.exceptions.TimeoutError as exc:
            LOG.error(f"TimeoutError: Unable to extract info. {str(exc)}")
            return {
                "status": "error",
                "msg": f"TimeoutError: {self.config.extract_info_timeout}s reached Unable to extract info.",
            }

        return await self.__add_entry(
            entry=entry,
            preset=preset,
            folder=folder,
            ytdlp_config=ytdlp_config,
            ytdlp_cookies=ytdlp_cookies,
            output_template=output_template,
            already=already,
        )

    async def cancel(self, ids: list[str]) -> dict[str, str]:
        status: dict[str, str] = {"status": "ok"}

        for id in ids:
            try:
                item = self.queue.get(key=id)
            except KeyError as e:
                status[id] = str(e)
                status["status"] = "error"
                LOG.warning(f"Requested cancel for non-existent download {id=}. {str(e)}")
                continue

            itemMessage = f"{id=} {item.info.id=} {item.info.title=}"

            if item.running():
                LOG.debug(f"Canceling {itemMessage}")
                item.cancel()
                LOG.info(f"Cancelled {itemMessage}")
                await item.close()
            else:
                await item.close()
                LOG.debug(f"Deleting from queue {itemMessage}")
                self.queue.delete(id)
                asyncio.create_task(self.emitter.canceled(id=id, dl=item.info.serialize()), name=f"notifier-c-{id}")
                item.info.status = "canceled"
                item.info.error = "Canceled by user."
                self.done.put(item)
                asyncio.create_task(self.emitter.completed(dl=item.info.serialize()), name=f"notifier-d-{id}")
                LOG.info(f"Deleted from queue {itemMessage}")

            status[id] = "ok"

        return status

    async def clear(self, ids: list[str], remove_file: bool = False) -> dict[str, str]:
        status: dict[str, str] = {"status": "ok"}

        for id in ids:
            try:
                item = self.done.get(key=id)
            except KeyError as e:
                status[id] = str(e)
                status["status"] = "error"
                LOG.warning(f"Requested delete for non-existent download {id=}. {str(e)}")
                continue

            itemRef: str = f"{id=} {item.info.id=} {item.info.title=}"
            fileDeleted: bool = False
            filename: str = ""

            if remove_file and self.config.remove_files and "finished" == item.info.status:
                filename = str(item.info.filename)
                if item.info.folder:
                    filename = f"{item.info.folder}/{item.info.filename}"

                try:
                    realFile: str = calcDownloadPath(
                        basePath=self.config.download_path,
                        folder=filename,
                        createPath=False,
                    )
                    if realFile and os.path.exists(realFile):
                        os.remove(realFile)
                        fileDeleted = True
                    else:
                        LOG.warning(f"File '{filename}' does not exist.")
                except Exception as e:
                    LOG.error(f"Unable to remove '{itemRef}' local file '{filename}'. {str(e)}")

            self.done.delete(id)
            asyncio.create_task(self.emitter.cleared(id, dl=item.info.serialize()), name=f"notifier-c-{id}")
            msg = f"Deleted completed download '{itemRef}'."
            if fileDeleted and filename:
                msg += f" and removed local file '{filename}'."

            LOG.info(msg=msg)
            status[id] = "ok"

        return status

    def get(self) -> dict[str, list[dict[str, ItemDTO]]]:
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

    async def __download_pool(self):
        self.pool = AsyncPool(
            loop=asyncio.get_running_loop(),
            num_workers=self.config.max_workers,
            worker_co=self.__downloadFile,
            name="download_pool",
            logger=logging.getLogger("WorkerPool"),
        )

        self.pool.start()

        lastLog = time.time()

        while True:
            while True:
                if self.pool.has_open_workers() is True:
                    break
                if self.config.max_workers > 1 and time.time() - lastLog > 120:
                    lastLog = time.time()
                    LOG.info(f"Waiting for worker to be free. {self.pool.get_workers_status()}")
                await asyncio.sleep(1)

            while not self.queue.hasDownloads():
                LOG.info(f"Waiting for item to download. '{self.pool.get_available_workers()}' free workers.")
                if self.event:
                    await self.event.wait()
                    self.event.clear()
                    LOG.debug("Cleared wait event.")

            if self.paused and isinstance(self.paused, asyncio.Event):
                LOG.info("Download pool is paused.")
                await self.paused.wait()
                LOG.info("Download pool resumed downloading.")

            entry = self.queue.getNextDownload()
            await asyncio.sleep(0.2)

            if entry is None:
                continue

            LOG.debug(f"Pushing {entry=} to executor.")

            if entry.started() is False and entry.is_canceled() is False:
                await self.pool.push(id=entry.info._id, entry=entry)
                LOG.debug(f"Pushed {entry=} to executor.")
                await asyncio.sleep(1)

    async def __downloadFile(self, id: str, entry: Download):
        LOG.info(
            f"Downloading 'id: {id}', 'Title: {entry.info.title}', 'URL: {entry.info.url}' to 'folder: {entry.info.folder}'."
        )

        try:
            await entry.start(self.emitter)

            if entry.info.status != "finished":
                if entry.tmpfilename and os.path.isfile(entry.tmpfilename):
                    try:
                        os.remove(entry.tmpfilename)
                        entry.tmpfilename = None
                    except Exception:
                        pass

                entry.info.status = "error"
        finally:
            await entry.close()

        if self.queue.exists(key=id):
            self.queue.delete(key=id)

            if entry.is_canceled() is True:
                asyncio.create_task(self.emitter.canceled(id, dl=entry.info.serialize()), name=f"notifier-c-{id}")
                entry.info.status = "canceled"
                entry.info.error = "Canceled by user."

            self.done.put(value=entry)
            asyncio.create_task(self.emitter.completed(dl=entry.info.serialize()), name=f"notifier-d-{id}")

        if self.event:
            self.event.set()

    def isDownloaded(self, url: str) -> tuple[bool, dict | None]:
        if not url or not self.config.keep_archive:
            return False, None

        return isDownloaded(self.config.ytdl_options.get("download_archive", None), url)
