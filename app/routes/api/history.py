import asyncio
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web
from aiohttp.web import Request, Response

from app.features.presets.schemas import Preset
from app.features.presets.service import Presets
from app.library.config import Config
from app.library.DataStore import StoreType
from app.library.downloads import Download, DownloadQueue
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.ItemDTO import Item
from app.library.router import route

if TYPE_CHECKING:
    from library.downloads import Download


LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", r"api/history/", "items_list")
async def items_list(request: Request, queue: DownloadQueue, encoder: Encoder, config: Config) -> Response:
    """
    Get the history with optional pagination support.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.
        config (Config): The configuration instance.

    Returns:
        Response: The response object.

    Query Parameters:
        type (str): Type of items to return - "all", "queue", or "done". Default: "all"
        page (int): Page number for pagination (1-indexed). Only used when type != "all"
        per_page (int): Items per page. Default: 50, Max: 1000. Only used when type != "all"
        order (str): Sort order - "ASC" or "DESC". Default: "DESC". Only used when type != "all"
        status (str): Filter by status. Use "!status" to exclude a status. Only used when type != "all"
                      Examples: "?status=finished" or "?status=!finished"

    """
    from app.library.DataStore import StoreType

    store_type: str = request.query.get("type", "queue").lower()
    try:
        store_type: StoreType = StoreType.from_value(store_type)
    except ValueError:
        return web.json_response(
            data={"error": f"type must be one of {', '.join(StoreType.all())}."},
            status=web.HTTPBadRequest.status_code,
        )

    ds = queue.queue if store_type == StoreType.QUEUE else queue.done

    try:
        page = int(request.query.get("page", 1))
        per_page = int(request.query.get("per_page", config.default_pagination))
        order: str = request.query.get("order", "DESC").upper()
    except ValueError:
        return web.json_response(
            data={"error": "page and per_page must be valid integers."},
            status=web.HTTPBadRequest.status_code,
        )

    if page < 1:
        return web.json_response(data={"error": "page must be >= 1."}, status=web.HTTPBadRequest.status_code)

    if per_page < 1 or per_page > 1000:
        return web.json_response(
            data={"error": "per_page must be between 1 and 1000."},
            status=web.HTTPBadRequest.status_code,
        )

    if order not in ("ASC", "DESC"):
        return web.json_response(
            data={"error": "order must be ASC or DESC."},
            status=web.HTTPBadRequest.status_code,
        )

    status_filter = request.query.get("status", None)

    items, total, current_page, total_pages = await ds.get_items_paginated(
        page=page, per_page=per_page, order=order, status_filter=status_filter
    )

    if store_type == StoreType.HISTORY:
        for _, download in items:
            if not download.info:
                continue

            try:
                download.info.sidecar = download.get_file_sidecar()
            except Exception:
                download.info.sidecar = {}

    return web.json_response(
        data={
            "type": store_type.value,
            "pagination": {
                "page": current_page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": current_page < total_pages,
                "has_prev": current_page > 1,
            },
            "items": [download.info for _, download in items],
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/history/live", "items_live")
async def items_live(queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Get live queue data

    Args:
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object with live queue items.

    """
    return web.json_response(
        data={
            "queue": (await queue.get("queue"))["queue"],
            "history_count": await queue.done.get_total_count(),
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("DELETE", "api/history/", "items_delete")
async def items_delete(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Delete items from the queue or history.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    Request Body:
        type (str): "queue" or "done"
        status (str, optional): Filter by status (e.g., "finished" or "!finished")
        ids (list[str], optional): Specific IDs to delete (if provided, ignores status filter)
        remove_file (bool, optional): Whether to remove files. Default: True

    """
    data = await request.json()

    ids = data.get("ids")
    remove_file: bool = bool(data.get("remove_file", True))
    storeType = data.get("type", data.get("where"))

    if not storeType:
        return web.json_response(data={"error": "Type is required."}, status=web.HTTPBadRequest.status_code)

    try:
        storeType: StoreType = StoreType.from_value(storeType)
    except ValueError:
        return web.json_response(
            data={"error": f"type must be one of '{StoreType.all()}'."},
            status=web.HTTPBadRequest.status_code,
        )

    ds = queue.queue if storeType == StoreType.QUEUE else queue.done

    if ids:
        return web.json_response(
            data={
                "items": await (
                    queue.cancel(ids) if storeType == StoreType.QUEUE else queue.clear(ids, remove_file=remove_file)
                ),
                "deleted": len(ids),
            },
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )

    status_filter = data.get("status")
    if not status_filter:
        return web.json_response(
            data={"error": "either 'ids' or 'status' filter is required."},
            status=web.HTTPBadRequest.status_code,
        )

    items_to_delete = []
    page = 1
    per_page = 1000

    while True:
        items, _, current_page, total_pages = await ds.get_items_paginated(
            page=page, per_page=per_page, order="DESC", status_filter=status_filter
        )

        items_to_delete.extend([item_id for item_id, _ in items])

        if current_page >= total_pages:
            break

        page += 1

    if not items_to_delete:
        return web.json_response(data={"error": "No items matched the filter."}, status=web.HTTPBadRequest.status_code)

    return web.json_response(
        data={
            "items": await (
                queue.cancel(items_to_delete)
                if storeType == StoreType.QUEUE
                else queue.clear(items_to_delete, remove_file=remove_file)
            ),
            "deleted": len(items_to_delete),
        },
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

    item: Download | None = await queue.done.get_by_id(id) or await queue.queue.get_by_id(id)
    if not item:
        return web.json_response(data={"error": "item not found."}, status=web.HTTPNotFound.status_code)

    if not item.info:
        return web.json_response(data={"error": "item has no info."}, status=web.HTTPNotFound.status_code)

    info: dict = {
        **item.info.serialize(),
        "ffprobe": {},
        "sidecar": {},
    }

    if "finished" == item.info.status and (filename := item.info.get_file()):
        from app.library.ffprobe import ffprobe

        try:
            info["ffprobe"] = await ffprobe(filename)
        except Exception:
            pass

        try:
            info["sidecar"] = item.info.get_file_sidecar()
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

    item: Download | None = await queue.done.get_by_id(id)
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
        await queue.done.put(item)
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

    status: list[dict] = await asyncio.wait_for(
        fut=asyncio.gather(*[queue.add(item=item) for item in items]),
        timeout=None,
    )

    response: list[dict[str, Any]] = []

    for i, item in enumerate(items):
        it = {"item": item, "status": "ok" == status[i].get("status"), "msg": status[i].get("msg")}
        if status[i].get("hidden"):
            it["hidden"] = True
        response.append(it)

    return web.json_response(data=response, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/history/start", "items_start")
async def items_start(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Start one or more queued downloads.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    data = await request.json()
    if not (ids := data.get("ids", [])):
        return web.json_response(data={"error": "ids array is required."}, status=web.HTTPBadRequest.status_code)

    if not isinstance(ids, list):
        return web.json_response(data={"error": "ids must be an array."}, status=web.HTTPBadRequest.status_code)

    status: dict[str, str] = await queue.start_items(ids)

    return web.json_response(data=status, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/history/pause", "items_pause")
async def items_pause(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Pause one or more queued downloads.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    data = await request.json()
    if not (ids := data.get("ids", [])):
        return web.json_response(data={"error": "ids array is required."}, status=web.HTTPBadRequest.status_code)

    if not isinstance(ids, list):
        return web.json_response(data={"error": "ids must be an array."}, status=web.HTTPBadRequest.status_code)

    status: dict[str, str] = await queue.pause_items(ids)

    return web.json_response(data=status, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/history/cancel", "items_cancel")
async def items_cancel(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """
    Cancel one or more queued downloads.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    data = await request.json()
    if not (ids := data.get("ids", [])):
        return web.json_response(data={"error": "ids array is required."}, status=web.HTTPBadRequest.status_code)

    if not isinstance(ids, list):
        return web.json_response(data={"error": "ids must be an array."}, status=web.HTTPBadRequest.status_code)

    status: dict[str, str] = await queue.cancel(ids)

    return web.json_response(data=status, status=web.HTTPOk.status_code, dumps=encoder.encode)


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
        item: Download | None = await queue.done.get_by_id(id)
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
    await queue.done.put(item, no_notify=True)
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
        item: Download | None = await queue.done.get_by_id(id)
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
    await queue.done.put(item, no_notify=True)
    notify.emit(Events.ITEM_UPDATED, data=item.info)

    return web.json_response(
        data={"message": f"item '{item.info.title}' removed from archive."},
        status=web.HTTPOk.status_code,
    )
