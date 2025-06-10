import asyncio
import errno
import functools
import logging
import os
import shlex
import time
from datetime import UTC, datetime
from pathlib import Path

import anyio
import socketio
from aiohttp import web

from .common import Common
from .config import Config
from .DownloadQueue import DownloadQueue
from .encoder import Encoder
from .Events import Event, EventBus, Events, error
from .ItemDTO import Item
from .Presets import Presets
from .Utils import is_downloaded, tail_log

LOG = logging.getLogger("socket_api")


class HttpSocket(Common):
    """
    This class is used to handle WebSocket events.
    """

    config: Config
    sio: socketio.AsyncServer
    queue: DownloadQueue

    subscribers: dict[str, list[str]] = {}
    """Event subscriber list."""

    log_task = None
    """Task to tail the log file."""

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

        # logger=True, engineio_logger=True,
        self.sio = sio or socketio.AsyncServer(
            async_handlers=True,
            async_mode="aiohttp",
            cors_allowed_origins=[],
            transports=["websocket", "polling"],
            logger=self.config.debug,
            engineio_logger=self.config.debug,
            ping_interval=10,
            ping_timeout=5,
        )
        encoder = encoder or Encoder()

        def emit(e: Event, _, **kwargs):
            return self.sio.emit(event=e.event, data=encoder.encode(e.data), **kwargs)

        self._notify.subscribe("frontend", emit, f"{__class__.__name__}.emit")

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

        for sid in self.sio.manager.get_participants("/", None):
            LOG.debug(f"Disconnecting client '{sid}'.")
            await self.sio.disconnect(sid[0], namespace="/")

        LOG.debug("Socket server shutdown complete.")

    def attach(self, app: web.Application):
        self.sio.attach(app, socketio_path=f"{self.config.base_path.rstrip('/')}/socket.io")

        for attr_name in dir(self):
            method = getattr(self, attr_name)
            if hasattr(method, "_ws_event") and self.sio:
                self.sio.on(method._ws_event)(method)  # type: ignore

        self._notify.subscribe(
            Events.ADD_URL,
            lambda data, _, **kwargs: self.add(item=Item.format(data.data)),  # noqa: ARG005
            f"{__class__.__name__}.add",
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

            try:
                import pty

                master_fd, slave_fd = pty.openpty()
                stdin_arg = asyncio.subprocess.DEVNULL
                stdout_arg = stderr_arg = slave_fd
                use_pty = True
            except ImportError:
                use_pty = False
                master_fd = slave_fd = None
                stdin_arg = asyncio.subprocess.DEVNULL
                stdout_arg = asyncio.subprocess.PIPE
                stderr_arg = asyncio.subprocess.STDOUT

            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=self.config.download_path,
                stdin=stdin_arg,
                stdout=stdout_arg,
                stderr=stderr_arg,
                env=_env,
            )

            if use_pty:
                try:
                    os.close(slave_fd)
                except Exception as e:
                    LOG.error(f"Error closing PTY. '{e!s}'.")

            async def reader(sid: str):
                if use_pty is False:
                    assert proc.stdout is not None
                    async for raw_line in proc.stdout:
                        line = raw_line.rstrip(b"\n")
                        await self._notify.emit(
                            Events.CLI_OUTPUT,
                            data={"type": "stdout", "line": line.decode("utf-8", errors="replace")},
                            to=sid,
                        )
                    return

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
            read_task = asyncio.create_task(reader(sid=sid))

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
            await self._notify.emit(
                event=Events.STATUS,
                data=await self.add(item=Item.format(data)),
                to=sid,
            )
        except ValueError as e:
            LOG.exception(e)
            await self._notify.emit(Events.ERROR, data=error(str(e)), to=sid)
            return

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
        if not isinstance(data, dict) or "url" not in data:
            return

        from .YTDLPOpts import YTDLPOpts

        params = YTDLPOpts.get_instance()

        if "preset" in data and isinstance(data["preset"], str):
            params.preset(name=data["preset"])

        if "cli" in data and isinstance(data["cli"], str) and len(data["cli"]) > 1:
            params.add_cli(data["cli"], from_user=True)

        params = params.get_all()

        file: str = params.get("download_archive", None)

        if not file:
            return

        exists, idDict = is_downloaded(file, data["url"])
        if exists or "archive_id" not in idDict or idDict["archive_id"] is None:
            return

        async with await anyio.open_file(file, "a") as f:
            await f.write(f"{idDict['archive_id']}\n")

        manual_archive = self.config.manual_archive
        if manual_archive:
            manual_archive = Path(manual_archive)

            if not manual_archive.exists():
                manual_archive.touch(exist_ok=True)

            previouslyArchived = False
            async with await anyio.open_file(manual_archive) as f:
                async for line in f:
                    if idDict["archive_id"] in line:
                        previouslyArchived = True
                        break

            if not previouslyArchived:
                async with await anyio.open_file(manual_archive, "a") as f:
                    await f.write(f"{idDict['archive_id']} - at: {datetime.now(UTC).isoformat()}\n")
                    LOG.info(f"Archiving url '{data['url']}' with id '{idDict['archive_id']}'.")
            else:
                LOG.info(f"URL '{data['url']}' with id '{idDict['archive_id']}' already archived.")

    @ws_event
    async def connect(self, sid: str, _=None):
        data = {
            **self.queue.get(),
            "config": self.config.frontend(),
            "presets": Presets.get_instance().get_all(),
            "paused": self.queue.is_paused(),
        }

        data["folders"] = [folder.name for folder in Path(self.config.download_path).iterdir() if folder.is_dir()]

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
    async def subscribe(self, sid: str, event: str):
        """
        Subscribe to a specific event.

        Args:
            sid (str): The session ID of the client.
            event (str): The event to subscribe to.

        """
        if not isinstance(event, str):
            await self._notify.emit(Events.ERROR, data=error("Invalid event."), to=sid)
            return

        if event not in self.subscribers:
            self.subscribers[event] = []

        if sid not in self.subscribers[event]:
            self.subscribers[event].append(sid)
            LOG.debug(f"Client '{sid}' subscribed to event '{event}'.")
            await self.sio.emit(Events.SUBSCRIBED, data={"event": event}, to=sid)

        async def emit_logs(data: dict):
            await self.subscribe_emit(event=event, data=data)

        if "log_lines" == event and self.log_task is None:
            log_file = Path(self.config.config_path) / "logs" / "app.log"
            LOG.debug(f"Starting tailing '{log_file!s}'.")
            self.log_task = asyncio.create_task(
                tail_log(
                    file=log_file,
                    emitter=emit_logs,
                ),
                name="tail_log",
            )

    @ws_event
    async def unsubscribe(self, sid: str, event: str):
        """
        Unsubscribe from a specific event.

        Args:
            sid (str): The session ID of the client.
            event (str): The event to unsubscribe from.

        """
        if event not in self.subscribers:
            return

        if sid not in self.subscribers[event]:
            return

        self.subscribers[event].remove(sid)
        await self.sio.emit(Events.UNSUBSCRIBED, data={"event": event}, to=sid)

        LOG.debug(f"Client '{sid}' unsubscribed from event '{event}'.")

        if "log_lines" != event or not self.log_task or "log_lines" not in self.subscribers:
            return

        if len(self.subscribers["log_lines"]) < 1:
            try:
                LOG.debug("Stopping log tailing task.")
                self.log_task.cancel()
                self.log_task = None
            except asyncio.CancelledError:
                pass

    @ws_event
    async def disconnect(self, sid: str, reason: str):
        """
        Handle client disconnection.

        Args:
            sid (str): The session ID of the client.
            reason (str): The reason for disconnection.

        """
        LOG.debug(f"Client '{sid}' disconnected. {reason}")

        for event in self.subscribers:
            if sid in self.subscribers[event]:
                await self.unsubscribe(sid=sid, event=event)

    async def subscribe_emit(self, event: str, data: dict):
        if event not in self.subscribers or len(self.subscribers[event]) < 1:
            return

        for sid in self.subscribers[event]:
            await self.sio.emit(event=event, data=data, to=sid)
