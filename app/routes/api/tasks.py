import logging
import uuid

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.router import route
from app.library.Tasks import Task, TaskFailure, TaskResult, Tasks
from app.library.Utils import init_class, validate_url, validate_uuid

LOG: logging.Logger = logging.getLogger(__name__)


@route("POST", "api/tasks/inspect", "task_handler_inspect")
async def task_handler_inspect(request: Request, tasks: Tasks, encoder: Encoder, config: Config) -> Response:
    data = await request.json()

    url: str | None = data.get("url") if isinstance(data, dict) else None
    if not url:
        return web.json_response({"error": "url is required."}, status=web.HTTPBadRequest.status_code)
    try:
        validate_url(url, allow_internal=config.allow_internal_urls)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=web.HTTPBadRequest.status_code)

    preset: str = data.get("preset", "") if isinstance(data, dict) else ""
    handler_name: str | None = data.get("handler") if isinstance(data, dict) else None

    try:
        result: TaskResult | TaskFailure = await tasks.get_handler().inspect(
            url=url, preset=preset, handler_name=handler_name
        )
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            {"error": "Failed to inspect handler.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )

    return web.json_response(
        data=result,
        status=web.HTTPBadRequest.status_code if isinstance(result, TaskFailure) else web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/tasks/", "tasks")
async def tasks(encoder: Encoder) -> Response:
    """
    Get the tasks.

    Args:
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    return web.json_response(data=Tasks.get_instance().get_all(), status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("PUT", "api/tasks/", "tasks_add")
async def tasks_add(request: Request, encoder: Encoder) -> Response:
    """
    Add tasks to the queue.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object

    """
    data = await request.json()

    if not isinstance(data, list):
        return web.json_response(
            {"error": "Invalid request body expecting list with dicts."},
            status=web.HTTPBadRequest.status_code,
        )

    tasks: list = []

    ins = Tasks.get_instance()

    for item in data:
        if not isinstance(item, dict):
            return web.json_response(
                {"error": "Invalid request body expecting list with dicts."},
                status=web.HTTPBadRequest.status_code,
            )

        if not item.get("url"):
            return web.json_response({"error": "url is required.", "data": item}, status=web.HTTPBadRequest.status_code)

        if not item.get("id", None) or not validate_uuid(item.get("id"), version=4):
            item["id"] = str(uuid.uuid4())

        if not item.get("template", None):
            item["template"] = ""

        if not item.get("cli", None):
            item["cli"] = ""

        try:
            Tasks.validate(item)
        except ValueError as e:
            return web.json_response(
                {"error": f"Failed to validate task '{item.get('name', '??')}'. '{e!s}'"},
                status=web.HTTPBadRequest.status_code,
            )

        tasks.append(init_class(Task, item))

    try:
        tasks = ins.save(tasks=tasks).load().get_all()
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            {"error": "Failed to save tasks.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )

    return web.json_response(data=tasks, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/tasks/{id}/mark", "tasks_mark")
async def task_mark(request: Request, encoder: Encoder) -> Response:
    """
    Mark all items from task as downloaded.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object

    """
    task_id: str = request.match_info.get("id", None)

    if not task_id:
        return web.json_response(data={"error": "No task id."}, status=web.HTTPBadRequest.status_code)

    tasks: Tasks = Tasks.get_instance()
    try:
        task: Task | None = tasks.get(task_id)
        if not task:
            return web.json_response(
                data={"error": f"Task '{task_id}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        _status, _message = task.mark()
        if not _status:
            return web.json_response(data={"error": _message}, status=web.HTTPBadRequest.status_code)

        return web.json_response(data={"message": _message}, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)


@route("DELETE", "api/tasks/{id}/mark", "tasks_unmark")
async def task_unmark(request: Request, encoder: Encoder) -> Response:
    """
    Remove All tasks items from download archive.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object

    """
    task_id: str = request.match_info.get("id", None)

    if not task_id:
        return web.json_response(data={"error": "No task id."}, status=web.HTTPBadRequest.status_code)

    tasks: Tasks = Tasks.get_instance()
    try:
        task: Task | None = tasks.get(task_id)
        if not task:
            return web.json_response(
                data={"error": f"Task '{task_id}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        _status, _message = task.unmark()
        if not _status:
            return web.json_response(data={"error": _message}, status=web.HTTPBadRequest.status_code)

        return web.json_response(data={"message": _message}, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)
