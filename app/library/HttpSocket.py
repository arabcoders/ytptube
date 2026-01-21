import functools
import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import web

from app.features.core.utils import gen_random
from app.library.router import Route, RouteType, get_routes
from app.library.Services import Services
from app.library.Utils import load_modules

from .config import Config
from .encoder import Encoder
from .Events import Event, EventBus, Events
from .ItemDTO import Item

LOG: logging.Logger = logging.getLogger("socket_api")


class WebSocketHub:
    def __init__(self, encoder: Encoder):
        self._encoder: Encoder = encoder
        self._clients: dict[str, web.WebSocketResponse] = {}

    def add(self, sid: str, ws: web.WebSocketResponse) -> None:
        self._clients[sid] = ws

    def remove(self, sid: str) -> None:
        self._clients.pop(sid, None)

    async def emit(self, event: str, data: Any, to: str | None = None) -> None:
        payload: str = self._encoder.encode({"event": event, "data": data})

        if to:
            await self._send(to, payload)
            return

        for sid in list(self._clients.keys()):
            await self._send(sid, payload)

    async def disconnect(self, sid: str) -> None:
        ws: web.WebSocketResponse | None = self._clients.pop(sid, None)
        if ws and not ws.closed:
            await ws.close()

    async def disconnect_all(self) -> None:
        for sid in list(self._clients.keys()):
            await self.disconnect(sid)

    async def _send(self, sid: str, payload: str) -> None:
        ws: web.WebSocketResponse | None = self._clients.get(sid)
        if not ws or ws.closed:
            self._clients.pop(sid, None)
            return

        try:
            await ws.send_str(payload)
        except ConnectionResetError:
            self._clients.pop(sid, None)


class HttpSocket:
    """
    This class is used to handle WebSocket events.
    """

    config: Config
    sio: WebSocketHub
    di_context: dict[str, Any] = {}

    def __init__(
        self,
        root_path: Path,
        encoder: Encoder | None = None,
        config: Config | None = None,
        sio: WebSocketHub | None = None,
    ):
        self.config = config or Config.get_instance()
        self._notify = EventBus.get_instance()

        encoder = encoder or Encoder()
        self.sio = sio or WebSocketHub(encoder=encoder)
        self.rootPath: Path = root_path

        async def event_handler(e: Event, _, **kwargs):
            payload = json.loads(encoder.encode(e))
            await self.sio.emit(event=e.event, data=payload, **kwargs)

        services: Services = Services.get_instance()
        services.add_all(
            {
                k: v
                for k, v in {
                    "config": self.config,
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
        await self.sio.disconnect_all()
        LOG.debug("Socket server shutdown complete.")

    def attach(self, app: web.Application):
        app.on_shutdown.append(self.on_shutdown)

        base_path: str = self.config.base_path.rstrip("/")
        ws_path: str = f"{base_path}/ws" if base_path else "/ws"

        async def event_handler(data: Event, _):
            if not (data and data.data):
                return

            await Services.get_instance().get("queue").add(item=Item.format(data.data))

        self._notify.subscribe(Events.ADD_URL, event_handler, f"{__class__.__name__}.add")

        load_modules(self.rootPath, self.rootPath / "routes" / "socket")

        socket_routes: dict[str, Route] = {route.path: route for route in get_routes(RouteType.SOCKET).values()}

        for route in socket_routes.values():
            if self.config.debug:
                LOG.debug(
                    f"Add ({route.name}) {route.method.value if isinstance(route.method, RouteType) else route.method}: {route.path}."
                )

        async def handle_message(sid: str, message: str) -> None:
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                LOG.debug("Invalid websocket payload received.")
                return

            event = payload.get("event") if isinstance(payload, dict) else None
            if not event or not isinstance(event, str):
                LOG.debug("Missing websocket event name.")
                return

            if not (route := socket_routes.get(event)):
                LOG.debug(f"Unknown websocket event '{event}'.")
                return

            data = payload.get("data") if isinstance(payload, dict) else None
            await Services.get_instance().handle_async(route.handler, sid=sid, data=data, event=event)

        async def handle_connect(sid: str) -> None:
            if not (route := socket_routes.get("connect")):
                return
            await Services.get_instance().handle_async(route.handler, sid=sid, event="connect")

        async def handle_disconnect(sid: str, reason: str | None) -> None:
            if not (route := socket_routes.get("disconnect")):
                return
            await Services.get_instance().handle_async(route.handler, sid=sid, data=reason, event="disconnect")

        async def ws_handler(request: web.Request) -> web.WebSocketResponse:
            ws = web.WebSocketResponse(heartbeat=10)
            await ws.prepare(request)

            sid: str = gen_random(14)
            self.sio.add(sid, ws)
            LOG.debug(f"WebSocket client '{sid}' connected.")

            await handle_connect(sid)

            try:
                async for msg in ws:
                    if msg.type == web.WSMsgType.TEXT:
                        await handle_message(sid, msg.data)
                    elif msg.type == web.WSMsgType.ERROR:
                        LOG.error(f"WebSocket connection closed with exception {ws.exception()}")
            finally:
                await handle_disconnect(sid, getattr(ws, "close_reason", None))
                self.sio.remove(sid)
                LOG.debug(f"WebSocket client '{sid}' disconnected.")

            return ws

        if self.config.debug:
            LOG.debug(f"Add (ws) GET: {ws_path}.")

        app.router.add_get(ws_path, ws_handler, name="ws")
