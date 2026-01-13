#!/usr/bin/env python3
import sys
from pathlib import Path

APP_ROOT = str((Path(__file__).parent / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)


import asyncio
import logging
from pathlib import Path

import magic
from aiohttp import web

from app.library.BackgroundWorker import BackgroundWorker
from app.library.conditions import Conditions
from app.library.config import Config
from app.library.dl_fields import DLFields
from app.library.downloads import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.HttpAPI import HttpAPI
from app.library.HttpSocket import HttpSocket
from app.library.Notifications import Notification
from app.library.Presets import Presets
from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.sqlite_store import SqliteStore
from app.library.TaskDefinitions import TaskDefinitions
from app.library.Tasks import Tasks
from app.library.UpdateChecker import UpdateChecker

LOG = logging.getLogger("app")
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
                LOG.debug(f"Checking folder at '{folder}'.")
                if not folder.exists():
                    LOG.info(f"Creating folder at '{folder}'.")
                    folder.mkdir(parents=True, exist_ok=True)
            except OSError:
                LOG.error(f"Could not create folder at '{folder}'.")
                raise

        try:
            db_file = Path(self._config.db_file)
            LOG.debug(f"Checking database file at '{db_file}'.")
            if not db_file.exists():
                LOG.info(f"Creating database file at '{db_file}'.")
                db_file.touch(exist_ok=True)
        except OSError as e:
            LOG.error(f"Could not create database file at '{self._config.db_file}'. {e!s}")
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

        self._socket.attach(self._app)
        self._http.attach(self._app)

        Presets.get_instance().attach(self._app)
        Tasks.get_instance().attach(self._app)
        Notification.get_instance().attach(self._app)
        Conditions.get_instance().attach(self._app)
        DLFields.get_instance().attach(self._app)
        TaskDefinitions.get_instance().attach(self._app)
        DownloadQueue.get_instance().attach(self._app)
        UpdateChecker.get_instance().attach(self._app)

        EventBus.get_instance().emit(
            Events.LOADED,
            data={"app": self._app},
            title="Application Loaded",
            message="The application has loaded all components.",
        )

        def started(_):
            LOG.info("=" * 40)
            LOG.info(f"YTPTube {self._config.app_version} - started on http://{host}:{port}{self._config.base_path}")
            LOG.info(f"Download path: {self._config.download_path}")
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
        if self._config.access_log:
            from app.library.HttpAPI import LOG as HTTP_LOGGER

            HTTP_LOGGER.addFilter(
                lambda record: f"GET {str(self._app.router['ping'].url_for()).rstrip('/')}" not in record.getMessage()
            )

        web.run_app(
            self._app,
            host=host,
            port=port,
            loop=asyncio.get_event_loop(),
            access_log=HTTP_LOGGER,
            print=started,
            handle_signals=cb is None,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    from multiprocessing import freeze_support

    freeze_support()
    Main().start()
