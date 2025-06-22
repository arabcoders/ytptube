#!/usr/bin/env python3
import sys
from pathlib import Path

APP_ROOT = str((Path(__file__).parent / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)


import asyncio
import logging
import sqlite3
from pathlib import Path

import caribou
import magic
from aiohttp import web

from app.library.conditions import Conditions
from app.library.config import Config
from app.library.DownloadQueue import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.HttpAPI import HttpAPI
from app.library.HttpSocket import HttpSocket
from app.library.Notifications import Notification
from app.library.Presets import Presets
from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.Tasks import Tasks

LOG = logging.getLogger("app")
MIME = magic.Magic(mime=True)

ROOT_PATH: Path = Path(__file__).parent.absolute()


class Main:
    def __init__(self, is_native: bool = False):
        self._config = Config.get_instance(is_native=is_native)
        self._app = web.Application()
        self.loop = asyncio.get_event_loop()
        self._app.on_shutdown.append(self.on_shutdown)

        Services.get_instance().add("app", self._app)

        if self._config.debug:
            self.loop.set_debug(True)
            self.loop.slow_callback_duration = 0.05

        self._check_folders()

        caribou.upgrade(self._config.db_file, ROOT_PATH / "migrations")

        connection = sqlite3.connect(database=self._config.db_file, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=wal")

        async def _close_connection(_):
            LOG.debug("Closing database connection.")
            connection.close()
            LOG.debug("Database connection closed.")

        try:
            db_file = Path(self._config.db_file)
            if "600" != oct(db_file.stat().st_mode)[-3:]:
                db_file.chmod(0o600)
        except Exception:
            pass

        self._queue = DownloadQueue(connection=connection)
        self._http = HttpAPI(root_path=ROOT_PATH, queue=self._queue)
        self._socket = HttpSocket(root_path=ROOT_PATH, queue=self._queue)

        self._app.on_cleanup.append(_close_connection)

    def _check_folders(self):
        """Check if the required folders exist and create them if they do not."""
        folders = (self._config.download_path, self._config.temp_path, self._config.config_path)

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
        await EventBus.get_instance().emit(Events.SHUTDOWN, data={"app": self._app})

    def start(self, host: str | None = None, port: int | None = None, cb=None):
        """
        Start the application.
        """
        host = host or self._config.host
        port = port or self._config.port

        EventBus.get_instance().sync_emit(Events.STARTUP, data={"app": self._app})
        Scheduler.get_instance().attach(self._app)

        self._socket.attach(self._app)
        self._http.attach(self._app)
        self._queue.attach(self._app)

        Tasks.get_instance().attach(self._app)
        Presets.get_instance().attach(self._app)
        Notification.get_instance().attach(self._app)
        Conditions.get_instance().attach(self._app)

        EventBus.get_instance().sync_emit(Events.LOADED, data={"app": self._app})

        def started(_):
            LOG.info("=" * 40)
            LOG.info(f"YTPTube {self._config.version} - started on http://{host}:{port}{self._config.base_path}")
            LOG.info("=" * 40)

            EventBus.get_instance().sync_emit(Events.STARTED, data={"app": self._app}, loop=self.loop, wait=False)

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
            reuse_port="win32" != sys.platform,
            loop=self.loop,
            access_log=HTTP_LOGGER,
            print=started,
            handle_signals=cb is None,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    Main().start()
