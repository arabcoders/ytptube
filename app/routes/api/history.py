import asyncio
import logging
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.Download import Download
from app.library.DownloadQueue import DownloadQueue
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.ItemDTO import Item
from app.library.Presets import Preset, Presets
from app.library.router import route

if TYPE_CHECKING:
    from library.Download import Download

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", r"api/history/", "items_list")
async def items_list(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Get the history with optional pagination support.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    Query Parameters:
        type (str): Type of items to return - "all", "queue", or "done". Default: "all"
        page (int): Page number for pagination (1-indexed). Only used when type != "all"
        per_page (int): Items per page. Default: 50, Max: 1000. Only used when type != "all"
        order (str): Sort order - "ASC" or "DESC". Default: "DESC". Only used when type != "all"

    """
    from app.library.DataStore import StoreType

    store_type = request.query.get("type", "all").lower()
    stores: list[str] = ["all", StoreType.QUEUE.value, StoreType.HISTORY.value]
    if store_type not in stores:
        return web.json_response(
            data={"error": f"type must be one of {', '.join(stores)}."},
            status=web.HTTPBadRequest.status_code,
        )

    # Legacy behavior: return all items without pagination, will be removed in future.
    if "all" == store_type:
        data: dict = {"queue": [], "history": []}
        q = queue.get()

        data["queue"].extend([q.get("queue", {}).get(k) for k in q.get("queue", {})])
        data["history"].extend([q.get("done", {}).get(k) for k in q.get("done", {})])

        return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=encoder.encode)

    ds = queue.queue if store_type == StoreType.QUEUE.value else queue.done

    try:
        page = int(request.query.get("page", 1))
        per_page = int(request.query.get("per_page", 50))
        order = request.query.get("order", "DESC").upper()
    except ValueError:
        return web.json_response(
            data={"error": "page and per_page must be valid integers."},
            status=web.HTTPBadRequest.status_code,
        )

    if page < 1:
        return web.json_response(data={"error": "page must be >= 1."}, status=web.HTTPBadRequest.status_code)

    if per_page < 1 or per_page > 200:
        return web.json_response(
            data={"error": "per_page must be between 1 and 1000."},
            status=web.HTTPBadRequest.status_code,
        )

    if order not in ("ASC", "DESC"):
        return web.json_response(
            data={"error": "order must be ASC or DESC."},
            status=web.HTTPBadRequest.status_code,
        )

    items, total, current_page, total_pages = ds.get_items_paginated(page=page, per_page=per_page, order=order)
    data = {
        "pagination": {
            "page": current_page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": current_page < total_pages,
            "has_prev": current_page > 1,
        },
        "items": [item for _, item in items],
    }

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
async def item_view(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
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

    item: Download | None = queue.done.get_by_id(id) or queue.queue.get_by_id(id)
    if not item:
        return web.json_response(data={"error": "item not found."}, status=web.HTTPNotFound.status_code)

    if not item.info:
        return web.json_response(data={"error": "item has no info."}, status=web.HTTPNotFound.status_code)

    info: dict = {
        **item.info.serialize(),
        "ffprobe": {},
    }

    if "finished" == item.info.status and (filename := item.info.get_file()):
        from app.library.ffprobe import ffprobe

        try:
            info["ffprobe"] = await ffprobe(filename)
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
        notify.emit(Events.ITEM_UPDATED, data=item.info)

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
async def item_archive_add(request: Request, queue: DownloadQueue, notify: EventBus) -> Response:
    """
    Manually mark an item as archived.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        notify (EventBus): The event bus instance.

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

    if not item.info.is_archivable:
        return web.json_response(
            data={"error": f"item '{item.info.title}' does not have an archive file."},
            status=web.HTTPBadRequest.status_code,
        )

    if not item.info.archive_id:
        return web.json_response(
            data={"error": f"item '{item.info.title}' does not have an archive ID."},
            status=web.HTTPBadRequest.status_code,
        )

    if item.info.is_archived:
        return web.json_response(
            data={"error": f"item '{item.info.title}' already archived."},
            status=web.HTTPConflict.status_code,
        )

    if not item.info.archive_add():
        return web.json_response(
            data={"error": f"item '{item.info.title}' could not be added to archive."},
            status=web.HTTPInternalServerError.status_code,
        )

    item.info.archive_status(force=True)
    queue.done.put(item, no_notify=True)
    notify.emit(Events.ITEM_UPDATED, data=item.info)

    return web.json_response(
        data={"message": f"item '{item.info.title}' archived."},
        status=web.HTTPOk.status_code,
    )


@route("DELETE", r"api/history/{id}/archive", "history.item.archive.delete")
async def item_archive_delete(request: Request, queue: DownloadQueue, notify: EventBus) -> Response:
    """
    Remove an item from the archive.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        notify (EventBus): The event bus instance.

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

    if not item.info.is_archivable:
        return web.json_response(
            data={"error": f"item '{item.info.title}' does not have an archive file."},
            status=web.HTTPBadRequest.status_code,
        )

    if not item.info.archive_id:
        return web.json_response(
            data={"error": f"item '{item.info.title}' does not have an archive ID."},
            status=web.HTTPBadRequest.status_code,
        )

    if not item.info.is_archived:
        return web.json_response(
            data={"error": f"item '{item.info.title}' not archived."},
            status=web.HTTPConflict.status_code,
        )

    if not item.info.archive_delete():
        return web.json_response(
            data={"error": f"item '{item.info.title}' not found in archive file."},
            status=web.HTTPInternalServerError.status_code,
        )

    item.info.archive_status(force=True)
    queue.done.put(item, no_notify=True)
    notify.emit(Events.ITEM_UPDATED, data=item.info)

    return web.json_response(
        data={"message": f"item '{item.info.title}' removed from archive."},
        status=web.HTTPOk.status_code,
    )
