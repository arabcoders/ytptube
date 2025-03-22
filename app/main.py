#!/usr/bin/env python3

import asyncio
import logging
import os
import sqlite3
from pathlib import Path

import caribou
import magic
from aiohttp import web
from library.config import Config
from library.DownloadQueue import DownloadQueue
from library.Events import EventBus, Events
from library.HttpAPI import HttpAPI
from library.HttpSocket import HttpSocket
from library.Notifications import Notification
from library.PackageInstaller import PackageInstaller
from library.Presets import Presets
from library.Scheduler import Scheduler
from library.Tasks import Tasks

LOG = logging.getLogger("app")
MIME = magic.Magic(mime=True)


class Main:
    def __init__(self):
        self._config = Config.get_instance()
        self.rootPath = str(Path(__file__).parent.absolute())
        self._app = web.Application()

        self._check_folders()

        try:
            PackageInstaller(self._config).check()
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Failed to check for packages. Error message '{e!s}'.")

        caribou.upgrade(self._config.db_file, os.path.join(self.rootPath, "migrations"))

        connection = sqlite3.connect(database=self._config.db_file, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=wal")

        async def _close_connection(_):
            LOG.debug("Closing database connection.")
            connection.close()
            LOG.debug("Database connection closed.")

        try:
            if "600" != oct(os.stat(self._config.db_file).st_mode)[-3:]:
                os.chmod(self._config.db_file, 0o600)
        except Exception:
            pass

        self._queue = DownloadQueue(connection=connection)
        self._http = HttpAPI(queue=self._queue)
        self._socket = HttpSocket(queue=self._queue)

        self._app.on_cleanup.append(_close_connection)

    def _check_folders(self):
        """Check if the required folders exist and create them if they do not."""
        folders = (self._config.download_path, self._config.temp_path, self._config.config_path)

        for folder in folders:
            try:
                LOG.debug(f"Checking folder at '{folder}'.")
                if not os.path.exists(folder):
                    LOG.info(f"Creating folder at '{folder}'.")
                    os.makedirs(folder, exist_ok=True)
            except OSError:
                LOG.error(f"Could not create folder at '{folder}'.")
                raise

        try:
            LOG.debug(f"Checking database file at '{self._config.db_file}'.")
            if not os.path.exists(self._config.db_file):
                LOG.info(f"Creating database file at '{self._config.db_file}'.")
                with open(self._config.db_file, "w") as _:
                    pass
        except OSError:
            LOG.error(f"Could not create database file at '{self._config.db_file}'.")
            raise

    def start(self):
        """
        Start the application.
        """
        EventBus.get_instance().sync_emit(Events.STARTUP, data={"app": self._app})

        self._socket.attach(self._app)
        self._http.attach(self._app)
        self._queue.attach(self._app)
        Scheduler.get_instance().attach(self._app)
        Tasks.get_instance().attach(self._app)
        Presets.get_instance().attach(self._app)
        Notification.get_instance().attach(self._app)

        EventBus.get_instance().sync_emit(Events.LOADED, data={"app": self._app})

        def started(_):
            LOG.info("=" * 40)
            LOG.info(f"YTPTube v{self._config.version} - started on http://{self._config.host}:{self._config.port}")
            LOG.info("=" * 40)

        HTTP_LOGGER = None
        if self._config.access_log:
            from library.HttpAPI import LOG as HTTP_LOGGER

            HTTP_LOGGER.addFilter(lambda record: "GET /api/ping" not in record.getMessage())

        web.run_app(
            self._app,
            host=self._config.host,
            port=self._config.port,
            reuse_port=True,
            loop=asyncio.get_event_loop(),
            access_log=HTTP_LOGGER,
            print=started,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    Main().start()
