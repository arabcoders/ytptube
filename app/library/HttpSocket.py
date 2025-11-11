import functools
import logging
from pathlib import Path
from typing import Any

import socketio
from aiohttp import web

from app.library.router import RouteType, get_routes
from app.library.Services import Services
from app.library.Utils import load_modules

from .config import Config
from .DownloadQueue import DownloadQueue
from .encoder import Encoder
from .Events import Event, EventBus, Events
from .ItemDTO import Item

LOG: logging.Logger = logging.getLogger("socket_api")


class HttpSocket:
    """
    This class is used to handle WebSocket events.
    """

    config: Config
    sio: socketio.AsyncServer
    queue: DownloadQueue
    di_context: dict[str, Any] = {}

    def __init__(
        self,
        root_path: Path,
        queue: DownloadQueue | None = None,
        encoder: Encoder | None = None,
        config: Config | None = None,
        sio: socketio.AsyncServer | None = None,
    ):
        self.config = config or Config.get_instance()
        self.queue = queue or DownloadQueue.get_instance()
        self._notify = EventBus.get_instance()

        self.sio = sio or socketio.AsyncServer(
            async_handlers=True,
            async_mode="aiohttp",
            cors_allowed_origins="*",
            transports=["websocket", "polling"],
            logger=self.config.debug,
            engineio_logger=self.config.debug,
            ping_interval=10,
            ping_timeout=5,
        )
        encoder = encoder or Encoder()
        self.rootPath: Path = root_path

        async def event_handler(e: Event, _, **kwargs):
            await self.sio.emit(event=e.event, data=encoder.encode(e), **kwargs)

        services: Services = Services.get_instance()
        services.add_all(
            {
                k: v
                for k, v in {
                    "config": self.config,
                    "queue": self.queue,
                    "sio": self.sio,
                    "encoder": encoder,
                    "notify": self._notify,
                    "root_path": self.rootPath,
                }.items()
                if not services.has(k)
            }
        )

        self._notify.subscribe("frontend", event_handler, f"{__class__.__name__}.emit")

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
        app.on_shutdown.append(self.on_shutdown)

        self.sio.attach(app, socketio_path=f"{self.config.base_path.rstrip('/')}/socket.io")

        async def event_handler(data: Event, _):
            if data and data.data:
                await self.queue.add(item=Item.format(data.data))

        self._notify.subscribe(Events.ADD_URL, event_handler, f"{__class__.__name__}.add")

        load_modules(self.rootPath, self.rootPath / "routes" / "socket")

        for route in get_routes(RouteType.SOCKET).values():
            if self.config.debug:
                LOG.debug(
                    f"Add ({route.name}) {route.method.value if isinstance(route.method, RouteType) else route.method}: {route.path}."
                )
            self.sio.on(route.path)(HttpSocket._injector(route.handler, route.path))

    @staticmethod
    def _injector(func, event: str):
        async def wrapper(sid, data=None, **kwargs):
            if not data:
                data = {}
            return await Services.get_instance().handle_async(func, sid=sid, data=data, event=event, **kwargs)

        return wrapper
