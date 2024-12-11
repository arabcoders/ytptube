#!/usr/bin/env python3

import argparse
import asyncio
import base64
from datetime import datetime
import json
import os
import random
import shlex
import time
from Config import Config
from DownloadQueue import DownloadQueue
from Utils import ObjectSerializer, Notifier, isDownloaded, load_file
from aiohttp import web, client
from aiohttp.web import Request, Response, RequestHandler
from Webhooks import Webhooks
from player.Playlist import Playlist
from player.M3u8 import M3u8
from player.Segments import Segments
from player.Subtitle import Subtitle
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

        if self.config.auth_username and self.config.auth_password:
            self.app.middlewares.append(
                Main.basic_auth(self.config.auth_username, self.config.auth_password)
            )

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
        start: str = f'YTPTube v{self.config.version} - listening on http://{self.config.host}:{self.config.port}'
        web.run_app(
            self.app,
            host=self.config.host,
            port=self.config.port,
            reuse_port=True,
            loop=self.loop,
            access_log=None,
            print=lambda _: LOG.info(start)
        )

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

    async def connect(self, sid, _):
        data: dict = {
            **self.queue.get(),
            "config": self.config,
            "tasks": [],
        }

        if os.path.exists(os.path.join(self.config.config_path, 'tasks.json')):
            try:
                (tasks, status, error) = load_file(os.path.join(self.config.config_path, 'tasks.json'), list)
                if status is False:
                    LOG.error(f"Could not load tasks file. Error message '{error}'.")
                else:
                    data['tasks'] = tasks

            except Exception as e:
                pass

        # get directory listing
        dlDir: str = self.config.download_path
        data['directories'] = [name for name in os.listdir(dlDir) if os.path.isdir(os.path.join(dlDir, name))]

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

            status: dict[str, str] = {}

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

        @self.routes.get(self.config.url_prefix + 'workers')
        async def workers(_) -> Response:
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

        @self.routes.post(self.config.url_prefix + 'workers')
        async def restart_pool(_) -> Response:
            if self.queue.pool is None:
                return web.json_response({"error": "Worker pool not initialized."}, status=404)

            status = self.queue.pool.start()

            return web.Response()

        @self.routes.patch(self.config.url_prefix + 'workers/{id}')
        async def restart_worker(request: Request) -> Response:
            id: str = request.match_info.get('id')
            if not id:
                raise web.HTTPBadRequest(reason='worker id is required.')

            if self.queue.pool is None:
                return web.json_response({"error": "Worker pool not initialized."}, status=404)

            status = await self.queue.pool.restart(id, 'requested by user.')

            return web.json_response({"status": "restarted" if status else "in_error_state"})

        @self.routes.delete(self.config.url_prefix + 'workers/{id}')
        async def stop_worker(request: Request) -> Response:
            id: str = request.match_info.get('id')
            if not id:
                raise web.HTTPBadRequest(reason='worker id is required.')

            if self.queue.pool is None:
                return web.json_response({"error": "Worker pool not initialized."}, status=404)

            status = await self.queue.pool.stop(id, 'requested by user.')

            return web.json_response({"status": "stopped" if status else "in_error_state"})

        @self.routes.get(self.config.url_prefix + 'player/playlist/{file:.*}.m3u8')
        async def playlist(request: Request) -> Response:
            file: str = request.match_info.get('file')

            if not file:
                raise web.HTTPBadRequest(reason='file is required.')

            try:
                text = await Playlist(url=f"{self.config.url_host}{self.config.url_prefix}").make(
                    download_path=self.config.download_path,
                    file=file
                )
                if isinstance(text, Response):
                    return text
            except Exception as e:
                return web.HTTPNotFound(reason=str(e))

            return web.Response(text=text, headers={
                'Content-Type': 'application/x-mpegURL',
                'Cache-Control': 'no-cache',
                'Access-Control-Max-Age': "300",
            })

        @self.routes.get(self.config.url_prefix + 'player/m3u8/{mode}/{file:.*}.m3u8')
        async def m3u8(request: Request) -> Response:
            file: str = request.match_info.get('file')
            mode: str = request.match_info.get('mode')

            if mode not in ['video', 'subtitle']:
                raise web.HTTPBadRequest(reason='Only video and subtitle modes are supported.')

            if not file:
                raise web.HTTPBadRequest(reason='file is required.')

            duration = request.query.get('duration', None)

            if 'subtitle' in mode:
                if not duration:
                    raise web.HTTPBadRequest(reason='duration is required.')

                duration = float(duration)

            try:
                cls = M3u8(f"{self.config.url_host}{self.config.url_prefix}")
                if 'subtitle' in mode:
                    text = await cls.make_subtitle(self.config.download_path, file, duration)
                else:
                    text = await cls.make_stream(self.config.download_path, file)

            except Exception as e:
                return web.HTTPNotFound(reason=str(e))

            return web.Response(
                text=text,
                headers={
                    'Content-Type': 'application/x-mpegURL',
                    'Cache-Control': 'no-cache',
                    'Access-Control-Max-Age': "300",
                }
            )

        @self.routes.get(self.config.url_prefix + 'player/segments/{segment:\d+}/{file:.*}.ts')
        async def segments(request: Request) -> Response:
            file: str = request.match_info.get('file')
            segment: int = request.match_info.get('segment')
            sd: int = request.query.get('sd')
            vc: int = int(request.query.get('vc', 0))
            ac: int = int(request.query.get('ac', 0))
            file_path: str = os.path.normpath(os.path.join(self.config.download_path, file))
            if not file_path.startswith(self.config.download_path):
                raise web.HTTPBadRequest(reason='Invalid file path.')

            if request.if_modified_since:
                if os.path.exists(file_path) and request.if_modified_since.timestamp() == os.path.getmtime(file_path):
                    return web.Response(status=304)

            if not file:
                raise web.HTTPBadRequest(reason='file is required')

            if not segment:
                raise web.HTTPBadRequest(reason='segment is required')

            segmenter = Segments(
                index=int(segment),
                duration=float('{:.6f}'.format(float(sd if sd else M3u8.duration))),
                vconvert=True if vc == 1 else False,
                aconvert=True if ac == 1 else False
            )

            return web.Response(
                body=await segmenter.stream(path=self.config.download_path, file=file),
                headers={
                    'Content-Type': 'video/mpegts',
                    'X-Accel-Buffering': 'no',
                    'Access-Control-Allow-Origin': '*',
                    'Pragma': 'public',
                    'Cache-Control': f'public, max-age={time.time() + 31536000}',
                    'Last-Modified': time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(os.path.getmtime(file_path)).timetuple()),
                    'Expires': time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(time.time() + 31536000).timetuple()),
                }
            )

        @self.routes.get(self.config.url_prefix + 'player/subtitle/{file:.*}.vtt')
        async def subtitles(request: Request) -> Response:
            file: str = request.match_info.get('file')
            file_path: str = os.path.normpath(os.path.join(self.config.download_path, file))
            if not file_path.startswith(self.config.download_path):
                raise web.HTTPBadRequest(reason='Invalid file path.')

            if request.if_modified_since:
                lastMod = time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(
                    os.path.getmtime(file_path)).timetuple())
                if os.path.exists(file_path) and request.if_modified_since.timestamp() == os.path.getmtime(file_path):
                    return web.Response(status=304, headers={'Last-Modified': lastMod})

            if not file:
                raise web.HTTPBadRequest(reason='file is required')

            return web.Response(
                body=await Subtitle().make(path=self.config.download_path, file=file),
                headers={
                    'Content-Type': 'text/vtt; charset=UTF-8',
                    'X-Accel-Buffering': 'no',
                    'Access-Control-Allow-Origin': '*',
                    'Pragma': 'public',
                    'Cache-Control': f'public, max-age={time.time() + 31536000}',
                    'Last-Modified': time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(os.path.getmtime(file_path)).timetuple()),
                    'Expires': time.strftime('%a, %d %b %Y %H:%M:%S GMT', datetime.fromtimestamp(time.time() + 31536000).timetuple()),
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
        async def cli_post(sid, data):
            if not data:
                await self.sio.emit('cli_close', {'exitcode': 0})
                return

            proc = None
            try:
                async def _read_stream(streamType, stream):
                    while True:
                        line = await stream.readline()
                        if line:
                            await self.sio.emit('cli_output', {
                                'type': streamType,
                                'line': line.decode('utf-8')
                            })
                        else:
                            break

                LOG.info(f'CLI: {data}')

                args = ['yt-dlp', *shlex.split(data)]
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    cwd=self.config.download_path,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=os.environ.copy().update({
                        "TERM": "xterm-256color",
                        "LANG": "en_US.UTF-8",
                        "SHELL": "/bin/bash",
                        "LC_ALL": "en_US.UTF-8",
                        "PWD": self.config.download_path,
                    }),
                )

                await asyncio.gather(
                    _read_stream('stdout', proc.stdout),
                    _read_stream('stderr', proc.stderr),
                )

                while proc.returncode is None:
                    await asyncio.sleep(0.1)

                await self.sio.emit('cli_close', {'exitcode': proc.returncode})
            except Exception as e:
                LOG.error(f'CLI Error: {str(e)}')
                await self.sio.emit('cli_output', {
                    'type': 'stderr',
                    'line': str(e),
                })
                await self.sio.emit('cli_close', {'exitcode': -1})

        @self.sio.event()
        async def archive_item(sid, data):
            if not isinstance(data, dict) or 'url' not in data or not self.config.keep_archive:
                return

            file: str = self.config.ytdl_options.get('download_archive', None)

            if not file:
                return

            exists, idDict = isDownloaded(file, data['url'])
            if exists or 'archive_id' not in idDict or idDict['archive_id'] is None:
                return

            with open(file, 'a') as f:
                f.write(f"{idDict['archive_id']}\n")

            manual_archive = self.config.manual_archive
            if manual_archive:
                previouslyArchived = False
                if os.path.exists(manual_archive):
                    with open(manual_archive, 'r') as f:
                        for line in f.readlines():
                            if idDict['archive_id'] in line:
                                previouslyArchived = True
                                break

                if not previouslyArchived:
                    with open(manual_archive, 'a') as f:
                        f.write(f"{idDict['archive_id']} - at: {datetime.now().isoformat()}\n")

            LOG.info(f'Archiving item: {data["url"]=}')

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
