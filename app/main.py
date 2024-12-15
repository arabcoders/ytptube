#!/usr/bin/env python3

import asyncio
import os
import random
import socketio
import logging
import caribou
import sqlite3
import magic
from datetime import datetime
from aiohttp import web
from pathlib import Path
from library.Utils import load_file
from library.Emitter import Emitter
from library.config import Config
from library.encoder import Encoder
from library.DownloadQueue import DownloadQueue
from library.Webhooks import Webhooks
from library.HttpSocket import HttpSocket
from library.HttpAPI import HttpAPI
from aiocron import crontab

LOG = logging.getLogger('app')
MIME = magic.Magic(mime=True)


class main:
    config: Config = None
    app: web.Application = None
    sio: socketio.AsyncServer = None
    routes: web.RouteTableDef = None
    loop: asyncio.AbstractEventLoop = None
    appLoader: str = None
    http: HttpAPI = None
    socket: HttpSocket = None

    def __init__(self):
        self.config = Config.get_instance()
        self.rootPath = str(Path(__file__).parent.absolute())
        self.app = web.Application()
        self.encoder = Encoder()

        self.checkDirectories()
        caribou.upgrade(self.config.db_file, os.path.join(self.rootPath, 'migrations'))

        connection = sqlite3.connect(database=self.config.db_file, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA journal_mode=wal')

        emitter = Emitter()

        queue = DownloadQueue(emitter=emitter, connection=connection)
        self.app.on_startup.append(lambda _: queue.initialize())

        self.http = HttpAPI(queue=queue, emitter=emitter, encoder=self.encoder)
        self.socket = HttpSocket(queue=queue, emitter=emitter, encoder=self.encoder)

        WebhookFile = os.path.join(self.config.config_path, 'webhooks.json')
        if os.path.exists(WebhookFile):
            emitter.add_emitter(Webhooks(WebhookFile).emit)

    def checkDirectories(self) -> None:
        try:
            LOG.debug(f'Checking download folder at [{self.config.download_path}]')
            if not os.path.exists(self.config.download_path):
                LOG.info(f'Creating download folder at [{self.config.download_path}]')
                os.makedirs(self.config.download_path, exist_ok=True)
        except OSError as e:
            LOG.error(f'Could not create download folder at [{self.config.download_path}]')
            raise e

        try:
            LOG.debug(f'Checking temp folder at [{self.config.temp_path}]')
            if not os.path.exists(self.config.temp_path):
                LOG.info(f'Creating temp folder at [{self.config.temp_path}]')
                os.makedirs(self.config.temp_path, exist_ok=True)
        except OSError as e:
            LOG.error(f'Could not create temp folder at [{self.config.temp_path}]')
            raise e

        try:
            LOG.debug(f'Checking config folder at [{self.config.config_path}]')
            if not os.path.exists(self.config.config_path):
                LOG.info(f'Creating config folder at [{self.config.config_path}]')
                os.makedirs(self.config.config_path, exist_ok=True)
        except OSError as e:
            LOG.error(f'Could not create config folder at [{self.config.config_path}]')
            raise e

        try:
            LOG.debug(f'Checking database file at [{self.config.db_file}]')
            if not os.path.exists(self.config.db_file):
                LOG.info(f'Creating database file at [{self.config.db_file}]')
                with open(self.config.db_file, 'w') as _:
                    pass
        except OSError as e:
            LOG.error(f'Could not create database file at [{self.config.db_file}]')
            raise e

    def load_tasks(self):
        tasks_file: str = os.path.join(self.config.config_path, 'tasks.json')
        if not os.path.exists(tasks_file):
            LOG.info(f'No tasks file found at {tasks_file}. Skipping Tasks.')
            return

        try:
            (tasks, status, error) = load_file(tasks_file, list)
            if status is False:
                raise Exception(error)
        except Exception as e:
            LOG.error(f"Could not load tasks file '{tasks_file}'. Error message '{str(e)}'. Skipping Tasks.")
            return

        for task in tasks:
            if not task.get('url'):
                LOG.warning(f'Invalid task {task}.')
                continue

            cron_timer: str = task.get('timer', f'{random.randint(1,59)} */1 * * *')

            async def cron_runner(task: dict):
                taskName = task.get("name", task.get("url"))
                timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                LOG.info(f'Started [Task: {taskName}] at [{timeNow}].')

                await self.add(
                    url=task.get('url'),
                    quality=task.get('quality', 'best'),
                    format=task.get('format', 'any'),
                    folder=task.get('folder'),
                    ytdlp_cookies=task.get('ytdlp_cookies'),
                    ytdlp_config=task.get('ytdlp_config'),
                    output_template=task.get('output_template')
                )

                timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                LOG.info(f'Completed [Task: {taskName}] at [{timeNow}].')

            crontab(
                spec=cron_timer,
                func=cron_runner,
                args=(task,),
                start=True,
                loop=self.loop
            )

            LOG.info(f'Added [Task: {task.get("name", task.get("url"))}] executed every [{cron_timer}].')

    def start(self):
        self.socket.attach(self.app)
        self.http.attach(self.app)

        self.load_tasks()

        start: str = f'YTPTube v{self.config.version} - listening on http://{self.config.host}:{self.config.port}'
        web.run_app(
            self.app,
            host=self.config.host,
            port=self.config.port,
            reuse_port=True,
            loop=asyncio.get_event_loop(),
            access_log=None,
            print=lambda _: LOG.info(start)
        )


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main().start()
