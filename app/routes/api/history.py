import asyncio
from pathlib import Path
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response
from aiohttp.web_response import StreamResponse

from app.features.core.utils import api_error_response
from app.features.downloads.items import Item
from app.features.downloads.runtime.core import Download
from app.features.downloads.runtime.queue_manager import DownloadQueue
from app.features.downloads.runtime.utils import safe_relative_path
from app.features.downloads.store import StoreType
from app.features.presets.schemas import Preset
from app.features.presets.service import Presets
from app.features.streaming.library.thumbnail import ensure_thumb, pick_local_thumb
from app.library.cache import Cache
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.log import get_logger
from app.library.router import route
from app.library.Utils import calc_download_path, get_file_sidecar, rename_file

LOG = get_logger()


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
    from app.features.downloads.store import StoreType

    store_type: str = request.query.get("type", "queue").lower()
    try:
        store_type: StoreType = StoreType.from_value(store_type)
    except ValueError:
        return api_error_response(
            f"type must be one of {', '.join(StoreType.all())}.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.type"},
        )

    ds = queue.queue if store_type == StoreType.QUEUE else queue.done

    try:
        page = int(request.query.get("page", 1))
        per_page = int(request.query.get("per_page", config.default_pagination))
        order: str = request.query.get("order", "DESC").upper()
    except ValueError:
        return api_error_response(
            "page and per_page must be valid integers.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.page"},
        )

    if page < 1:
        return api_error_response(
            "page must be >= 1.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.page"},
        )

    if per_page < 1 or per_page > 1000:
        return api_error_response(
            "per_page must be between 1 and 1000.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.per_page"},
        )

    if order not in ("ASC", "DESC"):
        return api_error_response(
            "order must be ASC or DESC.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.order"},
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
                download.info.sidecar = download.info.get_file_sidecar()
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
async def items_live(request: Request, queue: DownloadQueue, encoder: Encoder, config: Config) -> Response:
    """
    Get live queue data

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.
        config (Config): The configuration instance.

    Returns:
        Response: The response object with live queue items.

    """
    try:
        limit = int(request.query.get("limit", config.queue_display_limit))
    except ValueError:
        return api_error_response(
            "limit must be a valid integer.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.limit"},
        )

    return web.json_response(
        data={**queue.live_queue(limit), "history_count": await queue.done.get_total_count()},
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
        return api_error_response(
            "Type is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.type"},
        )

    try:
        storeType: StoreType = StoreType.from_value(storeType)
    except ValueError:
        return api_error_response(
            f"type must be one of '{StoreType.all()}'.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.type"},
        )

    if ids:
        if storeType == StoreType.HISTORY:
            result = await queue.clear_bulk(ids, remove_file=remove_file)
            return web.json_response(
                data={"items": {}, "deleted": int(result.get("deleted", 0))},
                status=web.HTTPOk.status_code,
                dumps=encoder.encode,
            )

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
        return api_error_response(
            "either 'ids' or 'status' filter is required.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    if storeType == StoreType.HISTORY:
        result = await queue.clear_by_status(status_filter, remove_file=remove_file)
        deleted = int(result.get("deleted", 0))
        if deleted < 1:
            return web.json_response(
                data={"items": {}, "deleted": 0},
                status=web.HTTPOk.status_code,
                dumps=encoder.encode,
            )

        return web.json_response(
            data={"items": {}, "deleted": deleted},
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )

    ds = queue.queue
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
        return web.json_response(
            data={"items": {}, "deleted": 0},
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )

    return web.json_response(
        data={
            "items": await queue.cancel(items_to_delete),
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
    id: str | None = request.match_info.get("id")
    if not id:
        return api_error_response("id is required.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    item: Download | None = await queue.done.get_by_id(id) or await queue.queue.get_by_id(id)
    if not item:
        return api_error_response(
            "item not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.item"},
        )

    if not item.info:
        return api_error_response(
            "item has no info.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.item"},
        )

    info: dict = {
        **item.info.serialize(),
        "ffprobe": {},
        "sidecar": {},
    }

    if "finished" == item.info.status and (filename := item.info.get_file()):
        try:
            from app.features.streaming.library.ffprobe import ffprobe, ffprobe_bin

            if ffprobe_bin() is not None:
                info["ffprobe"] = await ffprobe(filename)
        except Exception:
            pass

        try:
            info["sidecar"] = item.info.get_file_sidecar()
        except Exception:
            pass

    return web.json_response(data=info, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route(["GET", "HEAD"], r"api/history/{id}/thumbnail", "history.item.thumbnail")
async def item_thumbnail(request: Request, queue: DownloadQueue, config: Config) -> StreamResponse:
    if not (id := request.match_info.get("id")):
        return api_error_response("id is required.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    miss_key: str = f"thumb_missing:{id}"
    cache: Cache = Cache.get_instance()

    item: Download | None = await queue.done.get_by_id(id)
    if not item or not item.info:
        return api_error_response(
            "item not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.item"},
        )

    if cache.has(miss_key):
        return api_error_response(
            "thumbnail not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.file"},
        )

    filepath: Path | None = item.info.get_file(download_path=Path(config.download_path))
    if not filepath or not filepath.exists() or not filepath.is_file():
        cache.set(miss_key, value=True, ttl=30.0)
        return api_error_response(
            "thumbnail not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.file"},
        )

    cache.delete(miss_key)

    local_thumb: Path | None = pick_local_thumb(filepath)
    if local_thumb and local_thumb.exists() and local_thumb.is_file():
        return web.FileResponse(path=str(local_thumb))

    try:
        generated: Path | None = await ensure_thumb(
            filepath, Path(config.temp_path) / "thumbnails", item_id=item.info._id
        )
    except OSError as e:
        LOG.warning(
            "Failed to generate thumbnail for file '%s'.",
            filepath,
            extra={"route": "history.item.thumbnail", "item_id": id, "file_path": str(filepath), "error": str(e)},
            exc_info=True,
        )
        generated = None
    except Exception:
        LOG.exception(
            "Failed to generate thumbnail for file '%s'.",
            filepath,
            extra={"route": "history.item.thumbnail", "item_id": id, "file_path": str(filepath)},
        )
        generated = None

    if generated and generated.exists() and generated.is_file():
        return web.FileResponse(path=str(generated))

    return api_error_response(
        "thumbnail not found.",
        code="NOT_FOUND",
        status=web.HTTPNotFound.status_code,
        params={"resource": "api.resources.file"},
    )


@route("POST", r"api/history/{id}/rename", "history.item.rename")
async def item_rename(
    request: Request,
    queue: DownloadQueue,
    encoder: Encoder,
    notify: EventBus,
    config: Config,
) -> Response:
    if not (id := request.match_info.get("id")):
        return api_error_response("id is required.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    item: Download | None = await queue.done.get_by_id(id)
    if not item:
        return api_error_response(
            f"item '{id}' not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.item"},
        )

    try:
        post: dict = await request.json()
        if not post:
            return api_error_response("no data provided.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)
    except Exception:
        return api_error_response("invalid JSON body.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    new_name: str = str(post.get("new_name") or "").strip()
    if not new_name:
        return api_error_response(
            "new_name is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.name"},
        )

    filepath: Path | None = item.info.get_file(download_path=Path(config.download_path))
    if not filepath:
        return api_error_response(
            "item has no downloaded file.",
            code="NOT_FOUND",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.file"},
        )

    new_path = filepath.parent / new_name
    try:
        valid_parent = new_path.resolve(strict=False).parent == filepath.parent.resolve()
    except (OSError, ValueError):
        valid_parent = False
    if Path(new_name).parts != (new_name,) or not valid_parent:
        return api_error_response(
            "New name must not contain path separators.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.name"},
        )

    try:
        renamed, sidecar_renamed = rename_file(filepath, new_name)
    except ValueError as e:
        return api_error_response(
            str(e),
            code="ALREADY_EXISTS",
            status=web.HTTPConflict.status_code,
            params={"resource": "api.resources.file"},
        )
    except OSError as e:
        LOG.exception(
            "Failed to rename history item file '%s'.",
            filepath,
            extra={"route": "history.item.rename", "item_id": id, "file_path": str(filepath), "new_name": new_name},
        )
        return api_error_response(
            str(e),
            code="OPERATION_FAILED",
            status=web.HTTPInternalServerError.status_code,
        )

    item_dir: Path = (
        Path(item.info.download_dir)
        if item.info.download_dir
        else Path(calc_download_path(base_path=config.download_path, folder=item.info.folder, create_path=False))
    )
    item.info.filename = safe_relative_path(renamed, item_dir, Path(config.download_path))

    try:
        item.info.sidecar = get_file_sidecar(renamed)
    except Exception:
        item.info.sidecar = {}

    await queue.done.put(item, no_notify=True)
    notify.emit(Events.ITEM_UPDATED, data=item.info)

    sidecar_count: int = len(sidecar_renamed)
    LOG.info(
        "Renamed file '%s' to '%s'.",
        filepath,
        renamed,
        extra={
            "route": "history.item.rename",
            "item_id": id,
            "old_path": str(filepath),
            "new_path": str(renamed),
            "sidecar_count": sidecar_count,
        },
    )

    return web.json_response(
        data=item.info,
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


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
    id: str | None = request.match_info.get("id")
    if not id:
        return api_error_response("id is required.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    item: Download | None = await queue.done.get_by_id(id)
    if not item:
        return api_error_response(
            "item not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.item"},
        )

    post = await request.json()
    if not post:
        return api_error_response("no data provided.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    updated = False

    for k, v in post.items():
        if not hasattr(item.info, k):
            continue

        if getattr(item.info, k) == v:
            continue

        updated = True
        setattr(item.info, k, v)
        LOG.debug(
            "Updated history item '%s' field '%s'.",
            item.info.id,
            k,
            extra={"route": "history.item_update", "item_id": item.info.id, "field": k, "value": v},
        )

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
        return api_error_response(
            "url param is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.url"},
        )

    data: dict[str, str] = {"url": url}

    preset: str | None = request.query.get("preset")
    if preset:
        exists: Preset | None = Presets.get_instance().get(preset)
        if not exists:
            return api_error_response(
                f"Preset '{preset}' does not exist.",
                code="NOT_FOUND",
                status=web.HTTPBadRequest.status_code,
                params={"resource": "api.resources.preset"},
            )
        data["preset"] = preset

    try:
        status: dict[str, str] = await queue.add(item=Item.format(data))
    except ValueError as e:
        return api_error_response(
            str(e),
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.url"},
            detail=str(e),
        )

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

    Query Parameters:
        sync (bool): If true, wait for all items to be processed synchronously. Default: false

    """
    data = await request.json()

    if isinstance(data, dict):
        data = [data]

    items: list[Item] = []
    for item in data:
        try:
            items.append(Item.format(item))
        except ValueError as e:
            return api_error_response(
                str(e),
                code="INVALID",
                status=web.HTTPBadRequest.status_code,
                params={"field": "api.fields.url"},
                detail=str(e),
            )

    if "true" == request.query.get("sync", "false").lower():
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

    from app.features.downloads.runtime.utils import handle_task_exception

    batch_id: str = f"batch_{asyncio.get_running_loop().time():.0f}"

    for idx, item in enumerate(items):
        if not item.extras:
            item.extras = {}

        if len(items) > 1:
            item.extras["batch_id"] = batch_id
            item.extras["batch_index"] = idx
            item.extras["batch_total"] = len(items)

        task = asyncio.create_task(queue.add(item=item), name=f"bulk_add_{batch_id}_{idx}")
        task.add_done_callback(lambda t: handle_task_exception(t, LOG))

    return web.json_response(
        data={
            "status": "accepted",
            "message": f"Accepted {len(items)} item(s) for processing",
            "batch_id": batch_id,
            "count": len(items),
        },
        status=web.HTTPAccepted.status_code,
        dumps=encoder.encode,
    )


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
        return api_error_response(
            "ids array is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    if not isinstance(ids, list):
        return api_error_response(
            "ids must be an array.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

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
        return api_error_response(
            "ids array is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    if not isinstance(ids, list):
        return api_error_response(
            "ids must be an array.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    status: dict[str, str] = await queue.pause_items(ids)

    return web.json_response(data=status, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/history/force-start", "items_force_start")
async def items_force_start(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """Start queued downloads while bypassing worker and extractor limits."""
    data = await request.json()
    if not (ids := data.get("ids", [])):
        return api_error_response(
            "ids array is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    if not isinstance(ids, list):
        return api_error_response(
            "ids must be an array.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    status: dict[str, str] = await queue.force_start_items(ids)
    return web.json_response(data=status, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/history/position", "items_position")
async def items_position(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    """Move queued downloads to the front or back of pending downloads."""
    data = await request.json()
    if not (ids := data.get("ids", [])):
        return api_error_response(
            "ids array is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    if not isinstance(ids, list):
        return api_error_response(
            "ids must be an array.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    position = data.get("position")
    if position not in ("front", "back"):
        return api_error_response(
            "position must be 'front' or 'back'.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.position"},
        )

    status: dict[str, str] = await queue.position_items(ids, position)
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
        return api_error_response(
            "ids array is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    if not isinstance(ids, list):
        return api_error_response(
            "ids must be an array.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    status: dict[str, str] = await queue.cancel(ids)

    return web.json_response(data=status, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/history/retry", "items_retry")
async def items_retry(request: Request, queue: DownloadQueue, encoder: Encoder) -> Response:
    data = await request.json()
    ids = data.get("ids")
    status = data.get("status")

    if ids is not None and (
        not isinstance(ids, list) or not all(isinstance(item_id, str) and item_id.strip() for item_id in ids)
    ):
        return api_error_response(
            "ids must be an array.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    if not ids and not status:
        return api_error_response(
            "either 'ids' or 'status' is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
        )

    if status is not None and (not isinstance(status, str) or not status.strip()):
        return api_error_response(
            "status must be a non-empty string.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.status"},
        )

    count = await queue.retry(ids=ids or None, status=None if ids else status)
    return web.json_response(
        data={"status": "accepted", "count": count},
        status=web.HTTPAccepted.status_code,
        dumps=encoder.encode,
    )


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
        return api_error_response("id is required.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    try:
        item: Download | None = await queue.done.get_by_id(id)
        if not item:
            return api_error_response(
                f"item '{id}' not found.",
                code="NOT_FOUND",
                status=web.HTTPNotFound.status_code,
                params={"resource": "api.resources.item"},
            )
    except KeyError:
        return api_error_response(
            f"item '{id}' not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.item"},
        )

    if not item.info.is_archivable:
        return api_error_response(
            f"item '{item.info.title}' does not have an archive file.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.item"},
        )

    if not item.info.archive_id:
        return api_error_response(
            f"item '{item.info.title}' does not have an archive ID.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.item"},
        )

    if item.info.is_archived:
        return api_error_response(
            f"item '{item.info.title}' already archived.",
            code="ALREADY_EXISTS",
            status=web.HTTPConflict.status_code,
            params={"resource": "api.resources.item"},
        )

    if not item.info.archive_add():
        return api_error_response(
            f"item '{item.info.title}' could not be added to archive.",
            code="OPERATION_FAILED",
            status=web.HTTPInternalServerError.status_code,
            params={"resource": "api.resources.item"},
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
        return api_error_response("id is required.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    try:
        item: Download | None = await queue.done.get_by_id(id)
        if not item:
            return api_error_response(
                f"item '{id}' not found.",
                code="NOT_FOUND",
                status=web.HTTPNotFound.status_code,
                params={"resource": "api.resources.item"},
            )
    except KeyError:
        return api_error_response(
            f"item '{id}' not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.item"},
        )

    if not item.info.is_archivable:
        return api_error_response(
            f"item '{item.info.title}' does not have an archive file.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.item"},
        )

    if not item.info.archive_id:
        return api_error_response(
            f"item '{item.info.title}' does not have an archive ID.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.item"},
        )

    if not item.info.is_archived:
        return api_error_response(
            f"item '{item.info.title}' not archived.",
            code="INVALID",
            status=web.HTTPConflict.status_code,
            params={"resource": "api.resources.item"},
        )

    if not item.info.archive_delete():
        return api_error_response(
            f"item '{item.info.title}' not found in archive file.",
            code="OPERATION_FAILED",
            status=web.HTTPInternalServerError.status_code,
            params={"resource": "api.resources.item"},
        )

    item.info.archive_status(force=True)
    await queue.done.put(item, no_notify=True)
    notify.emit(Events.ITEM_UPDATED, data=item.info)

    return web.json_response(
        data={"message": f"item '{item.info.title}' removed from archive."},
        status=web.HTTPOk.status_code,
    )


@route("POST", r"api/history/{id}/nfo", "history.item.nfo.generate")
async def item_nfo_generate(request: Request, queue: DownloadQueue) -> Response:
    """
    Generate NFO file for an existing download.

    Args:
        request: The request object
        queue: DownloadQueue instance

    Request Body:
        type: 'tv' or 'movie' (default: 'tv')
        overwrite: bool (default: false)

    Returns:
        Response with NFO file path on success

    """
    from app.features.ytdlp.extractor import fetch_info
    from app.yt_dlp_plugins.postprocessor.nfo_maker import NFOMakerPP

    if not (id := request.match_info.get("id")):
        return api_error_response("id is required.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    try:
        item: Download | None = await queue.done.get_by_id(id)
        if not item:
            return api_error_response(
                f"item '{id}' not found.",
                code="NOT_FOUND",
                status=web.HTTPNotFound.status_code,
                params={"resource": "api.resources.item"},
            )
    except KeyError:
        return api_error_response(
            f"item '{id}' not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.item"},
        )

    if not item.info.filename:
        return api_error_response(
            "item has no downloaded file.",
            code="NOT_FOUND",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.file"},
        )

    filepath = item.info.get_file()
    if not filepath or not filepath.exists():
        return api_error_response(
            f"file '{item.info.filename}' not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.file"},
        )

    post = {}
    if request.body_exists:
        try:
            post = await request.json() or {}
        except Exception:
            post = {}

    mode: str = str(post.get("type", "tv")).lower()
    if mode not in ("tv", "movie"):
        return api_error_response(
            "type must be 'tv' or 'movie'.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.mode"},
        )

    try:
        (info_dict, _logs) = await fetch_info(
            config=item.info.get_ytdlp_opts().get_all(),
            url=item.info.url,
            no_archive=True,
            follow_redirect=True,
            budget_sleep=True,
        )

        if not info_dict:
            return api_error_response(
                "failed to extract metadata from URL.",
                code="OPERATION_FAILED",
                status=web.HTTPInternalServerError.status_code,
            )

        result = NFOMakerPP.generate_nfo(
            info_dict=info_dict,
            filepath=filepath,
            mode=mode,
            overwrite=bool(post.get("overwrite", False)),
            logger=LOG,
        )

        if result["success"]:
            return web.json_response(
                data={"message": result["message"], "nfo_file": result.get("nfo_file")},
                status=web.HTTPOk.status_code,
            )

        return api_error_response(
            result["message"],
            code="OPERATION_FAILED",
            status=web.HTTPBadRequest.status_code,
        )
    except Exception as e:
        LOG.exception(
            "Failed to generate NFO for item '%s'.",
            id,
            extra={"route": "history.item.nfo.generate", "item_id": id, "file_path": str(filepath), "mode": mode},
        )
        return api_error_response(
            f"failed to generate NFO: {e!s}",
            code="OPERATION_FAILED",
            status=web.HTTPInternalServerError.status_code,
        )
