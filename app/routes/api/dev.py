import asyncio
import json
import logging

from aiohttp import web
from aiohttp.web import Request, Response

from app.library import DownloadQueue
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.router import route

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/dev/loop/", "debug_loop")
async def debug_asyncio(config: Config, encoder: Encoder) -> Response:
    if not config.is_dev():
        return web.json_response(
            data={"error": "This endpoint is only available in development mode."},
            status=web.HTTPForbidden.status_code,
        )

    import traceback

    tasks = []
    for task in asyncio.all_tasks():
        task_info = {"task": str(task), "stack": []}
        for frame in task.get_stack():
            formatted = traceback.format_stack(f=frame)
            task_info["stack"].extend(formatted)

        tasks.append(task_info)

    return web.json_response(
        data={
            "total_tasks": len(tasks),
            "loop": str(asyncio.get_event_loop()),
            "tasks": tasks,
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/dev/workers/", "pool_list")
async def pool_list(config: Config, queue: DownloadQueue) -> Response:
    """
    Get the workers status.

    Args:
        config (Config): The configuration object.
        queue (DownloadQueue): The download queue object.

    Returns:
        Response: The response object.

    """
    if not config.is_dev():
        return web.json_response(
            {"error": "This endpoint is only available in development mode."},
            status=web.HTTPNotFound.status_code,
        )

    if queue.pool is None:
        return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

    status = queue.pool.get_workers_status()

    data = []

    for worker in status:
        worker_status = status.get(worker)
        data.append(
            {
                "id": worker,
                "data": {"status": "Waiting for download."} if worker_status is None else worker_status,
            }
        )

    return web.json_response(
        data={
            "open": queue.pool.has_open_workers(),
            "count": queue.pool.get_available_workers(),
            "workers": data,
        },
        status=web.HTTPOk.status_code,
        dumps=lambda obj: json.dumps(obj, default=lambda o: f"<<non-serializable: {type(o).__qualname__}>>"),
    )


@route("POST", "api/dev/workers/", "pool_start")
async def pool_restart(config: Config, queue: DownloadQueue) -> Response:
    """
    Restart the workers pool.

    Args:
        config (Config): The configuration object.
        queue (DownloadQueue): The download queue object.

    Returns:
        Response: The response object.

    """
    if not config.is_dev():
        return web.json_response(
            {"error": "This endpoint is only available in development mode."},
            status=web.HTTPNotFound.status_code,
        )

    if queue.pool is None:
        return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

    queue.pool.start()

    return web.json_response({"message": "Workers pool being restarted."}, status=web.HTTPOk.status_code)


@route("PATCH", "api/dev/workers/{id}", "worker_restart")
async def worker_restart(request: Request, config: Config, queue: DownloadQueue) -> Response:
    """
    Restart a worker.

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        queue (DownloadQueue): The download queue object.

    Returns:
        Response: The response object

    """
    if not config.is_dev():
        return web.json_response(
            {"error": "This endpoint is only available in development mode."},
            status=web.HTTPNotFound.status_code,
        )

    worker_id: str = request.match_info.get("id")
    if not worker_id:
        return web.json_response({"error": "worker id is required."}, status=web.HTTPBadRequest.status_code)

    if queue.pool is None:
        return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

    status = await queue.pool.restart(worker_id, "requested by user.")

    return web.json_response({"status": "restarted" if status else "in_error_state"}, status=web.HTTPOk.status_code)


@route("DELETE", "api/dev/workers/{id}", "worker_stop")
async def worker_stop(request: Request, config: Config, queue: DownloadQueue) -> Response:
    """
    Stop a worker.

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        queue (DownloadQueue): The download queue object.

    Returns:
        Response: The response object.

    """
    if not config.is_dev():
        return web.json_response(
            {"error": "This endpoint is only available in development mode."},
            status=web.HTTPNotFound.status_code,
        )

    worker_id: str = request.match_info.get("id")
    if not worker_id:
        raise web.HTTPBadRequest(text="worker id is required.")

    if queue.pool is None:
        return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

    status = await queue.pool.stop(worker_id, "requested by user.")

    return web.json_response({"status": "stopped" if status else "in_error_state"}, status=web.HTTPOk.status_code)
