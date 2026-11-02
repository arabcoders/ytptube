from __future__ import annotations

import json
from typing import get_args

from aiohttp import web
from pydantic import ValidationError

from app.features.core.utils import api_error_response, build_pagination, format_validation_errors, normalize_pagination
from app.features.toolbox.schemas import Status, Submission
from app.features.toolbox.service import Toolbox, ToolboxError
from app.library.router import route


def failure(exc: ToolboxError) -> web.Response:
    return api_error_response(str(exc), code=exc.code, status=exc.status, params=exc.params)


@route("GET", "api/toolbox/tools/", "toolbox_tools")
async def tools_list(toolbox: Toolbox) -> web.Response:
    return web.json_response({"items": toolbox.tools()})


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
