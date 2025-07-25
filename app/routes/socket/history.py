import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import anyio

from app.library.config import Config
from app.library.DownloadQueue import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.ItemDTO import Item
from app.library.router import RouteType, route
from app.library.Utils import is_downloaded
from app.library.YTDLPOpts import YTDLPOpts

LOG: logging.Logger = logging.getLogger(__name__)


@route(RouteType.SOCKET, "pause", "pause_downloads")
async def pause(notify: EventBus, queue: DownloadQueue):
    queue.pause()
    await notify.emit(
        Events.PAUSED,
        data={"paused": True, "at": time.time()},
        title="Downloads Paused",
        message="Non-active downloads have been paused.",
    )


@route(RouteType.SOCKET, "resume", "resume_downloads")
async def resume(notify: EventBus, queue: DownloadQueue):
    queue.resume()
    await notify.emit(
        Events.RESUMED,
        data={"paused": False, "at": time.time()},
        title="Downloads Resumed",
        message="Resumed all downloads.",
    )


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


@route(RouteType.SOCKET, "archive_item", "archive_item")
async def archive_item(config: Config, data: dict):
    if not isinstance(data, dict) or "url" not in data:
        return

    params: YTDLPOpts = YTDLPOpts.get_instance()

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

    manual_archive: str = config.manual_archive
    if not manual_archive:
        return

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
