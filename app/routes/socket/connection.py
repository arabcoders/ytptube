import asyncio
import logging
from pathlib import Path

import socketio

from app.library.config import Config
from app.library.DownloadQueue import DownloadQueue
from app.library.Events import EventBus, Events, error
from app.library.Presets import Presets
from app.library.router import RouteType, route
from app.library.Utils import tail_log

LOG: logging.Logger = logging.getLogger(__name__)


class _Data:
    subscribers: dict[str, list[str]] = {}
    log_task: asyncio.Task | None = None


@route(RouteType.SOCKET, "connect", "socket_connect")
async def connect(config: Config, queue: DownloadQueue, notify: EventBus, sid: str):
    data = {
        **queue.get(),
        "config": config.frontend(),
        "presets": Presets.get_instance().get_all(),
        "paused": queue.is_paused(),
    }

    data["folders"] = [folder.name for folder in Path(config.download_path).iterdir() if folder.is_dir()]

    await notify.emit(Events.INITIAL_DATA, data=data, to=sid)


@route(RouteType.SOCKET, "disconnect", "socket_disconnect")
async def disconnect(sid: str, data: str = None):
    """
    Handle client disconnection.

    Args:
        sid (str): The session ID of the client.
        data (str): The reason for disconnection.

    """
    LOG.debug(f"Client '{sid}' disconnected. {data}")

    for event in _Data.subscribers:
        if sid in _Data.subscribers[event]:
            await unsubscribe(sid=sid, data=event)


@route(RouteType.SOCKET, "subscribe", "socket_subscribe")
async def subscribe(config: Config, notify: EventBus, sio: socketio.AsyncServer, sid: str, data: str):
    """
    Subscribe to a specific event.

    Args:
        config (Config): The configuration instance.
        notify (EventBus): The event bus to use for notifications.
        sio (socketio.AsyncServer): The Socket.IO server instance.
        sid (str): The session ID of the client.
        data (str): The event to subscribe to.

    """
    if not isinstance(data, str):
        await notify.emit(Events.ERROR, data=error("Invalid event."), to=sid)
        return

    if data not in _Data.subscribers:
        _Data.subscribers[data] = []

    if sid not in _Data.subscribers[data]:
        _Data.subscribers[data].append(sid)
        LOG.debug(f"Client '{sid}' subscribed to event '{data}'.")
        await sio.emit(Events.SUBSCRIBED, data={"event": data}, to=sid)

    async def emit_logs(data: dict):
        await subscribe_emit(sio=sio, event=data, data=data)

    if "log_lines" == data and _Data.log_task is None:
        log_file = Path(config.config_path) / "logs" / "app.log"
        LOG.debug(f"Starting tailing '{log_file!s}'.")
        _Data.log_task = asyncio.create_task(tail_log(file=log_file, emitter=emit_logs), name="tail_log")


@route(RouteType.SOCKET, "unsubscribe", "socket_unsubscribe")
async def unsubscribe(sio: socketio.AsyncServer, sid: str, data: str):
    """
    Unsubscribe from a specific event.

    Args:
        sio (socketio.AsyncServer): The Socket.IO server instance.
        sid (str): The session ID of the client.
        data (str): The event to unsubscribe from.

    """
    if data not in _Data.subscribers:
        return

    if sid not in _Data.subscribers[data]:
        return

    _Data.subscribers[data].remove(sid)
    await sio.emit(Events.UNSUBSCRIBED, data={"event": data}, to=sid)

    LOG.debug(f"Client '{sid}' unsubscribed from event '{data}'.")

    if "log_lines" != data or not _Data.log_task or "log_lines" not in _Data.subscribers:
        return

    if len(_Data.subscribers["log_lines"]) < 1:
        try:
            LOG.debug("Stopping log tailing task.")
            _Data.log_task.cancel()
            _Data.log_task = None
        except asyncio.CancelledError:
            pass


async def subscribe_emit(sio: socketio.AsyncServer, event: str, data: dict):
    if event not in _Data.subscribers or len(_Data.subscribers[event]) < 1:
        return

    for sid in _Data.subscribers[event]:
        await sio.emit(event=event, data=data, to=sid)
