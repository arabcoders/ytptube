"""Runtime initialization for download worker processes."""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import threading
from typing import TYPE_CHECKING

from app.features.presets.repository import PresetsRepository
from app.features.presets.service import Presets
from app.library.config import Config
from app.library.log import get_logger
from app.library.sqlite_store import SqliteStore

LOG = get_logger()

if TYPE_CHECKING:
    from logging import Logger

_BOOTSTRAP_STATE: dict[str, int | None] = {"pid": None}
_LOCK = threading.Lock()


def _start_method() -> str | None:
    method = multiprocessing.get_start_method(allow_none=True)
    if method:
        return method

    try:
        return multiprocessing.get_context().get_start_method()
    except RuntimeError:
        return None


def _should_bootstrap() -> bool:
    if multiprocessing.current_process().name == "MainProcess":
        return False

    return _start_method() in {"spawn", "forkserver"}


async def _bootstrap_download_runtime() -> None:
    config = Config.get_instance()
    await SqliteStore.get_instance(db_path=config.db_file).get_connection()

    repo = PresetsRepository.get_instance()
    await Presets.get_instance().refresh_cache(await repo.all())


def _run_bootstrap() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_bootstrap_download_runtime())
        return

    msg = "Cannot initialize download worker runtime while an event loop is already running."
    raise RuntimeError(msg)


def ensure_download_runtime(logger: Logger | None = None) -> bool:
    """Initialize process-local runtime state for spawned download workers."""
    if not _should_bootstrap():
        return False

    pid = os.getpid()
    if _BOOTSTRAP_STATE["pid"] == pid:
        return False

    with _LOCK:
        if _BOOTSTRAP_STATE["pid"] == pid:
            return False

        log = logger or LOG
        log.debug(
            "Initializing download worker runtime for process PID=%s.",
            pid,
            extra={"process_id": pid, "start_method": _start_method()},
        )
        _run_bootstrap()
        _BOOTSTRAP_STATE["pid"] = pid
        return True
