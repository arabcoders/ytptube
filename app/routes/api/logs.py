import asyncio
import logging
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.router import route
from app.library.Utils import read_logfile, tail_log

LOG: logging.Logger = logging.getLogger(__name__)


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
        return web.json_response(data={"error": "File logging is not enabled."}, status=web.HTTPNotFound.status_code)

    offset = int(request.query.get("offset", 0))
    limit = int(request.query.get("limit", 100))
    if limit < 1 or limit > 150:
        limit = 50

    logs_data = await read_logfile(
        file=Path(config.config_path) / "logs" / "app.log",
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


@route("GET", "api/logs/stream", "logs.stream")
async def stream_logs(request: Request, config: Config, encoder: Encoder) -> Response | web.StreamResponse:
    if not config.file_logging:
        return web.json_response(
            data={"error": "File logging is not enabled."},
            status=web.HTTPNotFound.status_code,
        )

    log_file = Path(config.config_path) / "logs" / "app.log"
    if not log_file.exists():
        return web.json_response(
            data={"error": "Log file is not available."},
            status=web.HTTPNotFound.status_code,
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

    log_task: asyncio.Task[None] = asyncio.create_task(tail_log(file=log_file, emitter=emit_log), name="log_stream")

    try:
        LOG.debug("Log streaming connected.")
        while not log_task.done():
            await asyncio.sleep(0.5)
            if request.transport is None or request.transport.is_closing():
                log_task.cancel()
                break
        await log_task
    except asyncio.CancelledError:
        pass
    finally:
        LOG.debug("Log streaming disconnected.")
        try:
            await response.write_eof()
        except ConnectionResetError:
            pass

    return response
