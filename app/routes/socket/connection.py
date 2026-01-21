import logging
from pathlib import Path

from app.features.dl_fields.service import DLFields
from app.library.config import Config
from app.library.downloads import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.HttpSocket import WebSocketHub
from app.library.Presets import Presets
from app.library.router import RouteType, route
from app.library.Utils import list_folders

LOG: logging.Logger = logging.getLogger(__name__)


class _Data:
    subscribers: dict[str, list[str]] = {}


@route(RouteType.SOCKET, "connect", "socket_connect")
async def connect(config: Config, queue: DownloadQueue, notify: EventBus, sid: str):
    notify.emit(
        Events.CONFIGURATION,
        data={
            "config": config.frontend(),
            "presets": Presets.get_instance().get_all(),
            "dl_fields": await DLFields.get_instance().get_all_serialized(),
            "paused": queue.is_paused(),
        },
        title="Client connected",
        message=f"Client '{sid}' connected.",
        to=sid,
    )

    notify.emit(
        Events.CONNECTED,
        data={
            "folders": list_folders(
                path=Path(config.download_path),
                base=Path(config.download_path),
                depth_limit=config.download_path_depth - 1,
            ),
            "history_count": await queue.done.get_total_count(),
            "queue": (await queue.get("queue"))["queue"],
        },
        title="Sending initial download data",
        message=f"Sending initial download data to client '{sid}'.",
        to=sid,
    )

    notify.emit(
        Events.ACTIVE_QUEUE,
        data={"queue": (await queue.get("queue"))["queue"]},
        title="Sending initial active queue data",
        message=f"Sending active queue data to client '{sid}'.",
        to=sid,
    )


@route(RouteType.SOCKET, "disconnect", "socket_disconnect")
async def disconnect(sio: WebSocketHub, sid: str, data: str | None = None):  # noqa: ARG001
    """
    Handle client disconnection.

    Args:
        sio (WebSocketHub): The WebSocket hub instance.
        sid (str): The session ID of the client.
        data (str): The reason for disconnection.

    """
    LOG.debug(f"Client '{sid}' disconnected. {data}")
