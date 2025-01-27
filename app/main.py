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
from library.Emitter import Emitter
from library.EventsSubscriber import EventsSubscriber
from library.HttpAPI import LOG as http_logger
from library.HttpAPI import HttpAPI
from library.HttpSocket import HttpSocket
from library.Notifications import Notification
from library.PackageInstaller import PackageInstaller
from library.Tasks import Tasks

LOG = logging.getLogger("app")
MIME = magic.Magic(mime=True)


class Main:
    config: Config
    app: web.Application
    http: HttpAPI
    socket: HttpSocket

    def __init__(self):
        self.config = Config.get_instance()
        self.rootPath = str(Path(__file__).parent.absolute())
        self.app = web.Application()

        self.checkFolders()

        try:
            PackageInstaller(self.config).check()
        except Exception as e:
            LOG.error(f"Failed to check for packages. Error message '{str(e)}'.")
            LOG.exception(e)

        caribou.upgrade(self.config.db_file, os.path.join(self.rootPath, "migrations"))

        connection = sqlite3.connect(database=self.config.db_file, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=wal")
        try:
            if "600" != oct(os.stat(self.config.db_file).st_mode)[-3:]:
                os.chmod(self.config.db_file, 0o600)
        except Exception:
            pass

        queue = DownloadQueue(connection=connection)

        self.http = HttpAPI(queue=queue)
        self.socket = HttpSocket(queue=queue)

        Emitter.get_instance().add_emitter([Notification().emit], local=False).add_emitter(
            [EventsSubscriber().emit], local=True
        )

        self.app.on_startup.append(lambda _: queue.initialize())

    def checkFolders(self):
        """
        Check if the required folders exist and create them if they do not.
        """
        try:
            LOG.debug(f"Checking download folder at '{self.config.download_path}'.")
            if not os.path.exists(self.config.download_path):
                LOG.info(f"Creating download folder at '{self.config.download_path}'.")
                os.makedirs(self.config.download_path, exist_ok=True)
        except OSError as e:
            LOG.error(f"Could not create download folder at '{self.config.download_path}'.")
            raise e

        try:
            LOG.debug(f"Checking temp folder at '{self.config.temp_path}'.")
            if not os.path.exists(self.config.temp_path):
                LOG.info(f"Creating temp folder at '{self.config.temp_path}'.")
                os.makedirs(self.config.temp_path, exist_ok=True)
        except OSError as e:
            LOG.error(f"Could not create temp folder at '{self.config.temp_path}'.")
            raise e

        try:
            LOG.debug(f"Checking config folder at '{self.config.config_path}'.")
            if not os.path.exists(self.config.config_path):
                LOG.info(f"Creating config folder at '{self.config.config_path}'.")
                os.makedirs(self.config.config_path, exist_ok=True)
        except OSError as e:
            LOG.error(f"Could not create config folder at '{self.config.config_path}'.")
            raise e

        try:
            LOG.debug(f"Checking database file at '{self.config.db_file}'.")
            if not os.path.exists(self.config.db_file):
                LOG.info(f"Creating database file at '{self.config.db_file}'.")
                with open(self.config.db_file, "w") as _:
                    pass
        except OSError as e:
            LOG.error(f"Could not create database file at '{self.config.db_file}'.")
            raise e

    def start(self):
        """
        Start the application.
        """
        self.socket.attach(self.app)
        self.http.attach(self.app)
        Tasks.get_instance().load()

        def started(_):
            LOG.info("=" * 40)
            LOG.info(f"YTPTube v{self.config.version} - started on http://{self.config.host}:{self.config.port}")
            LOG.info("=" * 40)

        if self.config.access_log:
            http_logger.addFilter(lambda record: "GET /api/ping" not in record.getMessage())

        web.run_app(
            self.app,
            host=self.config.host,
            port=self.config.port,
            reuse_port=True,
            loop=asyncio.get_event_loop(),
            access_log=http_logger if self.config.access_log else None,
            print=started,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    Main().start()
