from __future__ import annotations

import asyncio
import json
import os
from typing import TYPE_CHECKING

from .names import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

LOG = get_logger()


def parse_jsonl_line(line: bytes | str) -> dict | None:
    raw = line.decode(errors="replace") if isinstance(line, bytes) else line
    try:
        payload = json.loads(raw.rstrip("\r\n"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or any(
        not payload.get(key) for key in ("id", "datetime", "level", "logger", "message")
    ):
        return None
    result = {key: str(payload[key]) for key in ("id", "datetime", "level", "logger")}
    result["message"] = str(payload["message"]).strip()
    result.update(
        {
            key: payload[key]
            for key in ("levelno", "source", "process", "thread", "fields", "exception")
            if key in payload
        }
    )
    return result


async def read_logfile(file: Path, offset: int = 0, limit: int = 50) -> dict:
    from anyio import open_file

    if not file.exists():
        return {"logs": [], "next_offset": None, "end_is_reached": True}
    try:
        async with await open_file(file, "rb") as stream:
            await stream.seek(0, os.SEEK_END)
            block_end = await stream.tell()
            buffer = b""
            lines: list[bytes] = []
            while len(lines) < offset + limit + 1 and block_end > 0:
                block_start = max(0, block_end - 1024)
                await stream.seek(block_start)
                buffer = await stream.read(block_end - block_start) + buffer
                lines = buffer.splitlines()
                block_end = block_start
            next_offset = offset + limit if len(lines) > offset + limit else None
            selected = lines[-(offset + limit) : -offset] if offset else lines[-limit:]
            logs = [log for line in selected if (log := parse_jsonl_line(line))]
            return {"logs": logs, "next_offset": next_offset, "end_is_reached": next_offset is None}
    except Exception:
        return {"logs": [], "next_offset": None, "end_is_reached": True}


async def tail_log(file: Path, emitter: Callable[[dict], Awaitable[None]], sleep_time: float = 0.5) -> None:
    from anyio import open_file

    if not file.exists():
        return
    try:
        async with await open_file(file, "rb") as stream:
            await stream.seek(0, os.SEEK_END)
            while True:
                line = await stream.readline()
                if not line:
                    await asyncio.sleep(sleep_time)
                    continue
                if log := parse_jsonl_line(line):
                    await emitter(log)
    except Exception:
        LOG.exception("Failed to tail log file '%s'.", file, extra={"route": "logs.stream", "file_path": str(file)})
