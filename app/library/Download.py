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
from typing import Any

import yt_dlp.utils

from .config import Config
from .Events import EventBus, Events
from .ffprobe import ffprobe
from .ItemDTO import ItemDTO
from .Utils import delete_dir, extract_info, extract_ytdlp_logs, load_cookies
from .ytdlp import YTDLP


class Terminator:
    pass


class NestedLogger:
    debug_messages: list[str] = ["[debug] ", "[download] "]

    def __init__(self, logger: logging.Logger) -> None:
        self.logger: logging.Logger = logger

    def debug(self, msg: str) -> None:
        levelno: int = logging.DEBUG if any(msg.startswith(x) for x in self.debug_messages) else logging.INFO
        self.logger.log(level=levelno, msg=re.sub(r"^\[(debug|info)\] ", "", msg, flags=re.IGNORECASE))

    def error(self, msg) -> None:
        self.logger.error(msg)

    def warning(self, msg) -> None:
        self.logger.warning(msg)


class Download:
    """
    Download task.
    """

    temp_path: str = None
    update_task = None
    cancel_in_progress: bool = False
    final_update = False

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

    def __init__(self, info: ItemDTO, info_dict: dict = None, logs: list | None = None):
        """
        Initialize download task.

        Args:
            info (ItemDTO): ItemDTO object.
            info_dict (dict): yt-dlp metadata dict.
            logs (list): Logs from yt-dlp.

        """
        config: Config = Config.get_instance()

        self.download_dir: str = info.download_dir
        "Download directory."
        self.temp_dir: str | None = info.temp_dir
        "Temporary directory."
        self.template: str | None = info.template
        "Filename template."
        self.template_chapter: str | None = info.template_chapter
        "Chapter filename template."
        self.download_info_expires = int(config.download_info_expires)
        "Time in seconds before the download info is considered expired."
        self.info: ItemDTO = info
        "ItemDTO object."
        self.id: str = info._id
        "Download ID."
        self.debug = bool(config.debug)
        "Debug mode."
        self.debug_ytdl = bool(config.ytdlp_debug)
        "Debug mode for yt-dlp."
        self.cancelled = False
        "Download cancelled."
        self.tmpfilename = None
        "Temporary filename."
        self.status_queue = None
        "Status queue."
        self.proc = None
        "yt-dlp process."
        self._notify: EventBus = EventBus.get_instance()
        "Event bus instance."
        self.max_workers = int(config.max_workers)
        "Maximum number of concurrent downloads."
        self.temp_keep = bool(config.temp_keep)
        "Keep temp folder after download."
        self.temp_disabled = bool(config.temp_disabled)
        "Disable the temporary files feature."
        self.is_live: bool = bool(info.is_live) or info.live_in is not None
        "Is the download a live stream."
        self.info_dict: dict = info_dict
        "yt-dlp metadata dict."
        self.logger: logging.Logger = logging.getLogger(f"Download.{info.id if info.id else info._id}")
        "Logger for the download task."
        self.started_time = 0
        "Time when the download started."
        self.queue_time: datetime = datetime.now(tz=UTC)
        "Time when the download was queued."
        self.logs: list[str] = logs if logs else []
        "Logs from yt-dlp."

    def _progress_hook(self, data: dict) -> None:
        if self.debug:
            try:
                d_safe: dict = {
                    "status": data.get("status"),
                    "filename": data.get("filename"),
                    "info_dict": {
                        k: v for k, v in data.get("info_dict", {}).items()
                        if k not in ["formats", "thumbnails", "description", "tags", "_format_sort_fields"]
                        and not isinstance(v, (type(None).__bases__[0], type(lambda: None)))  # Skip non-serializable
                    }
                }
                self.logger.debug(f"PG Hook: {d_safe}")
            except Exception as e:
                self.logger.debug(f"PG Hook: Error creating debug info: {e}")

        self.status_queue.put(
            {
                "id": self.id,
                "action": "progress",
                **{k: v for k, v in data.items() if k in self._ytdlp_fields},
            }
        )

    def _postprocessor_hook(self, data: dict) -> None:
        if self.debug:
            try:
                d_safe: dict = {
                    "postprocessor": data.get("postprocessor"),
                    "status": data.get("status"),
                    "info_dict": {
                        k: v for k, v in data.get("info_dict", {}).items()
                        if k not in ["formats", "thumbnails", "description", "tags", "_format_sort_fields"]
                        and not isinstance(v, (type(None).__bases__[0], type(lambda: None)))  # Skip non-serializable
                    }
                }
                self.logger.debug(f"PP Hook: {d_safe}")
            except Exception as e:
                self.logger.debug(f"PP Hook: Error creating debug info: {e}")

        if "MoveFiles" == data.get("postprocessor") and "finished" == data.get("status"):
            if "__finaldir" in data.get("info_dict", {}) and "filepath" in data.get("info_dict", {}):
                filename = str(Path(data["info_dict"]["__finaldir"]) / Path(data["info_dict"]["filepath"]).name)
            else:
                filename: str | None = data.get("info_dict", {}).get("filepath", data.get("filename"))

            self.logger.debug(f"Final filename: '{filename}'.")
            self.status_queue.put({"id": self.id, "action": "moved", "status": "finished", "final_name": filename})
            return

        dataDict = {k: v for k, v in data.items() if k in self._ytdlp_fields}
        self.status_queue.put({"id": self.id, "action": "postprocessing", **dataDict, "status": "postprocessing"})

    def post_hooks(self, filename: str | None = None) -> None:
        if not filename:
            return

        self.status_queue.put({"id": self.id, "filename": filename})

    def _download(self) -> None:
        if not self._notify:
            self._notify = EventBus.get_instance()

        cookie_file = None

        try:
            params: dict = (
                self.info.get_ytdlp_opts()
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
                    err_msg: str = f"Failed to create cookie file for '{self.info.id}: {self.info.title}'. '{e!s}'."
                    self.logger.error(err_msg)
                    raise ValueError(err_msg) from e

            # Safe-guard in-case downloading take too long and the info expires.
            if self.info_dict and isinstance(self.info_dict, dict) and self.download_info_expires > 0:
                _ts: int | None = self.info_dict.get("epoch", self.info_dict.get("timestamp", None))
                _ts = datetime.fromtimestamp(_ts, tz=UTC) if _ts else None
                if not _ts or (datetime.now(tz=UTC) - _ts).total_seconds() > self.download_info_expires:
                    self.info_dict = None
                    self.logger.warning(f"Info for '{self.info.url}' has expired, re-extracting info.")

            if not self.info_dict or not isinstance(self.info_dict, dict):
                self.logger.info(f"Extracting info for '{self.info.url}'.")
                self.logs = []
                ie_params: dict = params.copy()
                ie_params["callback"] = {
                    "func": lambda _, msg: self.logs.append(msg),
                    "level": logging.WARNING,
                    "name": "callback-logger",
                }

                info: dict = extract_info(
                    config=params,
                    url=self.info.url,
                    debug=self.debug,
                    no_archive=not params.get("download_archive", False),
                    follow_redirect=True,
                )

                if info:
                    self.info_dict = info

            if self.is_live:
                deletedOpts: list = []
                for opt in self.bad_live_options:
                    if opt in params:
                        params.pop(opt, None)
                        deletedOpts.append(opt)

                if len(deletedOpts) > 0:
                    self.logger.warning(
                        f"Live stream detected for '{self.info.title}', The following opts '{deletedOpts=}' have been deleted."
                    )

            if isinstance(self.info_dict, dict) and len(self.info_dict.get("formats", [])) < 1:
                msg: str = f"Failed to extract any formats for '{self.info.url}'."
                if filtered_logs := extract_ytdlp_logs(self.logs):
                    msg += " " + ", ".join(filtered_logs)

                raise ValueError(msg)  # noqa: TRY301

            self.logger.info(
                f'Task {self.info.name()}, preset="{self.info.preset}", cookies="{bool(params.get("cookiefile"))}" started.'
            )

            if self.debug:
                self.logger.debug(f"Params before passing to yt-dlp. {params}")

            params["logger"] = NestedLogger(self.logger)

            if "continuedl" in params and params["continuedl"] is False:
                self.delete_temp(by_pass=True)

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
                _dct: dict = self.info_dict.copy()
                if isinstance(self.info.extras, dict) and len(self.info.extras) > 0:
                    _dct.update({k: v for k, v in self.info.extras.items() if k not in _dct or not _dct.get(k)})

                cls.process_ie_result(ie_result=_dct, download=True)
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
            f'Task {self.info.name()} preset="{self.info.preset}" cookies="{bool(params.get("cookiefile"))}" completed.'
        )

    async def start(self) -> None:
        self.status_queue: multiprocessing.Queue[Any] = Config.get_manager().Queue()

        # Create temp dir for each download.
        if not self.temp_disabled:
            self.temp_path = Path(self.temp_dir) / hashlib.shake_256(f"D-{self.info.id}".encode()).hexdigest(5)

            if not self.temp_path.exists():
                self.temp_path.mkdir(parents=True, exist_ok=True)

            self.info.temp_path = str(self.temp_path)

        self.proc = multiprocessing.Process(name=f"download-{self.id}", target=self._download)
        self.proc.start()
        self.info.status = "preparing"

        self._notify.emit(Events.ITEM_UPDATED, data=self.info)
        asyncio.create_task(self.progress_update(), name=f"update-{self.id}")

        ret = await asyncio.get_running_loop().run_in_executor(None, self.proc.join)

        if self.final_update or self.cancelled:
            if self.cancelled:
                self.info.status = "cancelled"
            return ret

        self.status_queue.put(Terminator())
        self.logger.debug("Draining status queue.")
        try:
            drain_count: int = 50 + (self.status_queue.qsize() if hasattr(self.status_queue, "qsize") else 5)
        except Exception:
            drain_count = 55

        for i in range(drain_count):
            try:
                if self.debug:
                    self.logger.debug(f"(50/{i}) Draining the status queue...")
                if self.final_update:
                    if self.debug:
                        self.logger.debug("(50/{i}) Draining stopped. Final update received.")
                    break
                next_status = self.status_queue.get(timeout=0.1)
                if next_status is None or isinstance(next_status, Terminator):
                    continue
                await self._process_status_update(next_status)
            except Exception:  # noqa: S112
                continue

        return ret

    def started(self) -> bool:
        return self.proc is not None

    def cancel(self) -> bool:
        """
        Cancel the download task.
        For live streams and unresponsive processes, this will force-kill the process.
        """
        if not self.started():
            return False

        self.cancelled = True

        # Actively kill the process instead of just setting a flag
        return self.kill()

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
        """
        Kill the download process.
        Attempts graceful termination via signal first, then force-kills if necessary.
        For live streams that may not respond to signals, uses force termination.
        """
        if not self.running():
            return False

        procId: int | None = self.proc.ident
        try:
            self.logger.info(f"Killing download process: PID={self.proc.pid}, ident={procId}.")

            # First, try graceful termination with SIGUSR1 signal (if on POSIX)
            if self.proc.pid and "posix" == os.name:
                try:
                    self.logger.debug(f"Sending SIGUSR1 signal to PID={self.proc.pid}.")
                    os.kill(self.proc.pid, signal.SIGUSR1)

                    # Wait briefly for graceful shutdown (1 second timeout for live streams)
                    start_time = time.time()
                    timeout = 2 if self.is_live else 5  # Live streams get shorter timeout
                    while self.proc.is_alive() and (time.time() - start_time) < timeout:
                        time.sleep(0.1)

                    if self.proc.is_alive():
                        self.logger.warning(
                            f"Process PID={self.proc.pid} did not respond to SIGUSR1 "
                            f"({'live stream' if self.is_live else 'regular download'}), "
                            f"forcing termination."
                        )
                    else:
                        self.logger.debug(f"Process PID={self.proc.pid} terminated gracefully.")
                        return True

                except (OSError, AttributeError) as e:
                    self.logger.debug(f"Failed to send SIGUSR1 signal: {e}")

            # Force terminate if still running (for live streams or unresponsive processes)
            if self.proc.is_alive():
                self.logger.info(f"Force-terminating process PID={self.proc.pid}.")
                self.proc.terminate()

                # Give it a moment to terminate
                start_time = time.time()
                timeout = 1 if self.is_live else 2
                while self.proc.is_alive() and (time.time() - start_time) < timeout:
                    time.sleep(0.05)

                # If still alive, use hard kill
                if self.proc.is_alive():
                    self.logger.warning(
                        f"Process PID={self.proc.pid} did not respond to terminate(), "
                        f"killing forcefully."
                    )
                    self.proc.kill()
                    # Give it final moment
                    start_time = time.time()
                    while self.proc.is_alive() and (time.time() - start_time) < 1:
                        time.sleep(0.05)

            self.logger.info(f"Process PID={self.proc.pid} killed.")
            return True

        except Exception as e:
            self.logger.error(f"Failed to kill process PID={self.proc.pid}, ident={procId}. {e}")
            self.logger.exception(e)

        return False

    def delete_temp(self, by_pass: bool = False) -> None:
        if self.temp_disabled or self.temp_keep is True or not self.temp_path:
            return

        if (
            not by_pass
            and "finished" != self.info.status
            and self.info.downloaded_bytes
            and self.info.downloaded_bytes > 0
        ):
            self.logger.warning(f"Keeping temp folder '{self.temp_path}'. {self.info.status=}.")
            return

        tmp_dir = Path(self.temp_path)

        if not tmp_dir.exists():
            return

        if str(tmp_dir) == str(self.temp_dir):
            self.logger.warning(f"Refusing to delete video temp folder '{self.temp_path}' as it's temp root.")
            return

        status: bool = delete_dir(tmp_dir)
        if by_pass:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Temp folder '{self.temp_path}' emptied.")
        else:
            self.logger.info(f"Temp folder '{self.temp_path}' deletion is {'success' if status else 'failed'}.")

    async def _process_status_update(self, status) -> None:
        if status.get("id") != self.id or len(status) < 2:
            self.logger.warning(f"Received invalid status update. {status}")
            return

        if self.debug:
            self.logger.debug(f"Status Update: {self.info._id=} {status=}")

        if isinstance(status, str):
            self._notify.emit(Events.ITEM_UPDATED, data=self.info)
            return

        self.tmpfilename: str | None = status.get("tmpfilename")

        fl = None
        if "final_name" in status:
            fl = Path(status.get("final_name"))
            try:
                self.info.filename = str(fl.relative_to(Path(self.download_dir)))
            except ValueError as ve:
                self.logger.debug(f"Failed to get relative path for '{fl}' from '{self.download_dir}'. {ve}")
                if self.temp_path:
                    self.info.filename = str(fl.relative_to(Path(self.temp_path)))
                else:
                    self.info.filename = str(fl)

            if fl.is_file() and fl.exists():
                self.final_update = True
                self.logger.debug(f"Final file name: '{fl}'.")

                try:
                    self.info.file_size = fl.stat().st_size
                except FileNotFoundError:
                    self.info.file_size = 0

        self.info.status = status.get("status", self.info.status)
        self.info.msg = status.get("msg")

        if "error" == self.info.status and "error" in status:
            self.info.error = status.get("error")
            self._notify.emit(
                Events.LOG_ERROR,
                data=self.info,
                title="Download Error",
                message=f"'{self.info.title}' failed to download. {self.info.error}",
            )

        if "downloaded_bytes" in status and status.get("downloaded_bytes", 0) > 0:
            self.info.downloaded_bytes = status.get("downloaded_bytes")
            total: float | None = status.get("total_bytes") or status.get("total_bytes_estimate")
            if total:
                try:
                    self.info.percent = status["downloaded_bytes"] / total * 100
                except ZeroDivisionError:
                    self.info.percent = 0
                self.info.total_bytes = total

        self.info.speed = status.get("speed")
        self.info.eta = status.get("eta")

        if "finished" == self.info.status and fl and fl.is_file() and fl.exists():
            self.info.file_size = fl.stat().st_size
            self.info.datetime = str(formatdate(time.time()))

            try:
                ff = await ffprobe(str(fl))
                self.info.extras["is_video"] = ff.has_video()
                self.info.extras["is_audio"] = ff.has_audio()
                if (ff.has_video() or ff.has_audio()) and not self.info.extras.get("duration"):
                    self.info.extras["duration"] = int(float(ff.metadata.get("duration", 0.0)))
            except Exception as e:
                self.info.extras["is_video"] = True
                self.info.extras["is_audio"] = True
                self.logger.exception(e)
                self.logger.error(f"Failed to run ffprobe. {status.get}. {e}")

        if not self.final_update or fl:
            self._notify.emit(Events.ITEM_UPDATED, data=self.info)

    async def progress_update(self) -> None:
        """
        Update status of download task and notify the client.
        """
        while True:
            try:
                self.update_task = asyncio.get_running_loop().run_in_executor(None, self.status_queue.get)
                status = await self.update_task
                if status is None or isinstance(status, Terminator):
                    return
                await self._process_status_update(status)
            except (asyncio.CancelledError, OSError, FileNotFoundError):
                return

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
            self.logger.debug(f"Download task '{self.info.name()}' not started yet.")
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
            status: str = self.info.status if self.info.status else "unknown"
            self.logger.warning(
                f"Download task '{self.info.title}: {self.info.id}' has been stuck in '{status}' state for '{int(time.time()) - self.started_time}' seconds."
            )
            return True

        return False

    def __getstate__(self) -> dict[str, Any]:
        state: dict[str, Any] = self.__dict__.copy()

        # Exclude (unpickleable) keys during pickling, this issue arise mostly on Windows.
        excluded_keys: tuple[str] = ("_notify",)
        for key in excluded_keys:
            if key in state:
                state[key] = None

        return state
