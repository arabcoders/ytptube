#!/usr/bin/env python3

import asyncio
from datetime import datetime
import json
import os
import random
from Config import Config
from DownloadQueue import DownloadQueue
from Utils import ObjectSerializer, Notifier
from aiohttp import web
from aiohttp.web import Request, Response
from player.M3u8 import M3u8
from player.Segments import Segments
import socketio
import logging
import caribou
import sqlite3
from aiocron import crontab

class Main:
    config: Config = None
    serializer: ObjectSerializer = None
    app: web.Application = None
    sio: socketio.AsyncServer = None
    routes: web.RouteTableDef = None
    connection: sqlite3.Connection = None
    dqueue: DownloadQueue = None
    loop: asyncio.AbstractEventLoop = None
    logger: logging.Logger = None

    def __init__(self):
        self.config = Config()
        self.logger = logging.getLogger('main')

        try:
            if not os.path.exists(self.config.download_path):
                self.logger.info(
                    f'Creating download folder at {self.config.download_path}')
                os.makedirs(self.config.download_path, exist_ok=True)
        except OSError as e:
            self.logger.error(
                f'Could not create download folder at {self.config.download_path}')
            raise e
        try:
            if not os.path.exists(self.config.temp_path):
                self.logger.info(
                    f'Creating temp folder at {self.config.temp_path}')
                os.makedirs(self.config.temp_path, exist_ok=True)
        except OSError as e:
            self.logger.error(
                f'Could not create temp folder at {self.config.temp_path}')
            raise e

        try:
            if not os.path.exists(self.config.config_path):
                self.logger.info(
                    f'Creating config folder at {self.config.config_path}')
                os.makedirs(self.config.config_path, exist_ok=True)
        except OSError as e:
            self.logger.error(
                f'Could not create config folder at {self.config.config_path}')
            raise e

        try:
            if not os.path.exists(self.config.db_file):
                self.logger.info(
                    f'Creating database file at {self.config.db_file}')
                with open(self.config.db_file, 'w') as _:
                    pass
        except OSError as e:
            self.logger.error(
                f'Could not create database file at {self.config.db_file}')
            raise e

        caribou.upgrade(self.config.db_file, os.path.join(
            os.path.realpath(os.path.dirname(__file__)), 'migrations'))

        self.loop = asyncio.get_event_loop()
        self.serializer = ObjectSerializer()
        self.app = web.Application()
        self.sio = socketio.AsyncServer(cors_allowed_origins='*')
        self.sio.attach(
            self.app, socketio_path=self.config.url_prefix + 'socket.io')
        self.routes = web.RouteTableDef()
        self.connection = sqlite3.connect(self.config.db_file)
        self.dqueue = DownloadQueue(
            self.config,
            Notifier(sio=self.sio, serializer=self.serializer),
            connection=self.connection,
            serializer=self.serializer
        )
        self.app.on_startup.append(lambda _: self.dqueue.initialize())
        self.addRoutes()
        self.addTasks()
        self.start()

    def start(self):
        web.run_app(
            self.app,
            host=self.config.host,
            port=self.config.port,
            reuse_port=True,
            loop=self.loop,
            print=lambda _: print(
                f'YTPTube v{self.config.version} - listening on http://{self.config.host}:{self.config.port}'),
        )

    async def connect(self, sid, _):
        self.logger.info(f'Config [{self.config.__dict__}].')
        data: dict = {
            **self.dqueue.get(),
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

    def addTasks(self):
        tasks_file: str = os.path.join(self.config.config_path, 'tasks.json')
        if not os.path.exists(tasks_file):
            self.logger.info(
                f'No tasks file found at {tasks_file}. Skipping Tasks.')
            return

        try:
            with open(tasks_file, 'r') as f:
                tasks = json.load(f)
        except Exception as e:
            self.logger.error(
                f'Could not load tasks file [{tasks_file}]. Error message [{str(e)}]. Skipping Tasks.')
            return

        for task in tasks:
            if not task.get('url'):
                self.logger.warning(f'Invalid task {task}.')
                continue

            cron_timer: str = task.get(
                'timer', f'{random.randint(1,59)} */1 * * *')

            async def cron_runner(task: dict):
                self.logger.info(
                    f'Running task [{task.get("name",task.get("url"))}] at [{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}].')

                await self.add(
                    url=task.get('url'),
                    quality=task.get('quality', 'best'),
                    format=task.get('format', 'any'),
                    folder=task.get('folder'),
                    ytdlp_cookies=task.get('ytdlp_cookies'),
                    ytdlp_config=task.get('ytdlp_config'),
                    output_template=task.get('output_template')
                )

                self.logger.info(
                    f'Finished Running task [{task.get("name",task.get("url"))}] at [{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}].')

            crontab(
                spec=cron_timer,
                func=cron_runner,
                args=(task,),
                start=True,
                loop=self.loop
            )

            self.logger.info(
                f'Added task to grab {task.get("name",task.get("url"))} content every [{cron_timer}].')

    def addRoutes(self):
        @self.routes.post(self.config.url_prefix + 'add')
        async def add(request: Request) -> Response:
            post = await request.json()

            url: str = post.get('url')
            quality: str = post.get('quality')

            if not url:
                raise web.HTTPBadRequest()

            format: str = post.get('format')
            folder: str = post.get('folder')
            ytdlp_cookies: str = post.get('ytdlp_cookies')
            ytdlp_config: dict = post.get('ytdlp_config')
            output_template: str = post.get('output_template')
            if ytdlp_config is None:
                ytdlp_config = {}

            status = await self.add(
                url=url,
                quality=quality,
                format=format,
                folder=folder,
                ytdlp_cookies=ytdlp_cookies,
                ytdlp_config=ytdlp_config,
                output_template=output_template
            )

            return web.Response(text=self.serializer.encode(status))

        @self.routes.get(self.config.url_prefix + 'tasks')
        async def tasks(_: Request) -> Response:
            tasks_file: str = os.path.join(
                self.config.config_path, 'tasks.json')

            if not os.path.exists(tasks_file):
                return web.json_response({"error": "No tasks defined."}, status=404)

            try:
                with open(tasks_file, 'r') as f:
                    tasks = json.load(f)
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)

            return web.json_response(tasks)

        @self.routes.post(self.config.url_prefix + 'add_batch')
        async def add_batch(request: Request) -> Response:
            status = {}

            post = await request.json()
            if not isinstance(post, list):
                raise web.HTTPBadRequest()

            for item in post:
                if not isinstance(item, dict):
                    raise web.HTTPBadRequest(
                        'Invalid request body expecting list with dicts.')
                if not item.get('url'):
                    raise web.HTTPBadRequest(reason='url is required')

                status[item.get('url')] = await self.add(
                    url=item.get('url'),
                    quality=item.get('quality'),
                    format=item.get('format'),
                    folder=item.get('folder'),
                    ytdlp_cookies=item.get('ytdlp_cookies'),
                    ytdlp_config=item.get('ytdlp_config'),
                    output_template=item.get('output_template')
                )

            return web.Response(text=self.serializer.encode(status))

        @self.routes.delete(self.config.url_prefix + 'delete')
        async def delete(request: Request) -> Response:
            post = await request.json()
            ids = post.get('ids')
            where = post.get('where')

            if not ids or where not in ['queue', 'done']:
                raise web.HTTPBadRequest()

            status = await (self.dqueue.cancel(ids) if where == 'queue' else self.dqueue.clear(ids))

            return web.Response(text=self.serializer.encode(status))

        @self.routes.get(self.config.url_prefix + 'history')
        async def history(_) -> Response:
            history = {'done': [], 'queue': []}

            for _, v in self.dqueue.queue.saved_items():
                history['queue'].append(v)
            for _, v in self.dqueue.done.saved_items():
                history['done'].append(v)

            return web.Response(text=self.serializer.encode(history))

        @self.routes.get(self.config.url_prefix + 'm3u8/{file:.*}')
        async def m3u8(request: Request) -> Response:
            file: str = request.match_info.get('file')

            if not file:
                raise web.HTTPBadRequest(reason='file is required')

            return web.Response(
                text=M3u8(url=f"{self.config.url_host}{self.config.url_prefix}").make_stream(
                    download_path=self.config.download_path,
                    file=file
                ),
                headers={
                    'Content-Type': 'application/x-mpegURL',
                    'Cache-Control': 'no-cache',
                    'Access-Control-Max-Age': "300",
                }
            )

        @self.routes.get(self.config.url_prefix + 'segments/{segment:\d+}/{file:.*}')
        async def segments(request: Request) -> Response:
            file: str = request.match_info.get('file')
            segment: int = request.match_info.get('segment')
            sd: int = request.query.get('sd')
            vc: int = int(request.query.get('vc', 0))
            ac: int = int(request.query.get('ac', 0))

            if not file:
                raise web.HTTPBadRequest(reason='file is required')

            if not segment:
                raise web.HTTPBadRequest(reason='segment is required')

            segmenter = Segments(
                segment_index=int(segment),
                segment_duration=float('{:.6f}'.format(
                    float(sd if sd else M3u8.segment_duration))),
                vconvert=True if vc == 1 else False,
                aconvert=True if ac == 1 else False
            )

            return web.Response(
                body=await segmenter.stream(download_path=self.config.download_path, file=file),
                headers={
                    'Content-Type': 'video/mpegts',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Max-Age': "300",
                }
            )

        @self.routes.get(self.config.url_prefix)
        async def index(_) -> Response:
            return web.FileResponse(os.path.join(
                os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                'frontend/dist/index.html'
            ))

        @self.sio.event()
        async def connect(sid, environ):
            await self.connect(sid, environ)

        if self.config.url_prefix != '/':
            @self.routes.get('/')
            async def redirect_d(_) -> Response:
                return web.HTTPFound(self.config.url_prefix)

            @self.routes.get(self.config.url_prefix[:-1])
            async def redirect_w(_) -> Response:
                return web.HTTPFound(self.config.url_prefix)

        @self.routes.options(self.config.url_prefix + 'add')
        async def add_cors(_) -> Response:
            return web.Response(text=self.serializer.encode({"status": "ok"}))

        @self.routes.options(self.config.url_prefix + 'delete')
        async def delete_cors(_) -> Response:
            return web.Response(text=self.serializer.encode({"status": "ok"}))

        self.routes.static(
            self.config.url_prefix +
            'download/', self.config.download_path)

        self.routes.static(
            self.config.url_prefix,
            os.path.join(os.path.dirname(os.path.dirname(
                os.path.realpath(__file__))), 'frontend/dist')
        )

        try:
            self.app.add_routes(self.routes)

            async def on_prepare(request, response):
                if 'Origin' in request.headers:
                    response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
                    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
                    response.headers['Access-Control-Allow-Methods'] = 'PUT, POST, DELETE'

            self.app.on_response_prepare.append(on_prepare)
        except ValueError as e:
            if 'frontend/dist' in str(e):
                raise RuntimeError(
                    'Could not find the frontend UI static assets. Please run `node_modules/.bin/ng build` inside the frontend folder.') from e
            raise e

    async def add(
        self,
            url: str,
            quality: str,
            format: str,
            folder: str,
            ytdlp_cookies: str,
            ytdlp_config: dict,
            output_template: str
    ) -> dict[str, str]:
        if ytdlp_config is None:
            ytdlp_config = {}

        if ytdlp_cookies and isinstance(ytdlp_cookies, dict):
            ytdlp_cookies = self.serializer.encode(ytdlp_cookies)

        status = await self.dqueue.add(
            url=url,
            format=format if format else 'any',
            quality=quality if quality else 'best',
            folder=folder,
            ytdlp_cookies=ytdlp_cookies,
            ytdlp_config=ytdlp_config,
            output_template=output_template
        )

        return status


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main = Main()
