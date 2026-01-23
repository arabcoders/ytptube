import logging
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response
from pydantic import ValidationError

from app.features.core.schemas import CEAction, CEFeature, ConfigEvent, Pagination
from app.features.core.utils import build_pagination, format_validation_errors, normalize_pagination
from app.features.tasks.definitions.repository import TaskDefinitionsRepository as Repo
from app.features.tasks.definitions.schemas import (
    TaskDefinition,
    TaskDefinitionList,
    TaskDefinitionPatch,
)
from app.features.tasks.definitions.utils import model_to_schema, schema_to_payload
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.router import route

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/tasks/definitions/", "task_definitions")
async def task_definitions_list(request: Request, encoder: Encoder, repo: Repo) -> Response:
    page, per_page = normalize_pagination(request)
    models, total, current_page, total_pages = await repo.list_paginated(page, per_page)

    include: str | None = request.query.get("include")
    summary: bool = "definition" != include

    return web.json_response(
        data=TaskDefinitionList(
            items=[model_to_schema(model, summary=summary) for model in models],
            pagination=Pagination.model_validate(build_pagination(total, current_page, per_page, total_pages)),
        ),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", r"api/tasks/definitions/{id:\d+}", "task_definitions_get")
async def task_definitions_get(request: Request, encoder: Encoder, repo: Repo) -> Response:
    identifier: str = request.match_info.get("id", "").strip()
    if not identifier:
        return web.json_response(
            data={"error": "Missing task definition identifier."},
            status=web.HTTPBadRequest.status_code,
        )

    if not (model := await repo.get(identifier)):
        return web.json_response(
            data={"error": f"Task definition '{identifier}' not found."},
            status=web.HTTPNotFound.status_code,
        )

    definition = model_to_schema(model)
    return web.json_response(data=definition, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/tasks/definitions/", "task_definitions_create")
async def task_definitions_create(request: Request, encoder: Encoder, notify: EventBus, repo: Repo) -> Response:
    try:
        payload: Any = await request.json()
    except Exception:
        return web.json_response(
            data={"error": "Invalid JSON in request body."},
            status=web.HTTPBadRequest.status_code,
        )

    if not isinstance(payload, dict):
        return web.json_response(
            data={"error": "Invalid request body; expected JSON object."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        definition_input = TaskDefinition.model_validate(payload)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate task definition.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        repo_payload = schema_to_payload(definition_input)
        model = await repo.create(repo_payload)
        definition = model_to_schema(model)

        notify.emit(
            Events.CONFIG_UPDATE,
            data=ConfigEvent(feature=CEFeature.TASKS_DEFINITIONS, action=CEAction.CREATE, data=definition.model_dump()),
        )
        return web.json_response(data=definition, status=web.HTTPCreated.status_code, dumps=encoder.encode)
    except ValueError as exc:
        return web.json_response(data={"error": str(exc)}, status=web.HTTPBadRequest.status_code)
    except Exception as exc:
        LOG.exception(exc)
        return web.json_response(
            data={"error": "Failed to create task definition."},
            status=web.HTTPInternalServerError.status_code,
        )


@route("PUT", r"api/tasks/definitions/{id:\d+}", "task_definitions_update")
async def task_definitions_update(request: Request, encoder: Encoder, notify: EventBus, repo: Repo) -> Response:
    if not (identifier := request.match_info.get("id", "").strip()):
        return web.json_response(
            data={"error": "Missing task definition identifier."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        payload: dict | None = await request.json()
    except Exception:
        return web.json_response(
            data={"error": "Invalid JSON in request body."},
            status=web.HTTPBadRequest.status_code,
        )

    if not isinstance(payload, dict):
        return web.json_response(
            data={"error": "Invalid request body; expected JSON object."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        definition_input: TaskDefinition = TaskDefinition.model_validate(payload)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate task definition.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        definition: TaskDefinition = model_to_schema(await repo.update(identifier, schema_to_payload(definition_input)))
        notify.emit(
            Events.CONFIG_UPDATE,
            data=ConfigEvent(feature=CEFeature.TASKS_DEFINITIONS, action=CEAction.UPDATE, data=definition.model_dump()),
        )
        return web.json_response(data=definition, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except KeyError as exc:
        return web.json_response(data={"error": str(exc)}, status=web.HTTPNotFound.status_code)
    except ValueError as exc:
        return web.json_response(data={"error": str(exc)}, status=web.HTTPBadRequest.status_code)
    except Exception as exc:
        LOG.exception(exc)
        return web.json_response(
            data={"error": "Failed to update task definition."},
            status=web.HTTPInternalServerError.status_code,
        )


@route("PATCH", r"api/tasks/definitions/{id:\d+}", "task_definitions_patch")
async def task_definitions_patch(request: Request, encoder: Encoder, notify: EventBus, repo: Repo) -> Response:
    if not (identifier := request.match_info.get("id", "").strip()):
        return web.json_response(
            data={"error": "Missing task definition identifier."},
            status=web.HTTPBadRequest.status_code,
        )

    if not await repo.get(identifier):
        return web.json_response(
            data={"error": f"Task definition '{identifier}' not found."},
            status=web.HTTPNotFound.status_code,
        )

    try:
        payload: dict | None = await request.json()
    except Exception:
        return web.json_response(
            data={"error": "Invalid JSON in request body."},
            status=web.HTTPBadRequest.status_code,
        )

    if not isinstance(payload, dict):
        return web.json_response(
            data={"error": "Invalid request body; expected JSON object."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        patch_input: TaskDefinitionPatch = TaskDefinitionPatch.model_validate(payload)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate task definition patch.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        definition: TaskDefinition = model_to_schema(
            await repo.update(identifier, patch_input.model_dump(exclude_unset=True))
        )

        notify.emit(
            Events.CONFIG_UPDATE,
            data=ConfigEvent(feature=CEFeature.TASKS_DEFINITIONS, action=CEAction.UPDATE, data=definition.model_dump()),
        )
        return web.json_response(data=definition, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except KeyError as exc:
        return web.json_response(data={"error": str(exc)}, status=web.HTTPNotFound.status_code)
    except ValueError as exc:
        return web.json_response(data={"error": str(exc)}, status=web.HTTPBadRequest.status_code)
    except Exception as exc:
        LOG.exception(exc)
        return web.json_response(
            data={"error": "Failed to patch task definition."},
            status=web.HTTPInternalServerError.status_code,
        )


@route("DELETE", r"api/tasks/definitions/{id:\d+}", "task_definitions_delete")
async def task_definitions_delete(request: Request, encoder: Encoder, notify: EventBus, repo: Repo) -> Response:
    if not (identifier := request.match_info.get("id", "").strip()):
        return web.json_response(
            data={"error": "Missing task definition identifier."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        definition: TaskDefinition = model_to_schema(await repo.delete(identifier))

        notify.emit(
            Events.CONFIG_UPDATE,
            data=ConfigEvent(feature=CEFeature.TASKS_DEFINITIONS, action=CEAction.DELETE, data=definition.model_dump()),
        )
        return web.json_response(data=definition, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except KeyError as exc:
        return web.json_response(data={"error": str(exc)}, status=web.HTTPNotFound.status_code)
    except Exception as exc:
        LOG.exception(exc)
        return web.json_response(
            data={"error": "Failed to delete task definition."},
            status=web.HTTPInternalServerError.status_code,
        )
