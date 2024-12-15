import asyncio
import base64
from datetime import datetime
import functools
import json
import os
import random
import time
from .config import Config
from .DownloadQueue import DownloadQueue
from aiohttp import web
from aiohttp.web import Request, Response, RequestHandler
from .Playlist import Playlist
from .M3u8 import M3u8
from .Segments import Segments
from .Subtitle import Subtitle
import socketio
import logging
import sqlite3
import magic
from .common import common
from pathlib import Path
from .encoder import Encoder
from .Emitter import Emitter

LOG = logging.getLogger('app')
MIME = magic.Magic(mime=True)


class HttpAPI(common):
    config: Config = None
    encoder: Encoder = None
    app: web.Application = None
    sio: socketio.AsyncServer = None
    routes: web.RouteTableDef = None
    connection: sqlite3.Connection = None
    queue: DownloadQueue = None
    loop: asyncio.AbstractEventLoop = None
    rootPath: str = None

    staticHolder: dict = {}

    extToMime: dict = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.ico': 'image/x-icon',
    }

    def __init__(self, queue: DownloadQueue, emitter: Emitter, encoder: Encoder):
        super().__init__(queue=queue, encoder=encoder)

        self.rootPath = str(Path(__file__).parent.parent.parent)
        self.config = Config.get_instance()

        self.loop = asyncio.get_event_loop()
        self.encoder = encoder

        self.routes = web.RouteTableDef()

        self.emitter = emitter
        self.queue = queue

    def route(method: str, path: str):
        """
        Decorator to mark a method as an HTTP route handler.
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            wrapper._http_method = method.upper()
            wrapper._http_path = path
            return wrapper
        return decorator

    async def staticFile(self, req: Request) -> Response:
        """
        Preload static files from the ui/dist folder.
        """
        path = req.path
        if req.path not in self.staticHolder:
            return web.json_response({"error": "File not found.", "file": path}, status=404)

        item: dict = self.staticHolder[req.path]

        return web.Response(body=item.get('content'), headers={
            'Pragma': 'public',
            'Cache-Control': 'public, max-age=31536000',
            'Content-Type': item.get('content_type'),
            'X-Via': 'memory' if not item.get('file', None) else 'disk',
        })

    def preloadStatic(self, app: web.Application):
        """
        Preload static files from the ui/dist folder.
        """
        staticDir = os.path.join(self.rootPath, 'ui', 'dist')
        for root, _, files in os.walk(staticDir):
            for file in files:
                if file.endswith('.map'):
                    continue

                file = os.path.join(root, file)
                urlPath = f"{self.config.url_prefix}{file.replace(f'{staticDir}/', '')}"

                content = open(file, 'rb').read()
                contentType = self.extToMime.get(os.path.splitext(file)[1], MIME.from_file(file))

                self.staticHolder[urlPath] = {'content': content, 'content_type': contentType}
                LOG.debug(f'Preloading: [{urlPath}].')
                app.router.add_get(urlPath, self.staticFile)

                if urlPath.endswith('/index.html') and urlPath != '/index.html':
                    parentSlash = urlPath.replace('/index.html', '/')
                    parentNoSlash = urlPath.replace('/index.html', '')
                    self.staticHolder[parentSlash] = {'content': content, 'content_type': contentType}
                    self.staticHolder[parentNoSlash] = {'content': content, 'content_type': contentType}
                    app.router.add_get(parentSlash, self.staticFile)
                    app.router.add_get(parentNoSlash, self.staticFile)

    def attach(self, app: web.Application):
        if self.config.auth_username and self.config.auth_password:
            app.middlewares.append(HttpAPI.basic_auth(self.config.auth_username, self.config.auth_password))

        self.add_routes(app)
        pass

    def add_routes(self, app: web.Application):
        for attr_name in dir(self):
            method = getattr(self, attr_name)
            if hasattr(method, '_http_method') and hasattr(method, '_http_path'):
                http_path = method._http_path
                if http_path.startswith('/') and self.config.url_prefix.endswith('/'):
                    http_path = method._http_path[1:]

                self.routes.route(method._http_method, self.config.url_prefix + http_path)(method)

        async def on_prepare(request: Request, response: Response):
            if 'Origin' in request.headers:
                response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
                response.headers['Access-Control-Allow-Methods'] = 'PUT, POST, DELETE'

        if self.config.url_prefix != '/':
            self.routes.route('GET', '/')(lambda _: web.HTTPFound(self.config.url_prefix))
            self.routes.get(self.config.url_prefix[:-1])(lambda _: web.HTTPFound(self.config.url_prefix))

        # add static files.
        self.routes.static(f'{self.config.url_prefix}download/', self.config.download_path)
        self.preloadStatic(app)

        try:
            app.add_routes(self.routes)
            app.on_response_prepare.append(on_prepare)
        except ValueError as e:
            if 'ui/dist' in str(e):
                raise RuntimeError(f"Could not find the frontend UI static assets. '{e}'.") from e
            raise e

    def basic_auth(username: str, password: str):
        @web.middleware
        async def middleware_handler(request: Request, handler: RequestHandler) -> Response:
            auth_header = request.headers.get('Authorization')

            if auth_header is None:
                return web.Response(status=401, headers={
                    'WWW-Authenticate': 'Basic realm="Authorization Required."',
                }, text='Unauthorized.')

            auth_type, encoded_credentials = auth_header.split(' ', 1)

            if 'basic' != auth_type.lower():
                return web.Response(status=401, text="Unsupported authentication method.")

            decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
            user_name, _, user_password = decoded_credentials.partition(':')

            if user_name != username or user_password != password:
                return web.Response(status=401, text='Unauthorized (Invalid credentials).')

            return await handler(request)

        return middleware_handler

    @route('GET', 'ping')
    async def ping(self, _) -> Response:
        await self.queue.test()
        return web.Response(text='pong')

    @route('POST', 'add')
    async def add(self, request: Request) -> Response:
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

        return web.Response(text=self.encoder.encode(status))

    @route('GET', 'tasks')
    async def tasks(self, _: Request) -> Response:
        tasks_file: str = os.path.join(self.config.config_path, 'tasks.json')

        if not os.path.exists(tasks_file):
            return web.json_response({"error": "No tasks defined."}, status=404)

        try:
            with open(tasks_file, 'r') as f:
                tasks = json.load(f)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

        return web.json_response(tasks)

    @route('POST', 'add_batch')
    async def add_batch(self, request: Request) -> Response:
        status = {}

        post = await request.json()
        if not isinstance(post, list):
            raise web.HTTPBadRequest(text='Invalid request body expecting list with dicts.')

        for item in post:
            if not isinstance(item, dict):
                raise web.HTTPBadRequest(text='Invalid request body expecting list with dicts.')

            if not item.get('url'):
                raise web.HTTPBadRequest(text='url is required.')

            status[item.get('url')] = await self.add(
                url=item.get('url'),
                quality=item.get('quality'),
                format=item.get('format'),
                folder=item.get('folder'),
                ytdlp_cookies=item.get('ytdlp_cookies'),
                ytdlp_config=item.get('ytdlp_config'),
                output_template=item.get('output_template')
            )

        return web.Response(text=self.encoder.encode(status))

    @route('DELETE', 'delete')
    async def delete(self, request: Request) -> Response:
        post = await request.json()
        ids = post.get('ids')
        where = post.get('where')

        if not ids or where not in ['queue', 'done']:
            raise web.HTTPBadRequest()

        status: dict[str, str] = {}

        status = await (self.queue.cancel(ids) if where == 'queue' else self.queue.clear(ids))

        return web.Response(text=self.encoder.encode(status))

    @route('POST', 'item/{id}')
    async def update_item(self, request: Request) -> Response:
        id: str = request.match_info.get('id')
        if not id:
            raise web.HTTPBadRequest(text='id is required.')

        item = self.queue.done.getById(id)
        if not item:
            raise web.HTTPNotFound(text='Item not found.')

        try:
            post = await request.json()
            if not post:
                raise web.HTTPBadRequest(text='no data provided.')
        except Exception as e:
            raise web.HTTPBadRequest(text=str(e))

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

        return web.Response(text=self.encoder.encode(item.info), status=status)

    @route('GET', 'history')
    async def history(self, _: Request) -> Response:
        history = {'done': [], 'queue': []}

        for _, v in self.queue.queue.saved_items():
            history['queue'].append(v)
        for _, v in self.queue.done.saved_items():
            history['done'].append(v)

        return web.Response(text=self.encoder.encode(history))

    @route('GET', 'workers')
    async def workers(self, _) -> Response:
        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=404)

        status = self.queue.pool.get_workers_status()

        data = []

        for worker in status:
            worker_status = status.get(worker)

            data.append({
                'id': worker,
                'data': {"status": 'Waiting for download.'} if worker_status is None else worker_status,
            })

        def safe_serialize(obj):
            def default(o): return f"<<non-serializable: {type(o).__qualname__}>>"
            return json.dumps(obj, default=default)

        return web.Response(text=safe_serialize({
            'open': self.queue.pool.has_open_workers(),
            'count': self.queue.pool.get_available_workers(),
            'workers': data,
        }), headers={
            'Content-Type': 'application/json',
        })

    @route('POST', 'workers')
    async def restart_pool(self, _) -> Response:
        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=404)

        self.queue.pool.start()

        return web.Response()

    @route('PATCH', 'workers/{id}')
    async def restart_worker(self, request: Request) -> Response:
        id: str = request.match_info.get('id')
        if not id:
            raise web.HTTPBadRequest(text='worker id is required.')

        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=404)

        status = await self.queue.pool.restart(id, 'requested by user.')

        return web.json_response({"status": "restarted" if status else "in_error_state"})

    @route('delete', 'workers/{id}')
    async def stop_worker(self, request: Request) -> Response:
        id: str = request.match_info.get('id')
        if not id:
            raise web.HTTPBadRequest(text='worker id is required.')

        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=404)

        status = await self.queue.pool.stop(id, 'requested by user.')

        return web.json_response({"status": "stopped" if status else "in_error_state"})

    @route('GET', 'player/playlist/{file:.*}.m3u8')
    async def playlist(self, request: Request) -> Response:
        file: str = request.match_info.get('file')

        if not file:
            raise web.HTTPBadRequest(text='file is required.')

        try:
            text = await Playlist(url=f"{self.config.url_host}{self.config.url_prefix}").make(
                download_path=self.config.download_path,
                file=file
            )
            if isinstance(text, Response):
                return text
        except Exception as e:
            return web.HTTPNotFound(text=str(e))

        return web.Response(text=text, headers={
            'Content-Type': 'application/x-mpegURL',
            'Cache-Control': 'no-cache',
            'Access-Control-Max-Age': "300",
        })

    @route('GET', 'player/m3u8/{mode}/{file:.*}.m3u8')
    async def m3u8(self, request: Request) -> Response:
        file: str = request.match_info.get('file')
        mode: str = request.match_info.get('mode')

        if mode not in ['video', 'subtitle']:
            raise web.HTTPBadRequest(text='Only video and subtitle modes are supported.')

        if not file:
            raise web.HTTPBadRequest(text='file is required.')

        duration = request.query.get('duration', None)

        if 'subtitle' in mode:
            if not duration:
                raise web.HTTPBadRequest(text='duration is required.')

            duration = float(duration)

        try:
            cls = M3u8(f"{self.config.url_host}{self.config.url_prefix}")
            if 'subtitle' in mode:
                text = await cls.make_subtitle(self.config.download_path, file, duration)
            else:
                text = await cls.make_stream(self.config.download_path, file)
        except Exception as e:
            return web.HTTPNotFound(text=str(e))

        return web.Response(text=text, headers={
            'Content-Type': 'application/x-mpegURL',
            'Cache-Control': 'no-cache',
            'Access-Control-Max-Age': "300",
        })

    @route('GET', 'player/segments/{segment:\d+}/{file:.*}.ts')
    async def segments(self, request: Request) -> Response:
        file: str = request.match_info.get('file')
        segment: int = request.match_info.get('segment')
        sd: int = request.query.get('sd')
        vc: int = int(request.query.get('vc', 0))
        ac: int = int(request.query.get('ac', 0))
        file_path: str = os.path.normpath(os.path.join(self.config.download_path, file))
        if not file_path.startswith(self.config.download_path):
            raise web.HTTPBadRequest(text='Invalid file path.')

        if request.if_modified_since:
            if os.path.exists(file_path) and request.if_modified_since.timestamp() == os.path.getmtime(file_path):
                return web.Response(status=304)

        if not file:
            raise web.HTTPBadRequest(text='file is required')

        if not segment:
            raise web.HTTPBadRequest(text='segment is required')

        segmenter = Segments(
            index=int(segment),
            duration=float('{:.6f}'.format(float(sd if sd else M3u8.duration))),
            vconvert=True if vc == 1 else False,
            aconvert=True if ac == 1 else False
        )

        return web.Response(body=await segmenter.stream(path=self.config.download_path, file=file), headers={
            'Content-Type': 'video/mpegts',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*',
            'Pragma': 'public',
            'Cache-Control': f'public, max-age={time.time() + 31536000}',
            'Last-Modified': time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(os.path.getmtime(file_path)).timetuple()),
            'Expires': time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(time.time() + 31536000).timetuple()),
        })

    @route('GET', 'player/subtitle/{file:.*}.vtt')
    async def subtitles(self, request: Request) -> Response:
        file: str = request.match_info.get('file')
        file_path: str = os.path.normpath(os.path.join(self.config.download_path, file))
        if not file_path.startswith(self.config.download_path):
            raise web.HTTPBadRequest(text='Invalid file path.')

        if request.if_modified_since:
            lastMod = time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(
                os.path.getmtime(file_path)).timetuple())
            if os.path.exists(file_path) and request.if_modified_since.timestamp() == os.path.getmtime(file_path):
                return web.Response(status=304, headers={'Last-Modified': lastMod})

        if not file:
            raise web.HTTPBadRequest(text='file is required')

        return web.Response(body=await Subtitle().make(path=self.config.download_path, file=file), headers={
            'Content-Type': 'text/vtt; charset=UTF-8',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*',
            'Pragma': 'public',
            'Cache-Control': f'public, max-age={time.time() + 31536000}',
            'Last-Modified': time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(os.path.getmtime(file_path)).timetuple()),
            'Expires': time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(time.time() + 31536000).timetuple()),
        })

    @route('OPTIONS', '/add')
    async def add_cors(self, _: Request) -> Response:
        return web.Response(text=self.encoder.encode({"status": "ok"}))

    @route('OPTIONS', '/delete')
    async def delete_cors(self, _: Request) -> Response:
        return web.Response(text=self.encoder.encode({"status": "ok"}))

    @route('GET', '/')
    async def index(self, _) -> Response:
        data = self.staticHolder['/index.html']
        return web.Response(
            body=data.get('content'),
            content_type=data.get('content_type'),
            charset='utf-8',
            status=web.HTTPOk.status_code)
