#!/usr/bin/env python3

import asyncio
from datetime import datetime
import json
import os
import random
from fastapi.responses import HTMLResponse, RedirectResponse
from Config import Config
from DownloadQueue import DownloadQueue
from Utils import ObjectSerializer, Notifier
from Webhooks import Webhooks
from Models import ItemAddRequest, ItemAddRequestCollection, deleteItemRequest
from player.M3u8 import M3u8
from player.Segments import Segments
import socketio
import logging
import caribou
import sqlite3
from aiocron import crontab
from fastapi import FastAPI, HTTPException, status, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

LOG = logging.getLogger('app')


class Main:
    config: Config = None
    serializer: ObjectSerializer = None
    app: FastAPI = None
    sio: socketio.AsyncServer = None
    connection: sqlite3.Connection = None
    queue: DownloadQueue = None
    loop: asyncio.AbstractEventLoop = None
    appLoader: str = None
    mapp: socketio.ASGIApp = None

    def __init__(self):
        self.config = Config.get_instance()

        try:
            if not os.path.exists(self.config.download_path):
                LOG.info(f'Creating download folder at [{self.config.download_path}]')
                os.makedirs(self.config.download_path, exist_ok=True)
        except OSError as e:
            LOG.error(f'Could not create download folder at [{self.config.download_path}]')
            raise e

        try:
            if not os.path.exists(self.config.temp_path):
                LOG.info(f'Creating temp folder at [{self.config.temp_path}]')
                os.makedirs(self.config.temp_path, exist_ok=True)
        except OSError as e:
            LOG.error(f'Could not create temp folder at [{self.config.temp_path}]')
            raise e

        try:
            if not os.path.exists(self.config.config_path):
                LOG.info(f'Creating config folder at [{self.config.config_path}]')
                os.makedirs(self.config.config_path, exist_ok=True)
        except OSError as e:
            LOG.error(f'Could not create config folder at [{self.config.config_path}]')
            raise e

        try:
            if not os.path.exists(self.config.db_file):
                LOG.info(f'Creating database file at [{self.config.db_file}]')
                with open(self.config.db_file, 'w') as _:
                    pass
        except OSError as e:
            LOG.error(f'Could not create database file at [{self.config.db_file}]')
            raise e

        caribou.upgrade(self.config.db_file, os.path.join(os.path.realpath(os.path.dirname(__file__)), 'migrations'))

        self.webhooks = Webhooks(os.path.join(self.config.config_path, 'webhooks.json'))
        self.loop = asyncio.get_event_loop()
        self.serializer = ObjectSerializer()

        self.sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins='*')

        self.connection = sqlite3.connect(self.config.db_file, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA journal_mode=wal')

        self.queue = DownloadQueue(
            notifier=Notifier(sio=self.sio, serializer=self.serializer, webhooks=self.webhooks),
            connection=self.connection,
            serializer=self.serializer,
        )

        def startup_logo():
            print(f'YTPTube v{self.config.version} - listening on http://{self.config.host}:{self.config.port}'),

        self.app = FastAPI(
            debug=self.config.ytdl_debug,
            title='YTPTube',
            version=self.config.version,
            on_startup=[startup_logo, self.queue.initialize],
        )

        self.mapp = socketio.ASGIApp(
            socketio_server=self.sio,
            socketio_path=f'{self.config.url_prefix}socket.io',
            other_asgi_app=self.app,
        )

        self.addRoutes()

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.addTasks()

    def start(self):
        uvicorn.run(
            app='main:app',
            host=self.config.host,
            port=self.config.port,
            log_level='info',
            access_log=True,
            reload=True,
            workers=4,
        )

    async def connect(self, sid, _):
        data: dict = {
            **self.queue.get(),
            "config": self.config,
            "tasks": [],
        }

        if os.path.exists(os.path.join(self.config.config_path, 'tasks.json')):
            try:
                with open(os.path.join(self.config.config_path, 'tasks.json'), 'r') as f:
                    data['tasks'] = json.load(f)
            except Exception as e:
                pass

        await self.sio.emit('initial_data', self.serializer.encode(data), to=sid)

    async def version_check(self):
        try:
            with client.ClientSession() as session:
                async with session.get('https://api.github.com/repos/ytptube/ytptube/tags') as r:
                    if r.status != 200:
                        return

                    tags = await r.json()

                    for tag in tags:
                        tagName = tag.get('name')
                        splitTagName = tagName.split('-')
                        if len(splitTagName) > 1:
                            tagName = splitTagName[0]
                        cvDate = self.config.version.split('-')
                        if tagName > cvDate[0]:
                            self.config.new_version_available = True
                            LOG.info(f'New version [{tagName}] is available.')
                        break
        except Exception as e:
            pass

    def addTasks(self):
        tasks_file: str = os.path.join(self.config.config_path, 'tasks.json')
        if not os.path.exists(tasks_file):
            LOG.info(
                f'No tasks file found at {tasks_file}. Skipping Tasks.')
            return

        try:
            with open(tasks_file, 'r') as f:
                tasks = json.load(f)
        except Exception as e:
            LOG.error(f'Could not load tasks file [{tasks_file}]. Error message [{str(e)}]. Skipping Tasks.')
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

    def addRoutes(self):
        @self.app.get(f'{self.config.url_prefix}ping')
        async def ping() -> dict:
            self.connection.execute('SELECT "id" FROM "history" LIMIT 1').fetchone()
            return {'response': 'pong'}

        @self.app.post(f'{self.config.url_prefix}add')
        async def add(req: ItemAddRequest) -> dict:
            if not req.url:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='url is required.')

            status = await self.add(
                url=req.url,
                quality=req.quality,
                format=req.format,
                folder=req.folder,
                ytdlp_cookies=req.ytdlp_cookies,
                ytdlp_config=req.ytdlp_config if req.ytdlp_config else {},
                output_template=req.output_template
            )

            return status

        @self.app.get(f'{self.config.url_prefix}tasks')
        async def task() -> dict:
            tasks_file: str = os.path.join(self.config.config_path, 'tasks.json')

            if not os.path.exists(tasks_file):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": 'No tasks defined.'})

            try:
                with open(tasks_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": str(e)})

        @self.app.post(f'{self.config.url_prefix}add_batch')
        async def add_batch(req: ItemAddRequestCollection) -> dict:
            r_status = {}

            if not isinstance(req.items, list):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Invalid request body expecting list with dicts.'
                )

            for item in req.items:
                if not isinstance(item, ItemAddRequest):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail='Invalid request body expecting list with dicts.')

                if item.url is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='url is required.')

                r_status[item.url] = await self.add(
                    url=item.url,
                    quality=item.quality,
                    format=item.format,
                    folder=item.folder,
                    ytdlp_cookies=item.ytdlp_cookies,
                    ytdlp_config=item.ytdlp_config if item.ytdlp_config else {},
                    output_template=item.output_template
                )

            return r_status

        @self.app.delete(f'{self.config.url_prefix}delete')
        async def delete(req: deleteItemRequest) -> dict:
            if not req.ids or req.where not in ['queue', 'done']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='ids and where are required.'
                )

            if req.where == 'queue':
                status = await self.queue.cancel(req.ids)
            else:
                status = self.queue.clear(req.ids)

            LOG.info(f'Deleted [{len(req.ids)}] items from [{req.where}].')

            return status

        @self.app.get(f'{self.config.url_prefix}history')
        async def history() -> dict:
            queue = []
            done = []

            for _, v in self.queue.queue.saved_items():
                queue.append(v)

            for _, v in self.queue.done.saved_items():
                done.append(v)

            return {'queue': queue, 'done': done}

        @self.app.get(self.config.url_prefix + 'm3u8/{file:.*}')
        async def m3u8(file: str) -> Response:
            if not file:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='file is required')

            return Response(
                content=M3u8(
                    url=f"{self.config.url_host}{self.config.url_prefix}"
                ).make_stream(
                    download_path=self.config.download_path,
                    file=file
                ),
                status_code=status.HTTP_200_OK,
                media_type='application/x-mpegURL',
                headers={
                    'Cache-Control': 'no-cache',
                    'Access-Control-Max-Age': "300",
                }
            )

        @self.app.get(self.config.url_prefix + 'segments/{segment:\d+}/{file:.*}')
        async def segments(segment: int, file: str, sd: int = 0, vc: int = 0, ac: int = 0) -> Response:
            if not file:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='file is required')

            if not segment:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='segment is required')

            segmenter = Segments(
                segment_index=segment,
                segment_duration=float('{:.6f}'.format(float(sd if sd else M3u8.segment_duration))),
                vconvert=True if vc == 1 else False,
                aconvert=True if ac == 1 else False
            )

            return Response(
                content=await segmenter.stream(download_path=self.config.download_path, file=file),
                status_code=status.HTTP_200_OK,
                media_type='video/mpegts',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Max-Age': "300",
                }
            )

        @self.app.get(f'{self.config.url_prefix}')
        async def index() -> HTMLResponse:
            if not self.appLoader:
                with open(os.path.join(
                    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    'frontend/dist/index.html'
                ), 'r') as f:
                    self.appLoader = f.read()

            return HTMLResponse(content=self.appLoader, status_code=status.HTTP_200_OK)

        @self.sio.event
        async def connect(sid, environ, auth):
            await self.connect(sid, environ)

        if self.config.url_prefix != '/':
            @self.app.get('/')
            async def redirect_d() -> RedirectResponse:
                return RedirectResponse(self.config.url_prefix)

            @self.app.get(self.config.url_prefix[:-1])
            async def redirect_w() -> RedirectResponse:
                return RedirectResponse(self.config.url_prefix)

        @self.app.options(f'{self.config.url_prefix}add')
        async def add_cors() -> dict:
            return {"status": "ok"}

        @self.app.options(f'{self.config.url_prefix}delete')
        async def delete_cors() -> dict:
            return {"status": "ok"}

        self.app.mount(
            path=f'{self.config.url_prefix}download/',
            app=StaticFiles(directory=self.config.download_path),
            name="downloads"
        )

        self.app.mount(
            path=self.config.url_prefix,
            app=StaticFiles(
                directory=os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'frontend/dist')
            ),
            name="frontend"
        )

    async def add(self, url: str, quality: str, format: str, folder: str, ytdlp_cookies: str,
                  ytdlp_config: dict, output_template: str) -> dict[str, str]:

        if ytdlp_config is None:
            ytdlp_config = {}

        if ytdlp_cookies and isinstance(ytdlp_cookies, dict):
            ytdlp_cookies = self.serializer.encode(ytdlp_cookies)

        status = await self.queue.add(
            url=url,
            format=format if format else 'any',
            quality=quality if quality else 'best',
            folder=folder,
            ytdlp_cookies=ytdlp_cookies,
            ytdlp_config=ytdlp_config,
            output_template=output_template
        )

        return status


main = Main()
app = main.mapp

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main.start()
