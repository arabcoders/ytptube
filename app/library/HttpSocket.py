import asyncio
from datetime import datetime
import errno
import functools
import os
import pty
import shlex
from aiohttp import web
import socketio
import logging
import sqlite3
from .config import Config
from .DownloadQueue import DownloadQueue
from .common import common
from .encoder import Encoder
from .Utils import isDownloaded, load_file
from .Emitter import Emitter

LOG = logging.getLogger('socket')


class HttpSocket(common):
    """
    This class is used to handle WebSocket events.
    """
    config: Config = None
    app: web.Application = None
    sio: socketio.AsyncServer = None
    connection: sqlite3.Connection = None

    def __init__(self, queue: DownloadQueue, emitter: Emitter, encoder: Encoder):
        super().__init__(queue=queue, encoder=encoder)

        self.sio = socketio.AsyncServer(cors_allowed_origins='*')
        emitter.add_emitter(lambda event, data, **kwargs: self.sio.emit(event, encoder.encode(data), **kwargs))

        self.config = Config.get_instance()

        self.queue = queue
        self.emitter = emitter

    def ws_event(func):
        """
        Decorator to mark a method as a socket event.
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        wrapper._ws_event = func.__name__
        return wrapper

    def attach(self, app: web.Application):
        self.sio.attach(app, socketio_path=self.config.url_prefix + 'socket.io')

        for attr_name in dir(self):
            method = getattr(self, attr_name)
            if hasattr(method, '_ws_event'):
                event = method._ws_event
                self.sio.on(event)(method)

    @ws_event
    async def cli_post(self, sid: str, data):
        if not data:
            await self.emitter.emit('cli_close', {'exitcode': 0}, to=sid)
            return

        try:
            LOG.info(f'Cli command from {sid=}: {data}')

            args = ['yt-dlp'] + shlex.split(data)
            _env = os.environ.copy()
            _env.update({
                "TERM": "xterm-256color",
                "LANG": "en_US.UTF-8",
                "SHELL": "/bin/bash",
                "LC_ALL": "en_US.UTF-8",
                "PWD": self.config.download_path,
                "FORCE_COLOR": "1",
                "PYTHONUNBUFFERED": "1",
            })

            master_fd, slave_fd = pty.openpty()

            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=self.config.download_path,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=slave_fd,
                stderr=slave_fd,
                env=_env,
            )

            try:
                os.close(slave_fd)
            except Exception as e:
                LOG.error(f'Error closing PTY: {str(e)}')

            async def read_pty():
                loop = asyncio.get_running_loop()
                buffer = b''
                while True:
                    try:
                        chunk = await loop.run_in_executor(None, lambda: os.read(master_fd, 1024))
                    except OSError as e:
                        if e.errno == errno.EIO:
                            break
                        else:
                            raise

                    if not chunk:
                        # No more output
                        if buffer:
                            # Emit any remaining partial line
                            await self.emitter.emit('cli_output', {
                                'type': 'stdout',
                                'line': buffer.decode('utf-8', errors='replace')
                            })
                        break
                    buffer += chunk
                    *lines, buffer = buffer.split(b'\n')
                    for line in lines:
                        await self.emitter.emit('cli_output', {
                            'type': 'stdout',
                            'line': line.decode('utf-8', errors='replace')
                        })
                try:
                    os.close(master_fd)
                except Exception as e:
                    LOG.error(f'Error closing PTY: {str(e)}')

            # Start reading output from PTY
            read_task = asyncio.create_task(read_pty())

            # Wait until process finishes
            returncode = await proc.wait()

            # Ensure reading is done
            await read_task

            await self.emitter.emit('cli_close', {'exitcode': returncode}, to=sid)
        except Exception as e:
            LOG.error(f'CLI Error for {sid=}: {str(e)}')
            await self.emitter.emit('cli_out1put', {
                'type': 'stderr',
                'line': str(e),
            }, to=sid)
            await self.emitter.emit('cli_close', {'exitcode': -1}, to=sid)

    @ws_event
    async def add_url(self, sid: str, data: dict):
        url: str = data.get('url')
        quality: str = data.get('quality')

        if not url:
            self.emitter.warning('No URL provided.')
            return

        format: str = data.get('format')
        folder: str = data.get('folder')
        ytdlp_cookies: str = data.get('ytdlp_cookies')
        ytdlp_config: dict = data.get('ytdlp_config')
        output_template: str = data.get('output_template')
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

        await self.emitter.emit('status', status, to=sid)

    @ws_event
    async def item_cancel(self, sid: str, id: str):
        if not id:
            await self.emitter.warning('Invalid request.')
            return

        status: dict[str, str] = {}
        status = await self.queue.cancel([id])
        status.update({'identifier': id})

        await self.emitter.emit('item_cancel', status)

    @ws_event
    async def item_delete(self, sid: str, id: str):
        if not id:
            await self.emitter.warning('Invalid request.')
            return

        status: dict[str, str] = {}
        status = await self.queue.clear([id])
        status.update({'identifier': id})

        await self.emitter.emit('item_delete', status)

    @ws_event
    async def archive_item(self, sid: str, data: dict):
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

    @ws_event
    async def connect(self, sid: str, _=None):
        data: dict = {
            **self.queue.get(),
            "config": self.config.frontend(),
            "tasks": [],
            "presets": [],
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

        await self.emitter.emit('initial_data', data, to=sid)
