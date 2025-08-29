import logging

from app.library.DownloadQueue import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.ItemDTO import Item
from app.library.router import RouteType, route

LOG: logging.Logger = logging.getLogger(__name__)


@route(RouteType.SOCKET, "add_url", "add_url")
async def add_url(queue: DownloadQueue, notify: EventBus, sid: str, data: dict):
    data = data if isinstance(data, dict) else {}
    if not (url := data.get("url", None)):
        await notify.emit(Events.LOG_ERROR, title="Invalid request", message="No URL provided.", to=sid)
        return

    try:
        status = await queue.add(item=Item.format(data))
        await notify.emit(
            event=Events.ITEM_STATUS,
            title="Adding URL",
            message=f"Adding URL '{url}' to the download queue.",
            data=status,
            to=sid,
        )
    except ValueError as e:
        LOG.exception(e)
        await notify.emit(Events.LOG_ERROR, title="Error Adding URL", message=str(e), to=sid)


@route(RouteType.SOCKET, "item_cancel", "item_cancel")
async def item_cancel(queue: DownloadQueue, notify: EventBus, sid: str, data: str):
    if not (data := data if isinstance(data, str) else None):
        await notify.emit(Events.LOG_ERROR, title="Invalid Request", message="No item ID provided.", to=sid)
        return

    await queue.cancel([data])


@route(RouteType.SOCKET, "item_delete", "item_delete")
async def item_delete(queue: DownloadQueue, notify: EventBus, sid: str, data: dict):
    data = data if isinstance(data, dict) else {}

    if not (id := data.get("id", None)):
        await notify.emit(Events.LOG_ERROR, title="Invalid Request", message="No item ID provided.", to=sid)
        return

    await queue.clear([id], remove_file=bool(data.get("remove_file", False)))


@route(RouteType.SOCKET, "item_start", "item_start")
async def item_start(queue: DownloadQueue, notify: EventBus, sid: str, data: list | str) -> None:
    if not data:
        await notify.emit(
            Events.LOG_ERROR,
            title="Invalid Request",
            message="No items provided to start.",
            to=sid,
        )
        return

    if isinstance(data, str):
        data = [data]

    await queue.start_items(data)


@route(RouteType.SOCKET, "item_pause", "item_pause")
async def item_pause(queue: DownloadQueue, notify: EventBus, sid: str, data: list | str) -> None:
    if not data:
        await notify.emit(
            Events.LOG_ERROR,
            title="Invalid Request",
            message="No items provided to pause.",
            to=sid,
        )
        return

    if isinstance(data, str):
        data = [data]

    await queue.pause_items(data)
