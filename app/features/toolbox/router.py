from __future__ import annotations

import json
from typing import get_args

from aiohttp import web
from pydantic import ValidationError

from app.features.core.utils import api_error_response, build_pagination, format_validation_errors, normalize_pagination
from app.features.toolbox.definitions import Definition
from app.features.toolbox.schemas import Status, Submission
from app.features.toolbox.service import Toolbox, ToolboxError
from app.library.router import route


def failure(exc: ToolboxError) -> web.Response:
    return api_error_response(str(exc), code=exc.code, status=exc.status, params=exc.params)


@route("GET", "api/toolbox/tools/", "toolbox_tools")
async def tools_list(toolbox: Toolbox) -> web.Response:
    return web.json_response({"items": await toolbox.tools()}, headers={"Cache-Control": "no-store"})


@route("GET", "api/toolbox/definitions/", "toolbox_definitions", auth_only=True)
async def definitions_list(request: web.Request, toolbox: Toolbox) -> web.Response:
    try:
        page, per_page = normalize_pagination(request)
    except ValueError as exc:
        return api_error_response(str(exc), code="INVALID_PAGINATION", status=400)
    definitions, total, page, pages = await toolbox.definitions.list_paginated(
        page, per_page, include_defaults=request.query.get("include_defaults") == "true"
    )
    items = [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "default": item.default,
        }
        for item in definitions
    ]
    return web.json_response(
        {"items": items, "pagination": build_pagination(total, page, per_page, pages)},
        headers={"Cache-Control": "no-store"},
    )


def missing_definition() -> web.Response:
    return api_error_response("Toolbox tool not found.", code="NOT_FOUND", status=404)


@route("GET", r"api/toolbox/definitions/{id:\d+}/", "toolbox_definition", auth_only=True)
async def definitions_get(request: web.Request, toolbox: Toolbox) -> web.Response:
    try:
        item = await toolbox.definitions.get(int(request.match_info["id"]))
    except (ValueError, OverflowError):
        return api_error_response("Invalid Toolbox tool ID.", code="INVALID", status=400)
    if item is None:
        return missing_definition()
    return web.json_response(item.model_dump(mode="json"), headers={"Cache-Control": "no-store"})


async def save_definition(request: web.Request, toolbox: Toolbox, identifier: str | None = None) -> web.Response:
    try:
        definition = Definition.model_validate(await request.json())
        if identifier is None:
            item = await toolbox.definitions.create(definition)
        else:
            item = await toolbox.definitions.replace(int(identifier), definition)
    except json.JSONDecodeError:
        return api_error_response("Invalid JSON body.", code="BAD_REQUEST", status=400)
    except ValidationError as exc:
        return api_error_response(
            "Invalid Toolbox tool.", code="VALIDATION_FAILED", status=400, detail=format_validation_errors(exc)
        )
    except OverflowError:
        return api_error_response("Invalid Toolbox tool ID.", code="INVALID", status=400)
    except ValueError as exc:
        return api_error_response(str(exc), code="CONFLICT", status=409)
    if item is None:
        return missing_definition()
    return web.json_response(item.model_dump(mode="json"), status=201 if identifier is None else 200)


@route("POST", "api/toolbox/definitions/", "toolbox_definition_add", auth_only=True)
async def definitions_add(request: web.Request, toolbox: Toolbox) -> web.Response:
    return await save_definition(request, toolbox)


@route("PUT", r"api/toolbox/definitions/{id:\d+}/", "toolbox_definition_replace", auth_only=True)
async def definitions_replace(request: web.Request, toolbox: Toolbox) -> web.Response:
    return await save_definition(request, toolbox, request.match_info["id"])


@route("DELETE", r"api/toolbox/definitions/{id:\d+}/", "toolbox_definition_delete", auth_only=True)
async def definitions_delete(request: web.Request, toolbox: Toolbox) -> web.Response:
    try:
        if not await toolbox.definitions.delete(int(request.match_info["id"])):
            return missing_definition()
    except OverflowError:
        return api_error_response("Invalid Toolbox tool ID.", code="INVALID", status=400)
    except ValueError as exc:
        return api_error_response(str(exc), code="CONFLICT", status=409)
    return web.Response(status=204)


@route("POST", "api/toolbox/jobs/", "toolbox_submit")
async def jobs_submit(request: web.Request, toolbox: Toolbox) -> web.Response:
    try:
        data = Submission.model_validate(await request.json())
        job = await toolbox.submit(data)
    except ValidationError as exc:
        return api_error_response(
            "Invalid toolbox job.", code="VALIDATION_FAILED", status=400, detail=format_validation_errors(exc)
        )
    except json.JSONDecodeError:
        return api_error_response("Invalid JSON body.", code="BAD_REQUEST", status=400)
    except ToolboxError as exc:
        return failure(exc)
    return web.json_response(job.model_dump(mode="json"), status=202)


@route("GET", "api/toolbox/jobs/", "toolbox_jobs")
async def jobs_list(request: web.Request, toolbox: Toolbox) -> web.Response:
    try:
        page, per_page = normalize_pagination(request)
        status = request.query.get("status")
        if status is not None and status not in get_args(Status):
            return api_error_response(
                "Invalid toolbox job status.", code="INVALID", status=400, params={"field": "api.fields.status"}
            )
        jobs, total, page, pages = await toolbox.repo.list_paginated(page, per_page, status)
    except ValueError as exc:
        return api_error_response(str(exc), code="INVALID_PAGINATION", status=400)
    live = {ctx.job.id: ctx.job for ctx in ([toolbox.active] if toolbox.active else []) + list(toolbox.pending)}
    items = [live.get(job.id, job).model_dump(mode="json") for job in jobs]
    return web.json_response({"items": items, "pagination": build_pagination(total, page, per_page, pages)})


@route("GET", r"api/toolbox/jobs/{id:\d+}/", "toolbox_job")
async def jobs_get(request: web.Request, toolbox: Toolbox) -> web.Response:
    try:
        job = await toolbox.get(int(request.match_info["id"]))
    except ToolboxError as exc:
        return failure(exc)
    except (ValueError, OverflowError):
        return api_error_response("Invalid toolbox job ID.", code="INVALID", status=400)
    return web.json_response(job.model_dump(mode="json"))


@route("POST", r"api/toolbox/jobs/{id:\d+}/cancel/", "toolbox_cancel")
async def jobs_cancel(request: web.Request, toolbox: Toolbox) -> web.Response:
    try:
        job = await toolbox.cancel(int(request.match_info["id"]))
    except ToolboxError as exc:
        return failure(exc)
    except (ValueError, OverflowError):
        return api_error_response("Invalid toolbox job ID.", code="INVALID", status=400)
    return web.json_response(job.model_dump(mode="json"))


@route("DELETE", r"api/toolbox/jobs/{id:\d+}/", "toolbox_delete")
async def jobs_delete(request: web.Request, toolbox: Toolbox) -> web.Response:
    try:
        await toolbox.delete(int(request.match_info["id"]))
    except ToolboxError as exc:
        return failure(exc)
    except (ValueError, OverflowError):
        return api_error_response("Invalid toolbox job ID.", code="INVALID", status=400)
    return web.Response(status=204)
