#!/usr/bin/env python3

import asyncio
import json
import logging
import os
import random
import sqlite3
from datetime import datetime
from pathlib import Path
import time
from typing import TypedDict
import uuid

import caribou
import magic
from aiocron import crontab, Cron
from aiohttp import web
from library.Utils import load_file
from library.config import Config
from library.DownloadQueue import DownloadQueue
from library.Emitter import Emitter
from library.encoder import Encoder
from library.HttpAPI import HttpAPI, LOG as http_logger
from library.HttpSocket import HttpSocket
from library.Webhooks import Webhooks
from library.PackageInstaller import PackageInstaller

LOG = logging.getLogger("app")
MIME = magic.Magic(mime=True)


class job_item(TypedDict):
    name: str
    job: Cron


class Main:
    config: Config
    app: web.Application
    http: HttpAPI
    socket: HttpSocket
    cron: list[job_item] = []

    def __init__(self):
        self.config = Config.get_instance()
        self.rootPath = str(Path(__file__).parent.absolute())
        self.app = web.Application()
        self.encoder = Encoder()

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

        self.emitter = Emitter()

        queue = DownloadQueue(emitter=self.emitter, connection=connection)
        self.app.on_startup.append(lambda _: queue.initialize())

        self.http = HttpAPI(queue=queue, emitter=self.emitter, encoder=self.encoder, load_tasks=self.load_tasks)
        self.socket = HttpSocket(queue=queue, emitter=self.emitter, encoder=self.encoder)

        WebhookFile = os.path.join(self.config.config_path, "webhooks.json")
        if os.path.exists(WebhookFile):
            self.emitter.add_emitter(Webhooks(WebhookFile).emit)

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
            started = time.time()
            url = task.get("url")
            if not url:
                LOG.error(f"Invalid task '{task}'. No URL found.")
                return

            preset: str = str(task.get("preset", self.config.default_preset))
            folder: str = str(task.get("folder")) if task.get("folder") else ""
            ytdlp_cookies: str = str(task.get("ytdlp_cookies")) if task.get("ytdlp_cookies") else ""
            output_template: str = str(task.get("output_template")) if task.get("output_template") else ""

            ytdlp_config = task.get("ytdlp_config")
            if isinstance(ytdlp_config, str) and ytdlp_config:
                try:
                    ytdlp_config = json.loads(ytdlp_config)
                except Exception as e:
                    LOG.error(f"Failed to parse json yt-dlp config for '{taskName}'. {str(e)}")
                    return

            await self.emitter.info(f"Started 'Task: {taskName}' at '{timeNow}'.")
            LOG.info(f"Started 'Task: {taskName}' at '{timeNow}'.")
            await self.socket.add(
                url=url,
                preset=preset,
                folder=folder,
                ytdlp_cookies=ytdlp_cookies,
                ytdlp_config=ytdlp_config,
                output_template=output_template,
            )
            timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            ended = time.time()
            LOG.info(f"Completed 'Task: {taskName}' at '{timeNow}' ")

            await self.emitter.success(f"Completed 'Task: {taskName}' '{ended - started:.2f}' seconds.")
        except Exception as e:
            timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            LOG.error(f"Failed 'Task: {taskName}' at '{timeNow}'. Error message '{str(e)}'.")
            await self.emitter.error(f"Failed 'Task: {taskName}' at '{timeNow}'. Error message '{str(e)}'.")

    def load_tasks(self):
        tasksFile = os.path.join(self.config.config_path, "tasks.json")
        if not os.path.exists(tasksFile):
            return

        LOG.info(f"Loading tasks from '{tasksFile}'.")
        try:
            (tasks, status, error) = load_file(tasksFile, list)
            if not status:
                LOG.error(f"Could not load tasks file from '{tasksFile}'. '{error}'.")
                return
        except Exception:
            pass

        for job in self.cron:
            try:
                LOG.info(f"Stopping job '{job['name']}'.")
                job["job"].stop()
            except Exception as e:
                LOG.error(f"Failed to stop job. Error message '{str(e)}'.")
                LOG.exception(e)

        self.cron.clear()

        if not tasks or len(tasks) < 1:
            LOG.info(f"No tasks found in '{tasksFile}'.")
            return

        modified = False
        loop = asyncio.get_event_loop()
        for task in tasks:
            if not task.get("url"):
                LOG.warning(f"Invalid task '{task}'. No URL found.")
                continue

            try:
                if not task.get("timer", None):
                    task["timer"] = f"{random.randint(1,59)} */1 * * *"
                    modified = True

                if not task.get("id", None):
                    task["id"] = str(uuid.uuid4())
                    modified = True

                self.cron.append(
                    job_item(
                        name=task.get("name", "??"),
                        job=crontab(
                            spec=task.get("timer"),
                            func=self.cron_runner,
                            args=(task,),
                            start=True,
                            loop=loop,
                        ),
                    )
                )

                LOG.info(f"Queued 'Task: {task.get('name','??')}' to be executed every '{task.get('timer')}'.")
            except Exception as e:
                LOG.error(f"Failed to add 'Task: {task.get('name', '??')}'. Error message '{str(e)}'.")
                LOG.exception(e)

        if modified:
            try:
                with open(tasksFile, "w") as f:
                    f.write(json.dumps(tasks, indent=4))
            except Exception as e:
                LOG.error(f"Failed to save tasks file '{tasksFile}'. Error message '{str(e)}'.")
                LOG.exception(e)

        self.config.tasks = tasks

    def start(self):
        self.socket.attach(self.app)
        self.http.attach(self.app)

        self.load_tasks()

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
