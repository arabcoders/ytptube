"""Core Download class - orchestrates the download process."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yt_dlp.utils

from app.library.config import Config
from app.library.Events import EventBus, Events
from app.library.Utils import create_cookies_file, extract_ytdlp_logs
from app.library.ytdlp import YTDLP

from .extractor import extract_info_sync
from .hooks import HookHandlers, NestedLogger
from .process_manager import ProcessManager
from .status_tracker import StatusTracker
from .temp_manager import TempManager
from .types import Terminator
from .utils import BAD_LIVE_STREAM_OPTIONS, GENERIC_EXTRACTORS, is_download_stale

if TYPE_CHECKING:
    import multiprocessing

    from app.library.ItemDTO import ItemDTO


class Download:
    update_task: asyncio.Task | None = None

    def __init__(self, info: ItemDTO, info_dict: dict | None = None, logs: list[str] | None = None):
        """
        Initialize download task.

        Args:
            info: ItemDTO object containing download parameters
            info_dict: Pre-extracted yt-dlp metadata dict (optional)
            logs: Pre-existing logs from yt-dlp (optional)

        """
        config: Config = Config.get_instance()

        self.download_dir: str = info.download_dir
        self.temp_dir: str | None = info.temp_dir
        self.template: str | None = info.template
        self.template_chapter: str | None = info.template_chapter
        self.download_info_expires = int(config.download_info_expires)
        self.info: ItemDTO = info
        self.id: str = info._id
        self.debug = bool(config.debug)
        self.debug_ytdl = bool(config.ytdlp_debug)
        self.tmpfilename: str | None = None
        self.status_queue: multiprocessing.Queue[Any] | None = None
        self.max_workers = int(config.max_workers)
        self.is_live: bool = bool(info.is_live) or info.live_in is not None
        self.info_dict: dict | None = info_dict
        self.logger: logging.Logger = logging.getLogger(f"Download.{info.id if info.id else info._id}")
        self.started_time = 0
        self.queue_time: datetime = datetime.now(tz=UTC)
        self.logs: list[str] = logs if logs else []

        self._process_manager = ProcessManager(
            download_id=self.id,
            is_live=self.is_live,
            logger=self.logger,
        )

        self._temp_manager = TempManager(
            info=self.info,
            temp_dir=self.temp_dir,
            temp_disabled=bool(config.temp_disabled),
            temp_keep=bool(config.temp_keep),
            logger=self.logger,
        )

        self._status_tracker: StatusTracker | None = None
        self._hook_handlers: HookHandlers | None = None

    def _download(self) -> None:
        """
        Execute the download in a subprocess.

        This method runs in a separate process and performs the actual
        download using yt-dlp.
        """
        cookie_file: Path | None = None

        try:
            params: dict = (
                self.info.get_ytdlp_opts()
                .add(
                    config={
                        "color": "no_color",
                        "paths": {
                            "home": str(self.download_dir),
                            "temp": str(self._temp_manager.temp_path)
                            if self._temp_manager.temp_path
                            else self.download_dir,
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
                    "progress_hooks": [self._hook_handlers.progress_hook],
                    "postprocessor_hooks": [self._hook_handlers.postprocessor_hook],
                    "post_hooks": [self._hook_handlers.post_hook],
                }
            )

            if self.debug_ytdl:
                params["verbose"] = True
                params["noprogress"] = False

            if self.info.cookies:
                try:
                    cookie_file = (
                        Path(self._temp_manager.temp_path if self._temp_manager.temp_path else self.temp_dir)
                        / f"cookie_{self.info._id}.txt"
                    )
                    self.logger.debug(
                        f"Creating cookie file for '{self.info.id}: {self.info.title}' - '{cookie_file}'."
                    )
                    params["cookiefile"] = str(create_cookies_file(self.info.cookies, cookie_file))
                except Exception as e:
                    err_msg: str = f"Failed to create cookie file for '{self.info.id}: {self.info.title}'. '{e!s}'."
                    self.logger.error(err_msg)
                    raise ValueError(err_msg) from e

            if self.info_dict and isinstance(self.info_dict, dict):
                if self.info_dict.get("extractor_key") in GENERIC_EXTRACTORS and self.info.get_preset().default:
                    self.logger.debug(f"Removing 'download_archive' for generic extractor. url={self.info.url}")
                    params.pop("download_archive", None)

                if self.download_info_expires > 0:
                    _ts: int | None = self.info_dict.get("epoch", self.info_dict.get("timestamp", None))
                    _ts_dt = datetime.fromtimestamp(_ts, tz=UTC) if _ts else None
                    if not _ts_dt or (datetime.now(tz=UTC) - _ts_dt).total_seconds() > self.download_info_expires:
                        self.info_dict = None
                        self.logger.warning(f"Info for '{self.info.url}' has expired, re-extracting info.")

            if not self.info_dict or not isinstance(self.info_dict, dict):
                self.logger.info(f"Extracting info for '{self.info.url}'.")
                ie_params: dict = params.copy()

                (info, logs) = extract_info_sync(
                    config=ie_params,
                    url=self.info.url,
                    debug=self.debug,
                    no_archive=not params.get("download_archive", False),
                    follow_redirect=True,
                    capture_logs=logging.WARNING,
                )
                self.logs = [log["msg"] for log in logs]

                if info:
                    self.info_dict = info

            if self.is_live:
                deletedOpts: list[str] = []
                for opt in BAD_LIVE_STREAM_OPTIONS:
                    if opt in params:
                        params.pop(opt, None)
                        deletedOpts.append(opt)

                if len(deletedOpts) > 0:
                    self.logger.warning(f"Live stream detected for '{self.info.title}', deleted opts: {deletedOpts}")

            if isinstance(self.info_dict, dict) and not (
                len(self.info_dict.get("formats", [])) > 0 or self.info_dict.get("url")
            ):
                msg: str = f"Failed to extract any formats for '{self.info.url}'."
                if filtered_logs := extract_ytdlp_logs(self.logs):
                    msg += " " + ", ".join(filtered_logs)

                raise ValueError(msg)  # noqa: TRY301

            self.logger.info(
                f'Download {self.info.name()}, preset="{self.info.preset}", cookies="{bool(params.get("cookiefile"))}" started.'
            )

            if self.debug:
                self.logger.debug(f"Params before passing to yt-dlp. {params}")

            params["logger"] = NestedLogger(self.logger)

            if "continuedl" in params and params["continuedl"] is False:
                self._temp_manager.delete_temp(by_pass=True)

            cls = YTDLP(params=params)

            if "posix" == os.name:

                def mark_cancelled(*_) -> None:
                    cls._interrupted = True
                    cls.to_screen("[info] Interrupt received, exiting cleanly...")
                    raise SystemExit(130)  # noqa: TRY301

                signal.signal(signal.SIGUSR1, mark_cancelled)

            self.status_queue.put({"id": self.id, "status": "downloading"})

            if isinstance(self.info_dict, dict) and len(self.info_dict) > 1:
                self.logger.debug(f"Downloading '{self.info.url}' using pre-info.")
                _dct: dict = self.info_dict.copy()
                if isinstance(self.info.extras, dict) and len(self.info.extras) > 0:
                    _dct.update(
                        {
                            k: v
                            for k, v in self.info.extras.items()
                            if k not in _dct and v is not None and k not in ("is_live",)
                        }
                    )

                cls.process_ie_result(ie_result=_dct, download=True)
                ret: int = cls._download_retcode
            else:
                self.logger.debug(f"Downloading using url: {self.info.url}")
                ret = cls.download(url_list=[self.info.url])

            self.status_queue.put({"id": self.id, "status": "finished" if 0 == ret else "error"})
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

    async def start(self) -> int | None:
        """
        Start the download process.

        Creates the subprocess, initializes status tracking, and waits
        for completion.

        Returns:
            Process exit code or None

        """
        self.status_queue = Config.get_manager().Queue()

        if temp_path := self._temp_manager.create_temp_path():
            self.info.temp_path = str(temp_path)

        self._status_tracker = StatusTracker(
            info=self.info,
            download_id=self.id,
            download_dir=self.download_dir,
            temp_path=temp_path,
            status_queue=self.status_queue,
            logger=self.logger,
            debug=self.debug,
        )

        self._hook_handlers = HookHandlers(
            download_id=self.id,
            status_queue=self.status_queue,
            logger=self.logger,
            debug=self.debug,
        )

        self._process_manager.create_process(target=self._download)
        self._process_manager.start()
        self.started_time = int(time.time())
        self.info.status = "preparing"

        EventBus.get_instance().emit(Events.ITEM_UPDATED, data=self.info)
        asyncio.create_task(self._status_tracker.progress_update(), name=f"update-{self.id}")

        ret = await asyncio.get_running_loop().run_in_executor(None, self._process_manager.proc.join)

        if self._status_tracker.final_update or self._process_manager.is_cancelled():
            if self._process_manager.is_cancelled():
                self.info.status = "cancelled"
            return ret

        self._status_tracker.put_terminator()
        await self._status_tracker.drain_queue()

        return ret

    def started(self) -> bool:
        """Check if download process has been started."""
        return self._process_manager.started()

    def cancel(self) -> bool:
        """Cancel the download task."""
        return self._process_manager.cancel()

    async def close(self) -> bool:
        """Close download process and clean up resources."""
        if not self.started() or self._process_manager.cancel_in_progress:
            return False

        try:
            if self._status_tracker:
                self._status_tracker.cancel_update_task()

            await self._process_manager.close()

            if self._status_tracker:
                self._status_tracker.put_terminator()

            self._temp_manager.delete_temp()

            return True
        except Exception as e:
            self.logger.error(f"Failed to close process. {e}")
            self.logger.exception(e)

        return False

    def running(self) -> bool:
        return self._process_manager.running()

    def is_cancelled(self) -> bool:
        return self._process_manager.is_cancelled()

    def kill(self) -> bool:
        return self._process_manager.kill()

    def delete_temp(self, by_pass: bool = False) -> None:
        self._temp_manager.delete_temp(by_pass=by_pass)

    def is_stale(self) -> bool:
        """
        Check if the download task is stale.

        A download task is considered stale if it hasn't been updated
        for a certain period or is stuck in an unexpected state.

        Returns:
            True if the download task is stale, False otherwise

        """
        if self.started_time < 1:
            self.logger.debug(f"Download task '{self.info.name()}' not started yet.")
            return False

        elapsed = int(time.time()) - self.started_time
        if elapsed < 300:
            self.logger.debug(f"Download task '{self.info.title}: {self.info.id}' started for '{elapsed}' seconds.")
            return False

        status: str = self.info.status if self.info.status else "unknown"
        is_stale = is_download_stale(self.started_time, status, self.running(), self.info.auto_start, min_elapsed=300)

        if is_stale:
            if not self.running():
                self.logger.warning(
                    f"Download task '{self.info.title}: {self.info.id}' not started running for '{elapsed}' seconds."
                )
            else:
                self.logger.warning(
                    f"Download task '{self.info.title}: {self.info.id}' has been stuck in '{status}' state for '{elapsed}' seconds."
                )

        return is_stale

    def __getstate__(self) -> dict[str, Any]:
        """
        Prepare state for pickling.

        Excludes unpickleable objects like EventBus instances,
        primarily for Windows compatibility.
        """
        state: dict[str, Any] = self.__dict__.copy()

        excluded_keys: tuple[str, ...] = ("_notify",)
        for key in excluded_keys:
            if key in state:
                state[key] = None

        return state
