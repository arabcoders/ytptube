import asyncio
import hashlib
import logging
import multiprocessing
import os
import re
import shutil
import time
from email.utils import formatdate

import yt_dlp

from .AsyncPool import Terminator
from .config import Config
from .Events import EventBus, Events
from .ffprobe import ffprobe
from .ItemDTO import ItemDTO
from .Utils import extract_info
from .YTDLPOpts import YTDLPOpts

LOG = logging.getLogger("Download")


class NestedLogger:
    debug_messages = ["[debug] ", "[download] "]

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def debug(self, msg: str):
        levelno = logging.DEBUG if any(msg.startswith(x) for x in self.debug_messages) else logging.INFO
        self.logger.log(level=levelno, msg=re.sub(r"^\[(debug|info)\] ", "", msg, flags=re.IGNORECASE))

    def error(self, msg):
        self.logger.error(msg)

    def warning(self, msg):
        self.logger.warning(msg)


class Download:
    """
    Download task.
    """

    id: str = None
    download_dir: str = None
    temp_dir: str = None
    template: str = None
    template_chapter: str = None
    info: ItemDTO = None
    default_ytdl_opts: dict = None
    debug: bool = False
    temp_path: str = None
    cancelled: bool = False
    is_live: bool = False
    info_dict: dict = None
    "yt-dlp metadata dict."
    update_task = None

    cancel_in_progress: bool = False

    bad_live_options: list = [
        "concurrent_fragment_downloads",
        "fragment_retries",
        "skip_unavailable_fragments",
    ]
    "Bad yt-dlp options which are known to cause issues with live stream and post manifestless mode."

    _ytdlp_fields: tuple = (
        "tmpfilename",
        "filename",
        "status",
        "msg",
        "total_bytes",
        "total_bytes_estimate",
        "downloaded_bytes",
        "speed",
        "eta",
    )
    "Fields to be extracted from yt-dlp progress hook."

    temp_keep: bool = False
    "Keep temp folder after download."

    def __init__(self, info: ItemDTO, info_dict: dict = None):
        config = Config.get_instance()

        self.download_dir = info.download_dir
        self.temp_dir = info.temp_dir
        self.template = info.template
        self.template_chapter = info.template_chapter
        self.preset = info.preset
        self.info = info
        self.id = info._id
        self.default_ytdl_opts = config.ytdl_options
        self.debug = bool(config.debug)
        self.archive = bool(config.keep_archive)
        self.debug_ytdl = bool(config.ytdl_debug)
        self.cancelled = False
        self.tmpfilename = None
        self.status_queue = None
        self.proc = None
        self._notify = EventBus.get_instance()
        self.max_workers = int(config.max_workers)
        self.temp_keep = bool(config.temp_keep)
        self.is_live = bool(info.is_live) or info.live_in is not None
        self.is_manifestless = "is_manifestless" in self.info.options and self.info.options["is_manifestless"] is True
        self.info_dict = info_dict
        self.logger = logging.getLogger(f"Download.{info.id if info.id else info._id}")

    def _progress_hook(self, data: dict):
        dataDict = {k: v for k, v in data.items() if k in self._ytdlp_fields}

        if "finished" == data.get("status") and data.get("info_dict", {}).get("filename", None):
            dataDict["filename"] = data["info_dict"]["filename"]

        self.status_queue.put({"id": self.id, **dataDict})

    def _postprocessor_hook(self, data: dict):
        if self.debug:
            self.logger.debug(f"Postprocessor hook: {data}")

        if "MoveFiles" != data.get("postprocessor") or "finished" != data.get("status"):
            dataDict = {k: v for k, v in data.items() if k in self._ytdlp_fields}
            self.status_queue.put({"id": self.id, **dataDict, "status": "postprocessing"})
            return

        if "__finaldir" in data["info_dict"]:
            filename = os.path.join(data["info_dict"]["__finaldir"], os.path.basename(data["info_dict"]["filepath"]))
        else:
            filename = data["info_dict"]["filepath"]

        self.status_queue.put({"id": self.id, "status": "finished", "filename": filename})

    def post_hooks(self, filename: str | None = None):
        if not filename:
            return

        self.status_queue.put({"id": self.id, "filename": filename})

    def _download(self):
        try:
            params = (
                YTDLPOpts.get_instance()
                .preset(self.preset)
                .add({"break_on_existing": True})
                .add_cli(self.info.cli, from_user=True)
                .add(
                    {
                        "color": "no_color",
                        "paths": {
                            "home": self.download_dir,
                            "temp": self.temp_path,
                        },
                        "outtmpl": {
                            "default": self.template,
                            "chapter": self.template_chapter,
                        },
                        "noprogress": True,
                        "ignoreerrors": False,
                    },
                    from_user=False,
                )
                .get_all()
            )

            if not self.info_dict:
                self.logger.info(f"Extracting info for '{self.info.url}'.")
                info = extract_info(
                    config=params,
                    url=self.info.url,
                    debug=self.debug,
                    no_archive=not self.archive,
                    follow_redirect=True,
                )

                if info:
                    self.info_dict = info

            params.update(
                {
                    "progress_hooks": [self._progress_hook],
                    "postprocessor_hooks": [self._postprocessor_hook],
                    "post_hooks": [self.post_hooks],
                }
            )

            if self.debug_ytdl:
                params["verbose"] = True
                params["noprogress"] = False

            if self.info.cookies:
                try:
                    cookie_file = os.path.join(self.temp_path, f"cookie_{self.info._id}.txt")
                    self.logger.debug(
                        f"Creating cookie file for '{self.info.id}: {self.info.title}' - '{cookie_file}'."
                    )
                    with open(cookie_file, "w") as f:
                        f.write(self.info.cookies)
                        params["cookiefile"] = f.name
                except ValueError as e:
                    self.logger.error(f"Failed to create cookie file for '{self.info.id}: {self.info.title}'. '{e!s}'.")

            if self.is_live or self.is_manifestless:
                hasDeletedOptions = False
                deletedOpts: list = []
                for opt in self.bad_live_options:
                    if opt in params:
                        params.pop(opt, None)
                        hasDeletedOptions = True
                        deletedOpts.append(opt)

                if hasDeletedOptions:
                    self.logger.warning(
                        f"Live stream detected for '{self.info.title}', The following opts '{deletedOpts=}' have been deleted which are known to cause issues with live stream and post stream manifestless mode."
                    )

            self.logger.info(
                f'Task id="{self.info.id}" PID="{os.getpid()}" title="{self.info.title}" preset="{self.preset}" started.'
            )

            self.logger.debug(f"Params before passing to yt-dlp. {params}")

            params["logger"] = NestedLogger(self.logger)

            cls = yt_dlp.YoutubeDL(params=params)

            if isinstance(self.info_dict, dict) and len(self.info_dict) > 1:
                self.logger.debug(f"Downloading '{self.info.url}' using pre-info.")
                cls.process_ie_result(
                    ie_result=self.info_dict,
                    download=True,
                    extra_info={k: v for k, v in self.info.extras.items() if k.startswith("playlist")},
                )
                ret = cls._download_retcode
            else:
                self.logger.debug(f"Downloading using url: {self.info.url}")
                ret = cls.download(url_list=[self.info.url])

            self.status_queue.put({"id": self.id, "status": "finished" if ret == 0 else "error"})
        except Exception as exc:
            self.logger.exception(exc)
            self.status_queue.put({"id": self.id, "status": "error", "msg": str(exc), "error": str(exc)})

        self.logger.info(f'Task id="{self.info.id}" PID="{os.getpid()}" title="{self.info.title}" completed.')

    async def start(self):
        self.status_queue = Config.get_manager().Queue()

        # Create temp dir for each download.
        self.temp_path = os.path.join(self.temp_dir, hashlib.shake_256(f"D-{self.info.id}".encode()).hexdigest(5))

        if not os.path.exists(self.temp_path):
            os.makedirs(self.temp_path, exist_ok=True)

        self.proc = multiprocessing.Process(name=f"download-{self.id}", target=self._download)
        self.proc.start()
        self.info.status = "preparing"

        await self._notify.emit(Events.UPDATED, data=self.info)
        asyncio.create_task(self.progress_update(), name=f"update-{self.id}")

        return await asyncio.get_running_loop().run_in_executor(None, self.proc.join)

    def started(self) -> bool:
        return self.proc is not None

    def cancel(self) -> bool:
        if not self.started():
            return False

        self.cancelled = True

        return True

    async def close(self) -> bool:
        """
        Close download process.
        This method MUST be called to clear resources.
        """
        if not self.started() or self.cancel_in_progress:
            return False

        self.cancel_in_progress = True
        procId = self.proc.ident

        self.logger.info(f"Closing PID='{procId}' download process.")

        try:
            try:
                if "update_task" in self.__dict__ and self.update_task.done() is False:
                    self.update_task.cancel()
            except Exception as e:
                self.logger.error(f"Failed to close status queue: '{procId}'. {e}")

            self.kill()

            loop = asyncio.get_running_loop()

            if self.proc.is_alive():
                self.logger.debug(f"Waiting for PID='{procId}' to close.")
                await loop.run_in_executor(None, self.proc.join)
                self.logger.debug(f"PID='{procId}' closed.")

            if self.status_queue:
                self.logger.debug(f"Closing status queue for PID='{procId}'.")
                self.status_queue.put(Terminator())
                self.logger.debug(f"Closed status queue for PID='{procId}'.")

            if self.proc:
                self.proc.close()
                self.proc = None

            self.delete_temp()

            self.logger.debug(f"Closed PID='{procId}' download process.")

            return True
        except Exception as e:
            self.logger.error(f"Failed to close process: '{procId}'. {e}")

        return False

    def running(self) -> bool:
        try:
            return self.proc is not None and self.proc.is_alive()
        except ValueError:
            return False

    def is_cancelled(self) -> bool:
        return self.cancelled

    def kill(self) -> bool:
        if not self.running():
            return False

        try:
            self.logger.info(f"Killing download process: '{self.proc.ident}'.")
            self.proc.kill()
            return True
        except Exception as e:
            self.logger.error(f"Failed to kill process: '{self.proc.ident}'. {e}")

        return False

    def delete_temp(self):
        if self.temp_keep is True or not self.temp_path:
            return

        if "finished" != self.info.status and self.is_live:
            self.logger.warning(
                f"Keeping live temp folder '{self.temp_path}', as the reported status is not finished '{self.info.status}'."
            )
            return

        if not os.path.exists(self.temp_path):
            return

        if self.temp_path == self.temp_dir:
            self.logger.warning(
                f"Attempted to delete video temp folder: {self.temp_path}, but it is the same as main temp folder."
            )
            return

        self.logger.info(f"Deleting Temp folder '{self.temp_path}'.")
        shutil.rmtree(self.temp_path, ignore_errors=True)

    async def progress_update(self):
        """
        Update status of download task and notify the client.
        """
        while True:
            try:
                self.update_task = asyncio.get_running_loop().run_in_executor(None, self.status_queue.get)
                status = await self.update_task
            except (asyncio.CancelledError, OSError, FileNotFoundError):
                return

            if status is None or isinstance(status, Terminator):
                return

            if status.get("id") != self.id or len(status) < 2:
                continue

            if self.debug:
                self.logger.debug(f"Status Update: {self.info._id=} {status=}")

            if isinstance(status, str):
                await self._notify.emit(Events.UPDATED, data=self.info)
                continue

            self.tmpfilename = status.get("tmpfilename")

            if "filename" in status:
                self.info.filename = os.path.relpath(status.get("filename"), self.download_dir)

                if os.path.exists(status.get("filename")):
                    try:
                        self.info.file_size = os.path.getsize(status.get("filename"))
                    except FileNotFoundError:
                        self.info.file_size = 0

            self.info.status = status.get("status", self.info.status)
            self.info.msg = status.get("msg")

            if "error" == self.info.status and "error" in status:
                self.info.error = status.get("error")
                await self._notify.emit(Events.ERROR, data={"message": self.info.error, "data": self.info})

            if "downloaded_bytes" in status:
                total = status.get("total_bytes") or status.get("total_bytes_estimate")
                if total:
                    try:
                        self.info.percent = status["downloaded_bytes"] / total * 100
                    except ZeroDivisionError:
                        self.info.percent = 0
                    self.info.total_bytes = total

            self.info.speed = status.get("speed")
            self.info.eta = status.get("eta")

            if (
                "finished" == self.info.status
                and "filename" in status
                and os.path.isfile(status.get("filename"))
                and os.path.exists(status.get("filename"))
            ):
                try:
                    self.info.file_size = os.path.getsize(status.get("filename"))
                    self.info.datetime = str(formatdate(time.time()))
                except FileNotFoundError:
                    pass

                try:
                    ff = await ffprobe(status.get("filename"))
                    self.info.extras["is_video"] = ff.has_video()
                    self.info.extras["is_audio"] = ff.has_audio()
                except Exception as e:
                    self.info.extras["is_video"] = True
                    self.info.extras["is_audio"] = True
                    self.logger.exception(e)
                    self.logger.error(f"Failed to ffprobe: {status.get}. {e}")

            await self._notify.emit(Events.UPDATED, data=self.info)
