import asyncio
import hashlib
import logging
import multiprocessing
import os
import shutil
import time
from email.utils import formatdate

import yt_dlp

from .AsyncPool import Terminator
from .config import Config
from .Emitter import Emitter
from .ffprobe import ffprobe
from .ItemDTO import ItemDTO
from .YTDLPOpts import YTDLPOpts

LOG = logging.getLogger("download")


class Download:
    """
    Download task.
    """

    id: str = None
    download_dir: str = None
    temp_dir: str = None
    template: str = None
    template_chapter: str = None
    ytdl_opts: dict = None
    info: ItemDTO = None
    default_ytdl_opts: dict = None
    debug: bool = False
    temp_path: str = None
    emitter: Emitter = None
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

    def __init__(self, info: ItemDTO, info_dict: dict = None, debug: bool = False):
        config = Config.get_instance()

        self.download_dir = info.download_dir
        self.temp_dir = info.temp_dir
        self.template = info.template
        self.template_chapter = info.template_chapter
        self.preset = info.preset
        self.ytdl_opts = info.config if info.config else {}
        self.info = info
        self.id = info._id
        self.default_ytdl_opts = config.ytdl_options
        self.debug = debug
        self.cancelled = False
        self.tmpfilename = None
        self.status_queue = None
        self.proc = None
        self.emitter = None
        self.max_workers = int(config.max_workers)
        self.temp_keep = bool(config.temp_keep)
        self.is_live = bool(info.is_live) or info.live_in is not None
        self.is_manifestless = "is_manifestless" in self.info.options and self.info.options["is_manifestless"] is True
        self.info_dict = info_dict

    def _progress_hook(self, data: dict):
        dataDict = {k: v for k, v in data.items() if k in self._ytdlp_fields}

        if "finished" == data.get("status") and data.get("info_dict", {}).get("filename", None):
            dataDict["filename"] = data["info_dict"]["filename"]

        self.status_queue.put({"id": self.id, **dataDict})

    def _postprocessor_hook(self, data: dict):
        if "MoveFiles" != data.get("postprocessor") or "finished" != data.get("status"):
            return

        if self.debug:
            LOG.debug(f"Postprocessor hook: {data}")

        if "__finaldir" in data["info_dict"]:
            filename = os.path.join(data["info_dict"]["__finaldir"], os.path.basename(data["info_dict"]["filepath"]))
        else:
            filename = data["info_dict"]["filepath"]

        self.status_queue.put({"id": self.id, "status": "finished", "filename": filename})

    def _download(self):
        try:
            params = (
                YTDLPOpts.get_instance()
                .preset(self.preset)
                .add(self.ytdl_opts, from_user=True)
                .add(
                    {
                        "color": "no_color",
                        "paths": {"home": self.download_dir, "temp": self.temp_path},
                        "outtmpl": {"default": self.template, "chapter": self.template_chapter},
                        "noprogress": True,
                        "break_on_existing": True,
                        "ignoreerrors": False,
                    },
                    from_user=False,
                )
                .get_all()
            )

            params.update(
                {
                    "progress_hooks": [self._progress_hook],
                    "postprocessor_hooks": [self._postprocessor_hook],
                }
            )

            if self.debug:
                params["verbose"] = True
                params["noprogress"] = False

            if self.info.cookies:
                try:
                    cookie_file = os.path.join(self.temp_path, f"cookie_{self.info._id}.txt")
                    LOG.debug(f"Creating cookie file for '{self.info.id}: {self.info.title}' - '{cookie_file}'.")
                    with open(cookie_file, "w") as f:
                        f.write(self.info.cookies)
                        params["cookiefile"] = f.name
                except ValueError as e:
                    LOG.error(f"Failed to create cookie file for '{self.info.id}: {self.info.title}'. '{e!s}'.")

            if self.is_live or self.is_manifestless:
                hasDeletedOptions = False
                deletedOpts: list = []
                for opt in self.bad_live_options:
                    if opt in params:
                        params.pop(opt, None)
                        hasDeletedOptions = True
                        deletedOpts.append(opt)

                if hasDeletedOptions:
                    LOG.warning(
                        f"Live stream detected for '{self.info.title}', The following opts '{deletedOpts=}' have been deleted which are known to cause issues with live stream and post stream manifestless mode."
                    )

            LOG.info(
                f'Task id="{self.info.id}" PID="{os.getpid()}" title="{self.info.title}" preset="{self.preset}" started.'
            )

            LOG.debug("Params before passing to yt-dlp.", extra=params)

            cls = yt_dlp.YoutubeDL(params=params)

            if isinstance(self.info_dict, dict) and len(self.info_dict) > 1:
                LOG.debug(f"Downloading '{self.info.url}' using pre-info.")
                cls.process_ie_result(self.info_dict, download=True)
                ret = cls._download_retcode
            else:
                LOG.debug(f"Downloading using url: {self.info.url}")
                ret = cls.download([self.info.url])

            self.status_queue.put({"id": self.id, "status": "finished" if ret == 0 else "error"})
        except Exception as exc:
            LOG.exception(exc)
            self.status_queue.put({"id": self.id, "status": "error", "msg": str(exc), "error": str(exc)})

        LOG.info(f'Task id="{self.info.id}" PID="{os.getpid()}" title="{self.info.title}" completed.')

    async def start(self, emitter: Emitter):
        self.emitter = emitter
        self.status_queue = Config.get_manager().Queue()

        # Create temp dir for each download.
        self.temp_path = os.path.join(self.temp_dir, hashlib.shake_256(f"D-{self.info.id}".encode()).hexdigest(5))

        if not os.path.exists(self.temp_path):
            os.makedirs(self.temp_path, exist_ok=True)

        self.proc = multiprocessing.Process(name=f"download-{self.id}", target=self._download)
        self.proc.start()
        self.info.status = "preparing"

        asyncio.create_task(self.emitter.updated(dl=self.info), name=f"emitter-{self.id}")
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

        LOG.info(f"Closing PID='{procId}' download process.")

        try:
            try:
                if "update_task" in self.__dict__ and self.update_task.done() is False:
                    self.update_task.cancel()
            except Exception as e:
                LOG.error(f"Failed to close status queue: '{procId}'. {e}")

            self.kill()

            loop = asyncio.get_running_loop()

            if self.proc.is_alive():
                LOG.debug(f"Waiting for PID='{procId}' to close.")
                await loop.run_in_executor(None, self.proc.join)
                LOG.debug(f"PID='{procId}' closed.")

            if self.status_queue:
                LOG.debug(f"Closing status queue for PID='{procId}'.")
                self.status_queue.put(Terminator())
                LOG.debug(f"Closed status queue for PID='{procId}'.")

            if self.proc:
                self.proc.close()
                self.proc = None

            self.delete_temp()

            LOG.debug(f"Closed PID='{procId}' download process.")

            return True
        except Exception as e:
            LOG.error(f"Failed to close process: '{procId}'. {e}")

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
            LOG.info(f"Killing download process: '{self.proc.ident}'.")
            self.proc.kill()
            return True
        except Exception as e:
            LOG.error(f"Failed to kill process: '{self.proc.ident}'. {e}")

        return False

    def delete_temp(self):
        if self.temp_keep is True or not self.temp_path:
            return

        if "finished" != self.info.status and self.is_live:
            LOG.warning(
                f"Keeping live temp folder '{self.temp_path}', as the reported status is not finished '{self.info.status}'."
            )
            return

        if not os.path.exists(self.temp_path):
            return

        if self.temp_path == self.temp_dir:
            LOG.warning(
                f"Attempted to delete video temp folder: {self.temp_path}, but it is the same as main temp folder."
            )
            return

        LOG.info(f"Deleting Temp folder '{self.temp_path}'.")
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
                LOG.debug(f"Status Update: {self.info._id=} {status=}")

            if isinstance(status, str):
                asyncio.create_task(self.emitter.updated(dl=self.info), name=f"emitter-u-{self.id}")
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
                asyncio.create_task(
                    self.emitter.error(message=self.info.error, data=self.info), name=f"emitter-e-{self.id}"
                )

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
                    LOG.exception(e)
                    LOG.error(f"Failed to ffprobe: {status.get}. {e}")

            asyncio.create_task(self.emitter.updated(dl=self.info), name=f"emitter-u-{self.id}")
