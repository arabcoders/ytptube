import asyncio
import errno
import functools
import json
import logging
import os
import pty
import shlex
import time
from datetime import datetime

import socketio
from aiohttp import web

from .common import common
from .config import Config
from .DownloadQueue import DownloadQueue
from .Emitter import Emitter
from .encoder import Encoder
from .Utils import isDownloaded, arg_converter

LOG = logging.getLogger("socket_api")


class HttpSocket(common):
    """
    This class is used to handle WebSocket events.
    """

    config: Config
    sio: socketio.AsyncServer

    def __init__(self, queue: DownloadQueue, emitter: Emitter, encoder: Encoder):
        super().__init__(queue=queue, encoder=encoder)

        self.sio = socketio.AsyncServer(cors_allowed_origins="*")
        emitter.add_emitter(lambda event, data, **kwargs: self.sio.emit(event, encoder.encode(data), **kwargs))

        self.config = Config.get_instance()

        self.queue = queue
        self.emitter = emitter

    def ws_event(func):  # type: ignore
        """
        Decorator to mark a method as a socket event.
        """

        @functools.wraps(func)  # type: ignore
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)  # type: ignore

        wrapper._ws_event = func.__name__  # type: ignore
        return wrapper

    def attach(self, app: web.Application):
        self.sio.attach(app, socketio_path=self.config.url_socketio)

        for attr_name in dir(self):
            method = getattr(self, attr_name)
            if hasattr(method, "_ws_event") and self.sio:
                self.sio.on(method._ws_event)(method)  # type: ignore

    @ws_event  # type: ignore
    async def cli_post(self, sid: str, data):
        if not data:
            await self.emitter.emit("cli_close", {"exitcode": 0}, to=sid)
            return

        try:
            LOG.info(f"Cli command from client '{sid}'. '{data}'")

            args = ["yt-dlp"] + shlex.split(data)
            _env = os.environ.copy()
            _env.update(
                {
                    "TERM": "xterm-256color",
                    "LANG": "en_US.UTF-8",
                    "SHELL": "/bin/bash",
                    "LC_ALL": "en_US.UTF-8",
                    "PWD": self.config.download_path,
                    "FORCE_COLOR": "1",
                    "PYTHONUNBUFFERED": "1",
                }
            )

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
                LOG.error(f"Error closing PTY. '{str(e)}'.")

            async def read_pty():
                loop = asyncio.get_running_loop()
                buffer = b""
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
                            await self.emitter.emit(
                                "cli_output", {"type": "stdout", "line": buffer.decode("utf-8", errors="replace")}
                            )
                        break
                    buffer += chunk
                    *lines, buffer = buffer.split(b"\n")
                    for line in lines:
                        await self.emitter.emit(
                            "cli_output", {"type": "stdout", "line": line.decode("utf-8", errors="replace")}
                        )
                try:
                    os.close(master_fd)
                except Exception as e:
                    LOG.error(f"Error closing PTY. '{str(e)}'.")

            # Start reading output from PTY
            read_task = asyncio.create_task(read_pty())

            # Wait until process finishes
            returncode = await proc.wait()

            # Ensure reading is done
            await read_task

            await self.emitter.emit("cli_close", {"exitcode": returncode}, to=sid)
        except Exception as e:
            LOG.error(f"CLI execute exception was thrown for client '{sid}'.")
            LOG.exception(e)
            await self.emitter.emit(
                "cli_out1put",
                {
                    "type": "stderr",
                    "line": str(e),
                },
                to=sid,
            )
            await self.emitter.emit("cli_close", {"exitcode": -1}, to=sid)

    @ws_event  # type: ignore
    async def add_url(self, sid: str, data: dict):
        url: str | None = data.get("url")

        if not url:
            await self.emitter.warning("No URL provided.", to=sid)
            return

        preset: str = str(data.get("preset", self.config.default_preset))
        folder: str = str(data.get("folder")) if data.get("folder") else ""
        ytdlp_cookies: str = str(data.get("ytdlp_cookies")) if data.get("ytdlp_cookies") else ""
        output_template: str = str(data.get("output_template")) if data.get("output_template") else ""

        ytdlp_config = data.get("ytdlp_config")
        if isinstance(ytdlp_config, str) and ytdlp_config:
            try:
                ytdlp_config = json.loads(ytdlp_config)
            except Exception as e:
                await self.emitter.warning(f"Failed to parse json yt-dlp config. {str(e)}", to=sid)
                return

        status = await self.add(
            url=url,
            preset=preset,
            folder=folder,
            ytdlp_cookies=ytdlp_cookies,
            ytdlp_config=ytdlp_config if isinstance(ytdlp_config, dict) else {},
            output_template=output_template,
        )

        await self.emitter.emit("status", status, to=sid)

    @ws_event  # type: ignore
    async def item_cancel(self, sid: str, id: str):
        if not id:
            await self.emitter.warning("Invalid request.", to=sid)
            return

        status: dict[str, str] = {}
        status = await self.queue.cancel([id])
        status.update({"identifier": id})

        await self.emitter.emit("item_cancel", status)

    @ws_event  # type: ignore
    async def item_delete(self, sid: str, data: dict):
        if not data:
            await self.emitter.warning("Invalid request.", to=sid)
            return

        id: str | None = data.get("id")
        if not id:
            await self.emitter.warning("Invalid request.", to=sid)
            return

        status: dict[str, str] = {}
        status = await self.queue.clear([id], remove_file=bool(data.get("remove_file", False)))
        status.update({"identifier": id})

        await self.emitter.emit("item_delete", status)

    @ws_event  # type: ignore
    async def archive_item(self, sid: str, data: dict):
        if not isinstance(data, dict) or "url" not in data or not self.config.keep_archive:
            return

        if not isinstance(self.config.ytdl_options, dict):
            self.config.ytdl_options = {}

        file: str = self.config.ytdl_options.get("download_archive", None)

        if not file:
            return

        exists, idDict = isDownloaded(file, data["url"])
        if exists or "archive_id" not in idDict or idDict["archive_id"] is None:
            return

        with open(file, "a") as f:
            f.write(f"{idDict['archive_id']}\n")

        manual_archive = self.config.manual_archive
        if manual_archive:
            previouslyArchived = False
            if os.path.exists(manual_archive):
                with open(manual_archive, "r") as f:
                    for line in f.readlines():
                        if idDict["archive_id"] in line:
                            previouslyArchived = True
                            break

            if not previouslyArchived:
                with open(manual_archive, "a") as f:
                    f.write(f"{idDict['archive_id']} - at: {datetime.now().isoformat()}\n")

        LOG.info(f"Archiving url '{data['url']}' with id '{idDict['archive_id']}'.")

    @ws_event  # type: ignore
    async def connect(self, sid: str, _=None):
        data = {
            **self.queue.get(),
            "config": self.config.frontend(),
            "tasks": self.config.tasks,
            "presets": self.config.presets,
            "paused": self.queue.isPaused(),
        }

        # get download folder listing
        downloadPath: str = self.config.download_path
        data["folders"] = [name for name in os.listdir(downloadPath) if os.path.isdir(os.path.join(downloadPath, name))]

        await self.emitter.emit("initial_data", data, to=sid)

    @ws_event  # type: ignore
    async def pause(self, sid: str, _=None):
        self.queue.pause()
        await self.emitter.emit("paused", {"paused": True, "at": time.time()})

    @ws_event  # type: ignore
    async def resume(self, sid: str, _=None):
        self.queue.resume()
        await self.emitter.emit("paused", {"paused": False, "at": time.time()})

    @ws_event
    async def ytdlp_convert(self, sid: str, data: dict):
        if not isinstance(data, dict) or "args" not in data:
            await self.emitter.warning("Invalid request or no options were given.", to=sid)
            return

        args: str | None = data.get("args")

        if not args:
            await self.emitter.warning("no options were given.", to=sid)
            return

        try:
            await self.emitter.emit("ytdlp_convert", arg_converter(args), to=sid)
            return
        except Exception as e:
            err = str(e).strip()
            err = err.split("\n")[-1] if "\n" in err else err
            LOG.error(f"Failed to convert args. '{err}'.")
            await self.emitter.error(f"Failed to convert options. '{e}'.", to=sid)
