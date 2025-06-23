import logging
import uuid

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.encoder import Encoder
from app.library.router import route
from app.library.Tasks import Task, Tasks
from app.library.Utils import init_class, validate_uuid

LOG: logging.Logger = logging.getLogger(__name__)


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
