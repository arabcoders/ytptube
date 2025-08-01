import asyncio
import hashlib
import logging
import multiprocessing
import os
import re
import signal
import time
from datetime import UTC, datetime
from email.utils import formatdate
from pathlib import Path

import yt_dlp.utils

from .config import Config
from .Events import EventBus, Events
from .ffprobe import ffprobe
from .ItemDTO import ItemDTO
from .Utils import delete_dir, extract_info, extract_ytdlp_logs, load_cookies
from .ytdlp import YTDLP
from .YTDLPOpts import YTDLPOpts


class Terminator:
    pass


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
    temp_disabled: bool = False
    "Disable the temporary files feature."
    template: str = None
    template_chapter: str = None
    info: ItemDTO = None
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
    "Bad yt-dlp options which are known to cause issues with live stream."

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

    logs: list = []
    "Logs from yt-dlp."

    def __init__(self, info: ItemDTO, info_dict: dict = None, logs: list | None = None):
        """
        Initialize download task.

        Args:
            info (ItemDTO): ItemDTO object.
            info_dict (dict): yt-dlp metadata dict.
            logs (list): Logs from yt-dlp.

        """
        config: Config = Config.get_instance()

        self.download_dir = info.download_dir
        self.temp_dir = info.temp_dir
        self.template = info.template
        self.template_chapter = info.template_chapter
        self.preset = info.preset
        self.info = info
        self.id = info._id
        self.debug = bool(config.debug)
        self.debug_ytdl = bool(config.ytdl_debug)
        self.cancelled = False
        self.tmpfilename = None
        self.status_queue = None
        self.proc = None
        self._notify = EventBus.get_instance()
        self.max_workers = int(config.max_workers)
        self.temp_keep = bool(config.temp_keep)
        self.temp_disabled = bool(config.temp_disabled)
        self.is_live = bool(info.is_live) or info.live_in is not None
        self.info_dict = info_dict
        self.logger = logging.getLogger(f"Download.{info.id if info.id else info._id}")
        self.started_time = 0
        self.queue_time = datetime.now(tz=UTC)
        self.logs = logs if logs else []

    def _progress_hook(self, data: dict):
        if self.debug:
            from copy import deepcopy

            d_copy = deepcopy(data)
            for k in ["formats", "thumbnails", "description", "tags", "_format_sort_fields"]:
                d_copy["info_dict"].pop(k, None)

            self.logger.debug(f"Progress hook: {d_copy}")

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
            filename = str(Path(data["info_dict"]["__finaldir"]) / Path(data["info_dict"]["filepath"]).name)
        else:
            filename = data["info_dict"]["filepath"]

        self.status_queue.put({"id": self.id, "status": "finished", "filename": filename})

    def post_hooks(self, filename: str | None = None):
        if not filename:
            return

        self.status_queue.put({"id": self.id, "filename": filename})

    def _download(self):
        if not self._notify:
            self._notify = EventBus.get_instance()

        cookie_file = None

        try:
            params: dict = (
                YTDLPOpts.get_instance()
                .preset(self.preset)
                .add({"break_on_existing": True})
                .add_cli(args=self.info.cli, from_user=True)
                .add(
                    config={
                        "color": "no_color",
                        "paths": {
                            "home": str(self.download_dir),
                            "temp": str(self.temp_path) if self.temp_path else self.download_dir,
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
                    cookie_file: Path = (
                        Path(self.temp_path if self.temp_path else self.temp_dir) / f"cookie_{self.info._id}.txt"
                    )
                    self.logger.debug(
                        f"Creating cookie file for '{self.info.id}: {self.info.title}' - '{cookie_file}'."
                    )
                    cookie_file.write_text(self.info.cookies)
                    params["cookiefile"] = str(cookie_file.as_posix())

                    load_cookies(cookie_file)
                except Exception as e:
                    err_msg = f"Failed to create cookie file for '{self.info.id}: {self.info.title}'. '{e!s}'."
                    self.logger.error(err_msg)
                    raise ValueError(err_msg) from e

            if not self.info_dict:
                self.logger.info(f"Extracting info for '{self.info.url}'.")
                self.logs = []
                ie_params = params.copy()
                ie_params["callback"] = {
                    "func": lambda _, msg: self.logs.append(msg),
                    "level": logging.WARNING,
                    "name": "callback-logger",
                }

                info = extract_info(
                    config=params,
                    url=self.info.url,
                    debug=self.debug,
                    no_archive=not params.get("download_archive", False),
                    follow_redirect=True,
                )

                if info:
                    self.info_dict = info

            if self.is_live:
                hasDeletedOptions = False
                deletedOpts: list = []
                for opt in self.bad_live_options:
                    if opt in params:
                        params.pop(opt, None)
                        hasDeletedOptions = True
                        deletedOpts.append(opt)

                if hasDeletedOptions:
                    self.logger.warning(
                        f"Live stream detected for '{self.info.title}', The following opts '{deletedOpts=}' have been deleted."
                    )

            if isinstance(self.info_dict, dict) and len(self.info_dict.get("formats", [])) < 1:
                msg = f"Failed to extract any formats for '{self.info.url}'."
                if filtered_logs := extract_ytdlp_logs(self.logs):
                    msg += " " + ", ".join(filtered_logs)

                raise ValueError(msg)  # noqa: TRY301

            self.logger.info(
                f'Task id="{self.info.id}" PID="{os.getpid()}" title="{self.info.title}" preset="{self.preset}" cookies="{bool(params.get("cookiefile"))}" started.'
            )

            self.logger.debug(f"Params before passing to yt-dlp. {params}")

            params["logger"] = NestedLogger(self.logger)

            cls = YTDLP(params=params)

            self.started_time = int(time.time())

            if "posix" == os.name:

                def mark_cancelled(*_) -> None:
                    cls._interrupted = True
                    cls.to_screen("[info] Interrupt received, exiting cleanly...")
                    raise SystemExit(130)  # noqa: TRY301

                signal.signal(signal.SIGUSR1, mark_cancelled)

            if isinstance(self.info_dict, dict) and len(self.info_dict) > 1:
                self.logger.debug(f"Downloading '{self.info.url}' using pre-info.")
                cls.process_ie_result(
                    ie_result=self.info_dict,
                    download=True,
                    extra_info={k: v for k, v in self.info.extras.items() if k not in self.info_dict},
                )
                ret: int = cls._download_retcode
            else:
                self.logger.debug(f"Downloading using url: {self.info.url}")
                ret: int = cls.download(url_list=[self.info.url])

            self.status_queue.put({"id": self.id, "status": "finished" if ret == 0 else "error"})
        except yt_dlp.utils.ExistingVideoReached as exc:
            self.logger.error(exc)
            self.status_queue.put({"id": self.id, "status": "skip", "msg": "Item has already been downloaded."})
        except Exception as exc:
            self.logger.exception(exc)
            self.logger.error(exc)
            self.status_queue.put({"id": self.id, "status": "error", "msg": str(exc), "error": str(exc)})
        finally:
            self.status_queue.put(Terminator())
            if cookie_file and cookie_file.exists():
                try:
                    cookie_file.unlink()
                    self.logger.debug(f"Deleted cookie file: {cookie_file}")
                except Exception as e:
                    self.logger.error(f"Failed to delete cookie file: {cookie_file}. {e}")

        self.logger.info(
            f'Task id="{self.info.id}" PID="{os.getpid()}" title="{self.info.title}" preset="{self.preset}" cookies="{bool(params.get("cookiefile"))}" completed.'
        )

    async def start(self):
        self.status_queue = Config.get_manager().Queue()

        # Create temp dir for each download.
        if not self.temp_disabled:
            self.temp_path = Path(self.temp_dir) / hashlib.shake_256(f"D-{self.info.id}".encode()).hexdigest(5)

            if not self.temp_path.exists():
                self.temp_path.mkdir(parents=True, exist_ok=True)

            self.info.temp_path = str(self.temp_path)

        self.proc = multiprocessing.Process(name=f"download-{self.id}", target=self._download)
        self.proc.start()
        self.info.status = "preparing"

        await self._notify.emit(Events.ITEM_UPDATED, data=self.info)
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
        procId: int | None = self.proc.ident

        if not procId:
            if self.proc:
                self.proc.close()
                self.proc = None
            self.logger.warning("Attempted to close download process, but it is not running.")
            return False

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
            self.logger.exception(e)

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
            if self.proc.pid and "posix" == os.name:
                os.kill(self.proc.pid, signal.SIGUSR1)
            else:
                self.proc.kill()
            return True
        except Exception as e:
            self.logger.error(f"Failed to kill process: '{self.proc.ident}'. {e}")

        return False

    def delete_temp(self):
        if self.temp_disabled or self.temp_keep is True or not self.temp_path:
            return

        if "finished" != self.info.status and self.info.downloaded_bytes and self.info.downloaded_bytes > 0:
            self.logger.warning(
                f"Keeping temp folder '{self.temp_path}', as the reported status is not finished '{self.info.status}'."
            )
            return

        tmp_dir = Path(self.temp_path)

        if not tmp_dir.exists():
            return

        if str(tmp_dir) == str(self.temp_dir):
            self.logger.warning(
                f"Attempted to delete video temp folder '{self.temp_path}', but it is the same as main temp folder."
            )
            return

        status = delete_dir(tmp_dir)
        self.logger.info(f"Temp folder '{self.temp_path}' deletion is {'success' if status else 'failed'}.")

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
                await self._notify.emit(Events.ITEM_UPDATED, data=self.info)
                continue

            self.tmpfilename = status.get("tmpfilename")

            if "filename" in status:
                fl = Path(status.get("filename"))
                try:
                    self.info.filename = str(Path(status.get("filename")).relative_to(Path(self.download_dir)))
                except ValueError:
                    if self.temp_path:
                        self.info.filename = str(Path(status.get("filename")).relative_to(Path(self.temp_path)))
                    else:
                        self.info.filename = str(fl)

                if fl.is_file() and fl.exists():
                    try:
                        self.info.file_size = fl.stat().st_size
                    except FileNotFoundError:
                        self.info.file_size = 0

            self.info.status = status.get("status", self.info.status)
            self.info.msg = status.get("msg")

            if "error" == self.info.status and "error" in status:
                self.info.error = status.get("error")
                await self._notify.emit(
                    Events.LOG_ERROR,
                    data=self.info,
                    title="Download Error",
                    message=f"'{self.info.title}' failed to download: {self.info.error}",
                )

            if "downloaded_bytes" in status and status.get("downloaded_bytes") > 0:
                self.info.downloaded_bytes = status.get("downloaded_bytes")
                total = status.get("total_bytes") or status.get("total_bytes_estimate")
                if total:
                    try:
                        self.info.percent = status["downloaded_bytes"] / total * 100
                    except ZeroDivisionError:
                        self.info.percent = 0
                    self.info.total_bytes = total

            self.info.speed = status.get("speed")
            self.info.eta = status.get("eta")

            fl = Path(status.get("filename")) if status and "filename" in status else None

            if "finished" == self.info.status and fl and fl.is_file() and fl.exists():
                self.info.file_size = fl.stat().st_size
                self.info.datetime = str(formatdate(time.time()))

                try:
                    ff = await ffprobe(status.get("filename"))
                    self.info.extras["is_video"] = ff.has_video()
                    self.info.extras["is_audio"] = ff.has_audio()
                    if (ff.has_video() or ff.has_audio()) and not self.info.extras.get("duration"):
                        self.info.extras["duration"] = int(float(ff.metadata.get("duration", 0.0)))
                except Exception as e:
                    self.info.extras["is_video"] = True
                    self.info.extras["is_audio"] = True
                    self.logger.exception(e)
                    self.logger.error(f"Failed to run ffprobe. {status.get}. {e}")

            await self._notify.emit(Events.ITEM_UPDATED, data=self.info)

    def is_stale(self) -> bool:
        """
        Check if the download task is stale.
        A download task is considered stale if it has not been updated for a certain period of time.

        Returns:
            bool: True if the download task is stale, False otherwise.

        """
        if not self.info.auto_start:
            return False

        if self.started_time < 1:
            self.logger.debug(f"Download task '{self.info.title}: {self.info.id}' not started yet.")
            return False

        if int(time.time()) - self.started_time < 300:
            self.logger.debug(
                f"Download task '{self.info.title}: {self.info.id}' started for '{int(time.time()) - self.started_time}' seconds."
            )
            return False

        if not self.running():
            self.logger.warning(
                f"Download task '{self.info.title}: {self.info.id}' not started running for '{int(time.time()) - self.started_time}' seconds."
            )
            return True

        if self.info.status not in ["finished", "error", "cancelled", "downloading", "postprocessing"]:
            status = self.info.status if self.info.status else "unknown"
            self.logger.warning(
                f"Download task '{self.info.title}: {self.info.id}' has been stuck in '{status}' state for '{int(time.time()) - self.started_time}' seconds."
            )
            return True

        return False

    def __getstate__(self):
        state = self.__dict__.copy()

        # Exclude (unpickleable) keys during pickling, this issue arise mostly on Windows.
        excluded_keys = ("_notify",)
        for key in excluded_keys:
            if key in state:
                state[key] = None

        return state
