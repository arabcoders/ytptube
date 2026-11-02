from __future__ import annotations

import asyncio
import math
import shutil
import stat
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from app.features.streaming import utils as process
from app.features.streaming.library.ffprobe import ffmpeg_bin, ffprobe
from app.features.streaming.types import FFProbeError
from app.features.toolbox.schemas import RemuxOptions, Result
from app.library.Events import EventBus
from app.library.Services import Services

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from pydantic import BaseModel

    from app.features.toolbox.service import Context


async def remux(ctx: Context) -> Result:
    duration = None
    try:
        seconds = float((await ffprobe(ctx.source)).metadata.get("duration", 0))
        if math.isfinite(seconds) and seconds > 0:
            duration = seconds
    except (FFProbeError, OSError, ValueError, TypeError):
        pass
    folder = ctx.workspace()
    temporary = folder / "output.part.mp4"
    binary = ffmpeg_bin()
    if binary is None:
        msg = "ffmpeg is unavailable."
        raise ValueError(msg)
    await ctx.run(
        binary,
        [
            "-nostdin",
            "-n",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            str(ctx.source),
            "-map",
            "0",
            "-c",
            "copy",
            "-map_metadata",
            "0",
            "-map_chapters",
            "0",
            "-movflags",
            "+faststart",
            str(temporary),
        ],
        duration,
    )
    final = ctx.destination(".mp4", ".remux")
    await publish(ctx, temporary, final)
    return Result(outputs=[final.relative_to(ctx.root).as_posix()])


async def publish(ctx: Context, temporary: Path, final: Path) -> None:
    from app.features.toolbox.service import SHUTDOWN_TIMEOUT

    ctx.check_source()
    if final != ctx.source and final.exists():
        msg = "The output name already exists."
        raise ValueError(msg)

    mode = stat.S_IMODE(ctx.source.stat().st_mode)
    if post := TOOLS[ctx.job.tool].post:
        await post(ctx, temporary)
    queue = Services.get_instance().get("queue")
    history = (
        await queue.done.get_by_file(ctx.source, ctx.root)
        if queue is not None and ctx.job.extra.overwrite_source and final != ctx.source
        else []
    )
    stage = final.parent / f".{uuid4().hex}.part"
    try:
        move = asyncio.create_task(asyncio.to_thread(shutil.move, temporary, stage))
        try:
            await asyncio.shield(move)
        except asyncio.CancelledError as exc:
            # Cancelling the await cannot stop the thread; cleanup must wait for its move.
            try:
                await process.settle(move)
            finally:
                raise exc
        stage.chmod(mode)
        stage.replace(final)
        if ctx.job.extra.overwrite_source:
            if final != ctx.source:
                ctx.source.unlink()
            ctx.source = final
        if history and queue is not None:
            await process.settle(
                asyncio.create_task(
                    asyncio.wait_for(
                        queue.done.update_file(history, final, ctx.root, EventBus.get_instance()),
                        timeout=SHUTDOWN_TIMEOUT,
                    )
                )
            )
    finally:
        stage.unlink(missing_ok=True)


@dataclass(frozen=True, kw_only=True)
class Tool:
    name: str
    description: str
    options: type[BaseModel]
    execute: Callable[[Context], Awaitable[Result]]
    availability: Callable[[], str | None] | None = None
    pre: Callable[[Context], Awaitable[str | None]] | None = None
    post: Callable[[Context, Path], Awaitable[None]] | None = None

    def reason(self) -> str | None:
        return self.availability() if self.availability else None


TOOLS = {
    "remux": Tool(
        name="Remux into MP4",
        description="Copy streams into MP4 without re-encoding.",
        options=RemuxOptions,
        execute=remux,
        availability=lambda: None if ffmpeg_bin() else "ffmpeg is unavailable.",
    ),
}
