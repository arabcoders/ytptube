import asyncio
import errno
import functools
import logging
import os
import pty
import shlex
import time
from datetime import UTC, datetime

import anyio
import socketio
from aiohttp import web

from .common import Common
from .config import Config
from .DownloadQueue import DownloadQueue
from .encoder import Encoder
from .Events import Event, EventBus, Events, error
from .Presets import Presets
from .Utils import arg_converter, is_downloaded

LOG = logging.getLogger("socket_api")


class HttpSocket(Common):
    """
    This class is used to handle WebSocket events.
    """

    config: Config
    sio: socketio.AsyncServer
    queue: DownloadQueue

    def __init__(
        self,
        queue: DownloadQueue | None = None,
        encoder: Encoder | None = None,
        config: Config | None = None,
        sio: socketio.AsyncServer | None = None,
    ):
        self.config = config or Config.get_instance()
        self.queue = queue or DownloadQueue.get_instance()
        self._notify = EventBus.get_instance()

        self.sio = sio or socketio.AsyncServer(cors_allowed_origins="*")
        encoder = encoder or Encoder()

        def emit(e: Event, _, **kwargs):
            return self.sio.emit(event=e.event, data=encoder.encode(e.data), **kwargs)

        self._notify.subscribe("frontend", emit, f"{__class__.__name__}.socket_api")

        super().__init__(queue=queue, encoder=encoder, config=config)

    @staticmethod
    def ws_event(func):  # type: ignore
        """
        Decorator to mark a method as a socket event.
        """

        @functools.wraps(func)  # type: ignore
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)  # type: ignore

        wrapper._ws_event = func.__name__  # type: ignore
        return wrapper

    async def on_shutdown(self, _: web.Application):
        LOG.debug("Shutting down socket server.")

    def attach(self, app: web.Application):
        self.sio.attach(app, socketio_path=self.config.url_socketio)

        for attr_name in dir(self):
            method = getattr(self, attr_name)
            if hasattr(method, "_ws_event") and self.sio:
                self.sio.on(method._ws_event)(method)  # type: ignore

        self._notify.subscribe(
            Events.ADD_URL,
            lambda data, _, **kwargs: self.add(**data.data),  # noqa: ARG005
            f"{__class__.__name__}.socket_add_url",
        )

        # register the shutdown event.
        app.on_shutdown.append(self.on_shutdown)

    @ws_event
    async def cli_post(self, sid: str, data):
        if not self.config.console_enabled:
            await self._notify.emit(Events.ERROR, data=error("Console is disabled."), to=sid)
            return

        if not data:
            await self._notify.emit(Events.CLI_CLOSE, data={"exitcode": 0}, to=sid)
            return

        try:
            LOG.info(f"Cli command from client '{sid}'. '{data}'")

            args = ["yt-dlp", *shlex.split(data)]
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
                LOG.error(f"Error closing PTY. '{e!s}'.")

            async def read_pty(sid: str):
                loop = asyncio.get_running_loop()
                buffer = b""
                while True:
                    try:
                        chunk = await loop.run_in_executor(None, lambda: os.read(master_fd, 1024))
                    except OSError as e:
                        if e.errno == errno.EIO:
                            break
                        raise

                    if not chunk:
                        # No more output
                        if buffer:
                            # Emit any remaining partial line
                            await self._notify.emit(
                                Events.CLI_OUTPUT,
                                data={"type": "stdout", "line": buffer.decode("utf-8", errors="replace")},
                                to=sid,
                            )
                        break
                    buffer += chunk
                    *lines, buffer = buffer.split(b"\n")
                    for line in lines:
                        await self._notify.emit(
                            Events.CLI_OUTPUT,
                            data={"type": "stdout", "line": line.decode("utf-8", errors="replace")},
                            to=sid,
                        )
                try:
                    os.close(master_fd)
                except Exception as e:
                    LOG.error(f"Error closing PTY. '{e!s}'.")

            # Start reading output from PTY
            read_task = asyncio.create_task(read_pty(sid=sid))

            # Wait until process finishes
            returncode = await proc.wait()

            # Ensure reading is done
            await read_task

            await self._notify.emit(Events.CLI_CLOSE, data={"exitcode": returncode}, to=sid)
        except Exception as e:
            LOG.error(f"CLI execute exception was thrown for client '{sid}'.")
            LOG.exception(e)
            await self._notify.emit(Events.CLI_OUTPUT, data={"type": "stderr", "line": str(e)}, to=sid)
            await self._notify.emit(Events.CLI_CLOSE, data={"exitcode": -1}, to=sid)

    @ws_event
    async def add_url(self, sid: str, data: dict):
        url: str | None = data.get("url")

        if not url:
            await self._notify.emit(Events.ERROR, data=error("No URL provided.", data={"unlock": True}), to=sid)
            return

        try:
            item = self.format_item(data)
        except ValueError as e:
            await self._notify.emit(Events.ERROR, data=error(str(e)), to=sid)
            return

        status = await self.add(**item)
        await self._notify.emit(Events.STATUS, data=status, to=sid)

    @ws_event
    async def item_cancel(self, sid: str, id: str):
        if not id:
            await self._notify.emit(Events.ERROR, data=error("Invalid request."), to=sid)
            return

        status: dict[str, str] = {}
        status = await self.queue.cancel([id])
        status.update({"identifier": id})

        await self._notify.emit(Events.ITEM_CANCEL, data=status)

    @ws_event
    async def item_delete(self, sid: str, data: dict):
        if not data:
            await self._notify.emit(Events.ERROR, data=error("Invalid request."), to=sid)
            return

        id: str | None = data.get("id")
        if not id:
            await self._notify.emit(Events.ERROR, data=error("Invalid request."), to=sid)
            return

        status: dict[str, str] = {}
        status = await self.queue.clear([id], remove_file=bool(data.get("remove_file", False)))
        status.update({"identifier": id})

        await self._notify.emit(Events.ITEM_DELETE, data=status)

    @ws_event
    async def archive_item(self, _: str, data: dict):
        if not isinstance(data, dict) or "url" not in data or not self.config.keep_archive:
            return

        if not isinstance(self.config.ytdl_options, dict):
            self.config.ytdl_options = {}

        file: str = self.config.ytdl_options.get("download_archive", None)

        if not file:
            return

        exists, idDict = is_downloaded(file, data["url"])
        if exists or "archive_id" not in idDict or idDict["archive_id"] is None:
            return

        async with await anyio.open_file(file, "a") as f:
            await f.write(f"{idDict['archive_id']}\n")

        manual_archive = self.config.manual_archive
        if manual_archive:
            previouslyArchived = False
            if os.path.exists(manual_archive):
                async with await anyio.open_file(manual_archive) as f:
                    async for line in f:
                        if idDict["archive_id"] in line:
                            previouslyArchived = True
                            break

            if not previouslyArchived:
                async with await anyio.open_file(manual_archive, "a") as f:
                    await f.write(f"{idDict['archive_id']} - at: {datetime.now(UTC).isoformat()}\n")

        LOG.info(f"Archiving url '{data['url']}' with id '{idDict['archive_id']}'.")

    @ws_event
    async def connect(self, sid: str, _=None):
        data = {
            **self.queue.get(),
            "config": self.config.frontend(),
            "presets": Presets.get_instance().get_all(),
            "paused": self.queue.is_paused(),
        }

        # get download folder listing.
        downloadPath: str = self.config.download_path
        data["folders"] = [name for name in os.listdir(downloadPath) if os.path.isdir(os.path.join(downloadPath, name))]

        await self._notify.emit(Events.INITIAL_DATA, data=data, to=sid)

    @ws_event
    async def pause(self, *_, **__):
        self.queue.pause()
        await self._notify.emit(Events.PAUSED, data={"paused": True, "at": time.time()})

    @ws_event
    async def resume(self, *_, **__):
        self.queue.resume()
        await self._notify.emit(Events.PAUSED, data={"paused": False, "at": time.time()})

    @ws_event
    async def ytdlp_convert(self, sid: str, data: dict):
        if not isinstance(data, dict) or "args" not in data:
            await self._notify.emit(Events.ERROR, data=error("Invalid request or no options were given."), to=sid)
            return

        args: str | None = data.get("args")

        if not args:
            await self._notify.emit(Events.ERROR, data=error("no options were given."), to=sid)
            return

        try:
            await self._notify.emit(Events.YTDLP_CONVERT, data=arg_converter(args), to=sid)
        except Exception as e:
            err = str(e).strip()
            err = err.split("\n")[-1] if "\n" in err else err
            LOG.error(f"Failed to convert args. '{err}'.")
            await self._notify.emit(Events.ERROR, data=error(f"Failed to convert options. '{err}'."), to=sid)

        return
