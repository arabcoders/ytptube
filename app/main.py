#!/usr/bin/env python3

import asyncio
from datetime import datetime
import json
import os
import random
from Config import Config
from DownloadQueue import DownloadQueue
from Utils import ObjectSerializer, Notifier
from aiohttp import web, client
from aiohttp.web import Request, Response
from Webhooks import Webhooks
from player.M3u8 import M3u8
from player.Segments import Segments
import socketio
import logging
import caribou
import sqlite3
from aiocron import crontab
import magic

LOG = logging.getLogger('app')
MIME = magic.Magic(mime=True)


class Main:
    config: Config = None
    serializer: ObjectSerializer = None
    app: web.Application = None
    sio: socketio.AsyncServer = None
    routes: web.RouteTableDef = None
    connection: sqlite3.Connection = None
    queue: DownloadQueue = None
    loop: asyncio.AbstractEventLoop = None
    appLoader: str = None

    staticHolder: dict = {}

    extToMime: dict = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.ico': 'image/x-icon',
    }

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

        self.app = web.Application()
        self.sio = socketio.AsyncServer(cors_allowed_origins='*')
        self.sio.attach(self.app, socketio_path=self.config.url_prefix + 'socket.io')

        self.routes = web.RouteTableDef()

        self.connection = sqlite3.connect(self.config.db_file, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA journal_mode=wal')

        self.notifier = Notifier(sio=self.sio, serializer=self.serializer, webhooks=self.webhooks)
        self.queue = DownloadQueue(notifier=self.notifier, connection=self.connection, serializer=self.serializer)

        self.app.on_startup.append(lambda _: self.queue.initialize())
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
            access_log=None,
            print=lambda _: print(
                f'YTPTube v{self.config.version} - listening on http://{self.config.host}:{self.config.port}'),
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
        @self.routes.get(self.config.url_prefix + 'ping')
        async def ping(_) -> Response:
            self.connection.execute('SELECT "id" FROM "history" LIMIT 1').fetchone()
            return web.Response(text='pong')

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
            tasks_file: str = os.path.join(self.config.config_path, 'tasks.json')

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
                    raise web.HTTPBadRequest(reason='Invalid request body expecting list with dicts.')
                if not item.get('url'):
                    raise web.HTTPBadRequest(reason='url is required.')

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

            status = await (self.queue.cancel(ids) if where == 'queue' else self.queue.clear(ids))

            return web.Response(text=self.serializer.encode(status))

        @self.routes.post(self.config.url_prefix + 'item/{id}')
        async def update_item(request: Request) -> Response:
            id: str = request.match_info.get('id')
            if not id:
                raise web.HTTPBadRequest(reason='id is required.')

            item = self.queue.done.getById(id)
            if not item:
                raise web.HTTPNotFound(reason='Item not found.')

            try:
                post = await request.json()
                if not post:
                    raise web.HTTPBadRequest(reason='no data provided.')
            except Exception as e:
                raise web.HTTPBadRequest(reason=str(e))

            updated = False

            for k, v in post.items():
                if not hasattr(item.info, k):
                    continue

                if getattr(item.info, k) == v:
                    continue

                updated = True
                setattr(item.info, k, v)
                LOG.info(f'Updated [{k}] to [{v}] for [{item.info.id}]')

            status = 200 if updated else 304
            if updated:
                self.queue.done.put(item)
                await self.notifier.emit('update', item.info)

            return web.Response(text=self.serializer.encode(item.info), status=status)

        @self.routes.get(self.config.url_prefix + 'history')
        async def history(_) -> Response:
            history = {'done': [], 'queue': []}

            for _, v in self.queue.queue.saved_items():
                history['queue'].append(v)
            for _, v in self.queue.done.saved_items():
                history['done'].append(v)

            return web.Response(text=self.serializer.encode(history))

        @self.routes.get(self.config.url_prefix + 'm3u8/{file:.*}')
        async def m3u8(request: Request) -> Response:
            file: str = request.match_info.get('file')

            if not file:
                raise web.HTTPBadRequest(reason='file is required.')

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
                segment_duration=float('{:.6f}'.format(float(sd if sd else M3u8.segment_duration))),
                vconvert=True if vc == 1 else False,
                aconvert=True if ac == 1 else False
            )

            return web.Response(
                body=await segmenter.stream(download_path=self.config.download_path, file=file),
                headers={
                    'Content-Type': 'video/mpegts',
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Max-Age': "300",
                }
            )

        @self.routes.get(self.config.url_prefix)
        async def index(_) -> Response:
            if not self.appLoader:
                with open(os.path.join(
                    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    'frontend/dist/index.html'
                ), 'r') as f:
                    self.appLoader = f.read()

            return web.Response(text=self.appLoader, content_type='text/html', charset='utf-8', status=200)

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

        @self.routes.options(f'{self.config.url_prefix}delete')
        async def delete_cors(_) -> Response:
            return web.Response(text=self.serializer.encode({"status": "ok"}))

        self.routes.static(f'{self.config.url_prefix}download/', self.config.download_path)

        async def staticFile(req: Request) -> Response:
            if req.path not in self.staticHolder:
                return web.HTTPNotFound()

            item: dict = self.staticHolder[req.path]

            return web.Response(body=item.get('content'), headers={
                'Pragma': 'public',
                'Cache-Control': 'public, max-age=31536000',
                'Content-Type': item.get('content_type'),
                'X-Via': 'memory' if not item.get('file', None) else 'disk',
            })

        staticDir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'frontend/dist')
        for root, _, files in os.walk(staticDir):
            for file in files:
                if file.endswith('.map'):
                    continue

                file = os.path.join(root, file)
                urlPath = f"{self.config.url_prefix}{file.replace(f'{staticDir}/', '')}"

                self.staticHolder[urlPath] = {
                    # 'file': file,
                    'content': open(file, 'rb').read(),
                    'content_type': self.extToMime.get(os.path.splitext(file)[1], MIME.from_file(file)),
                }

                self.app.router.add_get(urlPath, staticFile)
                LOG.debug(f'Preloading: [{urlPath}].')

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
                raise RuntimeError('Could not find the frontend UI static assets.') from e
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


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main = Main()
