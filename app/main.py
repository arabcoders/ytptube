#!/usr/bin/env python3

import asyncio
import logging
import os
import random
import sqlite3
from datetime import datetime
from pathlib import Path

import caribou
import magic
from aiocron import crontab
from aiohttp import web
from library.config import Config
from library.DownloadQueue import DownloadQueue
from library.Emitter import Emitter
from library.encoder import Encoder
from library.HttpAPI import HttpAPI, LOG as http_logger
from library.HttpSocket import HttpSocket
from library.Webhooks import Webhooks

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
        self.encoder = Encoder()

        self.checkFolders()
        caribou.upgrade(self.config.db_file, os.path.join(self.rootPath, "migrations"))

        connection = sqlite3.connect(database=self.config.db_file, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=wal")

        emitter = Emitter()

        queue = DownloadQueue(emitter=emitter, connection=connection)
        self.app.on_startup.append(lambda _: queue.initialize())

        self.http = HttpAPI(queue=queue, emitter=emitter, encoder=self.encoder)
        self.socket = HttpSocket(queue=queue, emitter=emitter, encoder=self.encoder)

        WebhookFile = os.path.join(self.config.config_path, "webhooks.json")
        if os.path.exists(WebhookFile):
            emitter.add_emitter(Webhooks(WebhookFile).emit)

    def checkFolders(self) -> None:
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

    async def cron_runner(self, task: dict):
        try:
            taskName = task.get("name", task.get("url"))
            timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            LOG.info(f"Started 'Task: {taskName}' at '{timeNow}'.")
            await self.socket.add(
                url=task.get("url"),
                preset=task.get("preset", "default"),
                folder=task.get("folder"),
                ytdlp_cookies=task.get("ytdlp_cookies"),
                ytdlp_config=task.get("ytdlp_config"),
                output_template=task.get("output_template"),
            )
            timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            LOG.info(f"Completed 'Task: {taskName}' at '{timeNow}'.")
        except Exception as e:
            timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            LOG.error(f"Failed 'Task: {taskName}' at '{timeNow}'. Error message '{str(e)}'.")

    def load_tasks(self):
        for task in self.config.tasks:
            if not task.get("url"):
                LOG.warning(f"Invalid task '{task}'. No URL found.")
                continue

            cron_timer: str = task.get("timer", f"{random.randint(1,59)} */1 * * *")

            crontab(
                spec=cron_timer,
                func=self.cron_runner,
                args=(task,),
                start=True,
                loop=asyncio.get_event_loop(),
            )

            LOG.info(f"Added 'Task: {task.get('name', task.get('url'))}' to be executed every '{cron_timer}'.")

    def start(self):
        self.socket.attach(self.app)
        self.http.attach(self.app)

        self.load_tasks()

        def started(_):
            LOG.info("=" * 40)
            LOG.info(f"YTPTube v{self.config.version} - started on http://{self.config.host}:{self.config.port}")
            LOG.info("=" * 40)

        if self.config.access_log:
            http_logger.addFilter(lambda record: "GET /ping" not in record.getMessage())

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
