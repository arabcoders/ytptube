import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.Download import Download
from app.library.DownloadQueue import DownloadQueue
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.ItemDTO import Item
from app.library.Presets import Preset, Presets
from app.library.router import route
from app.library.Utils import archive_add, archive_delete, archive_read, get_archive_id

if TYPE_CHECKING:
    from library.Download import Download

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", r"api/history/", "items_list")
async def items_list(queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Get the history.

    Args:
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    data: dict = {"queue": [], "history": []}
    q = queue.get()

    data["queue"].extend([q.get("queue", {}).get(k) for k in q.get("queue", {})])
    data["history"].extend([q.get("done", {}).get(k) for k in q.get("done", {})])

    return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("DELETE", "api/history/", "item_delete")
async def item_delete(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Delete an item from the queue.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    data = await request.json()
    ids = data.get("ids")
    where = data.get("where")
    if not ids or where not in ["queue", "done"]:
        return web.json_response(data={"error": "ids and where are required."}, status=web.HTTPBadRequest.status_code)

    remove_file: bool = bool(data.get("remove_file", True))

    return web.json_response(
        data=await (queue.cancel(ids) if where == "queue" else queue.clear(ids, remove_file=remove_file)),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/history/{id}", "item_view")
async def item_view(request: Request, queue: DownloadQueue, encoder: Encoder, config: Config) -> Response:
    """
    Update an item in the history.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.
        config (Config): The configuration instance.

    Returns:
        Response: The response object.

    """
    id: str = request.match_info.get("id")
    if not id:
        return web.json_response(data={"error": "id is required."}, status=web.HTTPBadRequest.status_code)

    item: Download | None = queue.done.get_by_id(id) or queue.queue.get_by_id(id)
    if not item:
        return web.json_response(data={"error": "item not found."}, status=web.HTTPNotFound.status_code)

    if not item.info:
        return web.json_response(data={"error": "item has no info."}, status=web.HTTPNotFound.status_code)

    is_archived = False
    params: dict = item.get_ytdlp_opts().get_all()
    if (archive_file := params.get("download_archive")) and (archive_id := item.get_archive_id()):
        is_archived: bool = len(archive_read(archive_file, [archive_id])) > 0

    info = {
        **item.info.serialize(),
        "is_archived": is_archived,
        "ffprobe": {},
    }

    if item.info.filename:
        try:
            from app.library.ffprobe import ffprobe
            from app.library.Utils import get_file

            filename = Path(config.download_path)
            if item.info.folder:
                filename: Path = filename / item.info.folder

            filename: Path = filename / item.info.filename

            if filename.exists():
                realFile, status = get_file(
                    download_path=config.download_path, file=str(filename.relative_to(config.download_path))
                )
                if status in (web.HTTPOk.status_code, web.HTTPFound.status_code):
                    info["ffprobe"] = await ffprobe(str(realFile))
        except Exception:
            pass

    return web.json_response(data=info, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/history/{id}", "item_update")
async def item_update(request: Request, queue: DownloadQueue, encoder: Encoder, notify: EventBus) -> Response:
    """
    Update an item in the history.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    id: str = request.match_info.get("id")
    if not id:
        return web.json_response(data={"error": "id is required."}, status=web.HTTPBadRequest.status_code)

    item: Download | None = queue.done.get_by_id(id)
    if not item:
        return web.json_response(data={"error": "item not found."}, status=web.HTTPNotFound.status_code)

    post = await request.json()
    if not post:
        return web.json_response(data={"error": "no data provided."}, status=web.HTTPBadRequest.status_code)

    updated = False

    for k, v in post.items():
        if not hasattr(item.info, k):
            continue

        if getattr(item.info, k) == v:
            continue

        updated = True
        setattr(item.info, k, v)
        LOG.debug(f"Updated '{k}' to '{v}' for '{item.info.id}'")

    if updated:
        queue.done.put(item)
        await notify.emit(Events.ITEM_UPDATED, data=item.info)

    return web.json_response(
        data=item.info,
        status=web.HTTPOk.status_code if updated else web.HTTPNotModified.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/history/add/", "item_add")
async def item_add(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Add a URL to the download queue.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object

    """
    url: str | None = request.query.get("url")
    if not url:
        return web.json_response(data={"error": "url param is required."}, status=web.HTTPBadRequest.status_code)

    data: dict[str, str] = {"url": url}

    preset: str | None = request.query.get("preset")
    if preset:
        exists: Preset | None = Presets.get_instance().get(preset)
        if not exists:
            return web.json_response(
                data={"status": False, "message": f"Preset '{preset}' does not exist."},
                status=web.HTTPBadRequest.status_code,
            )
        data["preset"] = preset

    try:
        status: dict[str, str] = await queue.add(item=Item.format(data))
    except ValueError as e:
        return web.json_response(data={"status": False, "message": str(e)}, status=web.HTTPBadRequest.status_code)

    return web.json_response(
        data={"status": status.get("status") == "ok", "message": status.get("msg", "URL added")},
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/history/", "items_add")
async def items_add(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Add a URL to the download queue.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    data = await request.json()

    if isinstance(data, dict):
        data = [data]

    items = []
    for item in data:
        try:
            items.append(Item.format(item))
        except ValueError as e:
            return web.json_response(data={"error": str(e), "data": item}, status=web.HTTPBadRequest.status_code)

    status: list = await asyncio.wait_for(
        fut=asyncio.gather(*[queue.add(item=item) for item in items]),
        timeout=None,
    )

    response: list = []

    for i, item in enumerate(items):
        response.append({"item": item, "status": "ok" == status[i].get("status"), "msg": status[i].get("msg")})

    return web.json_response(data=response, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", r"api/history/{id}/archive", "history.item.archive.add")
async def item_archive_add(request: Request, queue: DownloadQueue) -> Response:
    """
    Manually mark an item as archived.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        config (Config): The configuration instance.

    Returns:
        Response: The response object.

    """
    if not (id := request.match_info.get("id")):
        return web.json_response(data={"error": "id is required."}, status=web.HTTPBadRequest.status_code)

    try:
        item: Download | None = queue.done.get_by_id(id)
        if not item:
            return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)
    except KeyError:
        return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)

    params: dict = item.get_ytdlp_opts().get_all()

    if not (archive_file := params.get("download_archive")):
        return web.json_response(
            data={"error": f"item '{item.info.title}' does not have an archive file."},
            status=web.HTTPBadRequest.status_code,
        )

    idDict = get_archive_id(url=item.info.url)
    if not (archive_id := idDict.get("archive_id")):
        return web.json_response(
            data={"error": f"item '{item.info.title}' does not have an archive ID."},
            status=web.HTTPBadRequest.status_code,
        )

    if len(archive_read(archive_file, [archive_id])) > 0:
        return web.json_response(
            data={"error": f"item '{item.info.title}' already archived."},
            status=web.HTTPConflict.status_code,
        )

    archive_add(archive_file, [archive_id])

    return web.json_response(
        data={"message": f"item '{item.info.title}' archived."},
        status=web.HTTPOk.status_code,
    )


@route("DELETE", r"api/history/{id}/archive", "history.item.archive.delete")
async def item_archive_delete(request: Request, queue: DownloadQueue) -> Response:
    """
    Remove an item from the archive.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.

    Returns:
        Response: The response object.

    """
    if not (id := request.match_info.get("id")):
        return web.json_response(data={"error": "id is required."}, status=web.HTTPBadRequest.status_code)

    try:
        item: Download | None = queue.done.get_by_id(id)
        if not item:
            return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)
    except KeyError:
        return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)

    url: str = item.info.url
    title: str = f" '{item.info.title}'"
    params: dict = item.get_ytdlp_opts().get_all()

    if not (archive_file := params.get("download_archive")):
        return web.json_response(
            data={"error": "Archive file is not configured."},
            status=web.HTTPBadRequest.status_code,
        )

    archive_file = Path(archive_file)

    if not archive_file.exists():
        return web.json_response(
            data={"error": f"Archive file '{archive_file}' does not exist."},
            status=web.HTTPNotFound.status_code,
        )

    idDict = get_archive_id(url=url)
    if not (archive_id := idDict.get("archive_id")):
        return web.json_response(
            data={"error": "item does not have an archive ID."},
            status=web.HTTPBadRequest.status_code,
        )

    if not archive_delete(archive_file, [archive_id]):
        return web.json_response(
            data={"error": f"item{title} not found in '{archive_file}' archive."},
            status=web.HTTPNotFound.status_code,
        )

    return web.json_response(
        data={"message": f"item{title} removed from '{archive_file}' archive."},
        status=web.HTTPOk.status_code,
    )
