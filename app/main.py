#!/usr/bin/env python3
import sys
from pathlib import Path

if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()

APP_ROOT = str((Path(__file__).parent / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)


import asyncio
import logging
from pathlib import Path

import magic
from aiohttp import web

from app.features.conditions.service import Conditions
from app.features.dl_fields.service import DLFields
from app.features.notifications.service import Notifications
from app.features.presets.deps import get_presets_repo
from app.features.tasks.definitions.deps import get_task_definitions_repo
from app.features.tasks.service import Tasks
from app.library.BackgroundWorker import BackgroundWorker
from app.library.cache import Cache
from app.library.config import Config
from app.library.downloads import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.HttpAPI import HttpAccessLogger, HttpAPI
from app.library.HttpSocket import HttpSocket
from app.library.httpx_client import close_shared_clients
from app.library.log import get_logger
from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.sqlite_store import SqliteStore
from app.library.TerminalSessionManager import TerminalSessionManager
from app.library.UpdateChecker import UpdateChecker

LOG = get_logger()
MIME = magic.Magic(mime=True)

ROOT_PATH: Path = Path(__file__).parent.absolute()


class Main:
    def __init__(self, is_native: bool = False):
        self._config: Config = Config.get_instance(is_native=is_native)
        self._config.set_app_path(str(ROOT_PATH))
        self._app = web.Application()
        self._app.on_shutdown.append(self.on_shutdown)

        Services.get_instance().add("app", self._app)

        self._check_folders()

        try:
            db_file = Path(self._config.db_file)
            if "600" != oct(db_file.stat().st_mode)[-3:]:
                db_file.chmod(0o600)
        except Exception:
            pass

        self._http = HttpAPI(root_path=ROOT_PATH)
        self._socket = HttpSocket(root_path=ROOT_PATH)

    def _check_folders(self):
        """Check if the required folders exist and create them if they do not."""
        folders: tuple[str, str, str] = (self._config.download_path, self._config.temp_path, self._config.config_path)

        for folder in folders:
            folder = Path(folder)
            try:
                LOG.debug("Checking folder '%s'.", folder, extra={"folder": str(folder)})
                if not folder.exists():
                    LOG.info("Creating folder '%s'.", folder, extra={"folder": str(folder)})
                    folder.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                LOG.exception(
                    "Failed to create folder '%s'.",
                    folder,
                    extra={"folder": str(folder), "exception_type": type(e).__name__},
                )
                raise

        try:
            db_file = Path(self._config.db_file)
            LOG.debug("Checking database file '%s'.", db_file, extra={"db_file": str(db_file)})
            if not db_file.exists():
                LOG.info("Creating database file '%s'.", db_file, extra={"db_file": str(db_file)})
                db_file.touch(exist_ok=True)
        except OSError as e:
            LOG.exception(
                "Failed to create database file at '%s'.",
                self._config.db_file,
                extra={"db_file": str(self._config.db_file), "exception_type": type(e).__name__},
            )
            raise

    async def on_shutdown(self, _: web.Application):
        EventBus.get_instance().emit(
            Events.SHUTDOWN,
            data={"app": self._app},
            title="Application Shutdown",
            message="The application is shutting down.",
        )

    def start(self, host: str | None = None, port: int | None = None, cb=None):
        """
        Start the application.
        """
        host = host or self._config.host
        port = port or self._config.port

        EventBus.get_instance().emit(
            Events.STARTUP,
            data={"app": self._app},
            title="Application Startup",
            message="The application is starting up.",
        )
        if self._config.debug:
            EventBus.get_instance().debug_enable()

        SqliteStore.get_instance(db_path=self._config.db_file).attach(self._app)
        BackgroundWorker.get_instance().attach(self._app)
        Scheduler.get_instance().attach(self._app)
        Cache.get_instance().attach(self._app)
        TerminalSessionManager.get_instance().attach(self._app)

        self._socket.attach(self._app)
        self._http.attach(self._app)

        get_presets_repo().attach(self._app)
        Tasks.get_instance().attach(self._app)
        Notifications.get_instance().attach(self._app)
        Conditions.get_instance().attach(self._app)
        DLFields.get_instance().attach(self._app)
        get_task_definitions_repo().attach(self._app)
        DownloadQueue.get_instance().attach(self._app)
        UpdateChecker.get_instance().attach(self._app)
        self._app.on_shutdown.append(close_shared_clients)

        EventBus.get_instance().emit(
            Events.LOADED,
            data={"app": self._app},
            title="Application Loaded",
            message="The application has loaded all components.",
        )

        def started(_):
            LOG.info("=" * 40)
            LOG.info(
                "YTPTube %s started on %s.",
                self._config.app_version,
                f"http://{host}:{port}{self._config.base_path}",
                extra={
                    "app_version": self._config.app_version,
                    "listen_url": f"http://{host}:{port}{self._config.base_path}",
                    "host": host,
                    "port": port,
                    "base_path": self._config.base_path,
                },
            )
            LOG.info(
                "Using download path '%s'.",
                self._config.download_path,
                extra={"download_path": self._config.download_path},
            )
            if self._config.is_native:
                LOG.info("Running in native mode.")
            LOG.info("=" * 40)

            loop = asyncio.get_event_loop()

            EventBus.get_instance().emit(
                Events.STARTED,
                data={"app": self._app},
                title="Application Started",
                message="The application has started successfully.",
            )

            if loop and self._config.debug:
                loop.set_debug(True)
                loop.slow_callback_duration = 0.05

            if cb:
                cb()

        HTTP_LOGGER = None
        HTTP_LOGGER_CLASS = None
        if self._config.access_log:
            from app.library.HttpAPI import LOG as HTTP_LOGGER

            HTTP_LOGGER.addFilter(
                lambda record: f"GET {str(self._app.router['ping'].url_for()).rstrip('/')}" not in record.getMessage()
            )
            HTTP_LOGGER_CLASS = HttpAccessLogger

        run_args = {
            "host": host,
            "port": port,
            "loop": asyncio.get_event_loop(),
            "access_log": HTTP_LOGGER,
            "print": started,
            "handle_signals": cb is None,
        }
        if HTTP_LOGGER_CLASS is not None:
            run_args["access_log_class"] = HTTP_LOGGER_CLASS

        web.run_app(self._app, **run_args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    Main().start()
