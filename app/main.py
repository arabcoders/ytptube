#!/usr/bin/env python3

import os
from src.Config import Config
from src.Notifier import Notifier
from src.DownloadQueue import DownloadQueue
from src.Utils import ObjectSerializer
from aiohttp import web
from aiohttp.web import Request, Response
import socketio
import logging
import caribou
import sqlite3

log = logging.getLogger('main')


class Main:
    config: Config = None
    serializer: ObjectSerializer = None
    app: web.Application = None
    sio: socketio.AsyncServer = None
    routes: web.RouteTableDef = None
    connection: sqlite3.Connection = None
    dqueue: DownloadQueue = None

    def __init__(self):
        self.config = Config()

        try:
            if not os.path.exists(self.config.download_path):
                logging.info(
                    f'Creating download folder at {self.config.download_path}')
                os.makedirs(self.config.download_path, exist_ok=True)
        except OSError as e:
            logging.error(
                f'Could not create download folder at {self.config.download_path}')
            raise e
        try:
            if not os.path.exists(self.config.temp_path):
                logging.info(
                    f'Creating temp folder at {self.config.temp_path}')
                os.makedirs(self.config.temp_path, exist_ok=True)
        except OSError as e:
            logging.error(
                f'Could not create temp folder at {self.config.temp_path}')
            raise e

        try:
            if not os.path.exists(self.config.config_path):
                logging.info(
                    f'Creating config folder at {self.config.config_path}')
                os.makedirs(self.config.config_path, exist_ok=True)
        except OSError as e:
            logging.error(
                f'Could not create config folder at {self.config.config_path}')
            raise e

        try:
            if not os.path.exists(self.config.db_file):
                logging.info(
                    f'Creating database file at {self.config.db_file}')
                with open(self.config.db_file, 'w') as _:
                    pass
        except OSError as e:
            logging.error(
                f'Could not create database file at {self.config.db_file}')
            raise e

        caribou.upgrade(self.config.db_file, './app/migrations')

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
        self.app.on_startup.append(lambda app: self.dqueue.initialize())
        self.addRoutes()
        self.start()

    def start(self):
        log.info(f"Listening on {self.config.host}:{self.config.port}")
        web.run_app(
            self.app,
            host=self.config.host,
            port=self.config.port,
            reuse_port=True
        )

    async def connect(self, sid, environ):
        await self.sio.emit('all', self.serializer.encode(self.dqueue.get()), to=sid)
        await self.sio.emit('configuration', self.serializer.encode(self.config), to=sid)

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

            status = await self.dqueue.add(
                url=url,
                quality=quality,
                format=format,
                folder=folder,
                ytdlp_cookies=ytdlp_cookies,
                ytdlp_config=ytdlp_config,
                output_template=output_template
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


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main = Main()
