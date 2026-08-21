import asyncio
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response

from app.features.core.utils import api_error_response
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.logging import (
    SUPPORTED_LOG_LEVELS,
    get_runtime_log_level,
    normalize_log_level,
    read_logfile,
    set_runtime_log_level,
    tail_log,
)
from app.library.router import route


@route("GET", "api/logs/", "logs")
async def logs(request: Request, config: Config, encoder: Encoder) -> Response:
    """
    Get recent logs

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    if not config.file_logging:
        return api_error_response(
            "File logging is not enabled.",
            code="FEATURE_DISABLED",
            status=web.HTTPNotFound.status_code,
            params={"feature": "api.features.fileLogging"},
        )

    offset = int(request.query.get("offset", 0))
    limit = int(request.query.get("limit", 100))
    if limit < 1 or limit > 150:
        limit = 50

    logs_data = await read_logfile(
        file=Path(config.config_path) / "logs" / "app.jsonl",
        offset=offset,
        limit=limit,
    )

    return web.json_response(
        data={
            "logs": logs_data["logs"],
            "offset": offset,
            "limit": limit,
            "next_offset": logs_data["next_offset"],
            "end_is_reached": logs_data["end_is_reached"],
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/logs/level", "logs.level")
async def get_logs_level(config: Config, encoder: Encoder) -> Response:
    configured = normalize_log_level(config.log_level)
    active = get_runtime_log_level()
    return web.json_response(
        data={
            "conf": configured,
            "active": active,
            "levels": list(SUPPORTED_LOG_LEVELS),
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/logs/level/{level}", "logs.level.set")
async def set_logs_level(request: Request) -> Response:
    if not (level := request.match_info.get("level")):
        return api_error_response(
            "Log level is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.logLevel"},
        )

    try:
        set_runtime_log_level(level)
    except ValueError as e:
        return api_error_response(
            f"{e!s} Available levels: {', '.join(SUPPORTED_LOG_LEVELS)}.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    return web.Response(status=web.HTTPNoContent.status_code)


@route("GET", "api/logs/stream", "logs.stream")
async def stream_logs(request: Request, config: Config, encoder: Encoder) -> Response | web.StreamResponse:
    if not config.file_logging:
        return api_error_response(
            "File logging is not enabled.",
            code="FEATURE_DISABLED",
            status=web.HTTPNotFound.status_code,
            params={"feature": "api.features.fileLogging"},
        )

    log_file = Path(config.config_path) / "logs" / "app.jsonl"
    if not log_file.exists():
        return api_error_response(
            "Log file is not available.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.file"},
        )

    response = web.StreamResponse(
        status=web.HTTPOk.status_code,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
    await response.prepare(request)

    async def emit_log(data: dict) -> None:
        if request.transport is None or request.transport.is_closing():
            raise asyncio.CancelledError
        payload = f"event: log_lines\ndata: {encoder.encode(data)}\n\n"
        await response.write(payload.encode("utf-8"))

    from app.features.core.utils import gen_random

    log_task: asyncio.Task[None] = asyncio.create_task(
        tail_log(file=log_file, emitter=emit_log),
        name=f"log_stream_{gen_random(8)}",
    )

    try:
        while not log_task.done():
            await asyncio.sleep(1.0)
            if request.transport is None or request.transport.is_closing():
                log_task.cancel()
                break
        await log_task
    except asyncio.CancelledError:
        pass
    finally:
        try:
            await response.write_eof()
        except ConnectionResetError:
            pass

    return response
