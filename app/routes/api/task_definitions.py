import logging
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.encoder import Encoder
from app.library.router import route
from app.library.TaskDefinitions import TaskDefinitionRecord, TaskDefinitions

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/task_definitions/", "task_definitions")
async def task_definitions_list(request: Request, encoder: Encoder, task_definitions: TaskDefinitions) -> Response:
    include: str | None = request.query.get("include")
    include_definition: bool = "definition" == include

    return web.json_response(
        data=[item.serialize(include_definition=include_definition) for item in task_definitions.list()],
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/task_definitions/{identifier}", "task_definitions_get")
async def task_definitions_get(request: Request, encoder: Encoder, task_definitions: TaskDefinitions) -> Response:
    identifier: str = request.match_info.get("identifier", "").strip()
    if not identifier:
        return web.json_response(
            data={"error": "Missing task definition identifier."},
            status=web.HTTPBadRequest.status_code,
        )

    record: TaskDefinitionRecord | None = task_definitions.get(identifier)
    if not record:
        return web.json_response(
            data={"error": f"Task definition '{identifier}' not found."},
            status=web.HTTPNotFound.status_code,
        )

    return web.json_response(
        data=record.serialize(include_definition=True),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/task_definitions/", "task_definitions_create")
async def task_definitions_create(request: Request, encoder: Encoder, task_definitions: TaskDefinitions) -> Response:
    try:
        payload: Any = await request.json()
        if not isinstance(payload, dict):
            return web.json_response(
                data={"error": "Invalid request body; expected JSON object."},
                status=web.HTTPBadRequest.status_code,
            )

        if "definition" in payload:
            if not isinstance(payload["definition"], dict):
                return web.json_response(
                    data={"error": "definition must be a JSON object when provided."},
                    status=web.HTTPBadRequest.status_code,
                )
            payload = payload["definition"]

        record: TaskDefinitionRecord = task_definitions.create(payload)
    except (ValueError, TypeError) as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": "Failed to create task definition."},
            status=web.HTTPInternalServerError.status_code,
        )

    return web.json_response(
        data=record.serialize(include_definition=True),
        status=web.HTTPCreated.status_code,
        dumps=encoder.encode,
    )


@route("PUT", "api/task_definitions/{identifier}", "task_definitions_update")
async def task_definitions_update(request: Request, encoder: Encoder, task_definitions: TaskDefinitions) -> Response:
    identifier: str = request.match_info.get("identifier", "").strip()
    if not identifier:
        return web.json_response(
            data={"error": "Missing task definition identifier."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        payload: Any = await request.json()
        if not isinstance(payload, dict):
            return web.json_response(
                data={"error": "Invalid request body; expected JSON object."},
                status=web.HTTPBadRequest.status_code,
            )

        if "definition" in payload:
            if not isinstance(payload["definition"], dict):
                return web.json_response(
                    data={"error": "definition must be a JSON object when provided."},
                    status=web.HTTPBadRequest.status_code,
                )
            payload = payload["definition"]

        record: TaskDefinitionRecord = task_definitions.update(identifier, payload)
    except (ValueError, TypeError) as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": "Failed to update task definition."},
            status=web.HTTPInternalServerError.status_code,
        )

    return web.json_response(
        data=record.serialize(include_definition=True),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("DELETE", "api/task_definitions/{identifier}", "task_definitions_delete")
async def task_definitions_delete(request: Request, task_definitions: TaskDefinitions) -> Response:
    identifier: str = request.match_info.get("identifier", "").strip()
    if not identifier:
        return web.json_response(
            data={"error": "Missing task definition identifier."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        task_definitions.delete(identifier)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": "Failed to delete task definition."}, status=web.HTTPInternalServerError.status_code
        )

    return web.json_response(data={"status": "deleted"}, status=web.HTTPOk.status_code)
