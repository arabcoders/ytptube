import asyncio
import json
import os
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.log import get_logger
from app.library.router import route

LOG = get_logger()


def _parse_jsonl_line(line: bytes | str) -> dict | None:
    raw: str = line.decode(errors="replace") if isinstance(line, bytes) else line
    raw = raw.rstrip("\r\n")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    required = ("id", "datetime", "level", "logger", "message")
    if any(not payload.get(key) for key in required):
        return None

    result: dict = {
        "id": str(payload["id"]),
        "datetime": str(payload["datetime"]),
        "level": str(payload["level"]),
        "logger": str(payload["logger"]),
        "message": str(payload["message"]).strip(),
    }

    for key in ("levelno", "source", "process", "thread", "fields", "exception"):
        if key not in payload:
            continue

        result[key] = payload[key]

    return result


async def _read_logfile(file: Path, offset: int = 0, limit: int = 50) -> dict:
    """
    Read a log file and return a set of log lines along with pagination metadata.

    Args:
        file (Path): The log file path.
        offset (int): Number of lines to skip from the end (newer entries).
        limit (int): Number of lines to return.

    Returns:
        dict: A dictionary containing:
            - logs: List of log entries.
            - next_offset: Offset for the next page or None.
            - end_is_reached: True if there are no older logs.

    """
    from anyio import open_file

    if not file.exists():
        return {"logs": [], "next_offset": None, "end_is_reached": True}

    result = []
    try:
        async with await open_file(file, "rb") as f:
            await f.seek(0, os.SEEK_END)
            file_size: int = await f.tell()

            block_size = 1024
            block_end: int = file_size
            buffer: bytes = b""
            lines: list = []

            required_count: int = offset + limit + 1

            while len(lines) < required_count and block_end > 0:
                block_start: int = max(0, block_end - block_size)
                await f.seek(block_start)
                chunk: bytes = await f.read(block_end - block_start)
                buffer: bytes = chunk + buffer  # prepend the chunk
                lines = buffer.splitlines()
                block_end = block_start

            if len(lines) > offset + limit:
                next_offset: int = offset + limit
                end_is_reached = False
            else:
                next_offset = None
                end_is_reached = True

            selected = lines[-(offset + limit) : -offset] if offset else lines[-limit:]
            result.extend(log for line in selected if (log := _parse_jsonl_line(line)))

            return {"logs": result, "next_offset": next_offset, "end_is_reached": end_is_reached}
    except Exception:
        return {"logs": [], "next_offset": None, "end_is_reached": True}


async def _tail_log(file: Path, emitter: callable, sleep_time: float = 0.5):
    """
    Live tail.

    Args:
        file (str): The log file path.
        emitter (callable): A callable to emit new lines.
        sleep_time (float): The time to sleep between reads.

    """
    from anyio import open_file

    if not file.exists():
        return

    try:
        async with await open_file(file, "rb") as f:
            await f.seek(0, os.SEEK_END)
            while True:
                line: bytes = await f.readline()
                if not line:
                    await asyncio.sleep(sleep_time)
                    continue

                if log := _parse_jsonl_line(line):
                    await emitter(log)
    except Exception:
        LOG.exception("Failed to tail log file '%s'.", file, extra={"route": "logs.stream", "file_path": str(file)})
        return


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

    logs_data = await _read_logfile(
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


@route("GET", "api/logs/stream", "logs.stream")
async def stream_logs(request: Request, config: Config, encoder: Encoder) -> Response | web.StreamResponse:
    if not config.file_logging:
        return web.json_response(
            data={"error": "File logging is not enabled."},
            status=web.HTTPNotFound.status_code,
        )

    log_file = Path(config.config_path) / "logs" / "app.jsonl"
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

    from app.features.core.utils import gen_random

    log_task: asyncio.Task[None] = asyncio.create_task(
        _tail_log(file=log_file, emitter=emit_log),
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
