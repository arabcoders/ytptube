from __future__ import annotations

import asyncio
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING
from uuid import uuid4

from app.features.streaming import utils as process
from app.features.toolbox.definitions import INPUT, OUTPUT
from app.features.toolbox.schemas import Result
from app.library.Events import EventBus
from app.library.Services import Services

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pydantic import BaseModel

    from app.features.toolbox.definitions import Definition
    from app.features.toolbox.service import Context


async def publish(ctx: Context, temporary: Path, final: Path) -> None:
    from app.features.toolbox.service import SHUTDOWN_TIMEOUT

    ctx.check_source()
    if final != ctx.source and final.exists():
        msg = "The output name already exists."
        raise ValueError(msg)

    mode = stat.S_IMODE(ctx.source.stat().st_mode)
    if ctx.tool.post:
        await ctx.tool.post(ctx, temporary)
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
    supports_overwrite: bool = False

    def reason(self) -> str | None:
        return self.availability() if self.availability else None


def configured(spec: Definition, config_dir: Path) -> Tool:
    command, *args = spec.command

    def binary() -> str | None:
        path = Path(command)
        if command.startswith("./") or (os.name == "nt" and command.startswith(".\\")):
            path = config_dir / path
        elif not path.is_absolute() and command != path.name:
            return None
        found = which(path)
        if found is None or (os.name == "nt" and Path(found).suffix.lower() in (".bat", ".cmd")):
            return None
        return str(Path(found).absolute())

    def reason() -> str | None:
        return None if binary() else "The configured executable is unavailable."

    async def execute(ctx: Context) -> Result:
        if (executable := binary()) is None:
            msg = "The configured executable is unavailable."
            raise ValueError(msg)

        folder = ctx.workspace()
        output = folder / f"output{spec.output_extension}"
        values = {
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in ctx.job.extra.options.items()
        }
        env = {**spec.env, **values, INPUT: str(ctx.source), OUTPUT: str(output)}
        if os.name == "nt":
            env = {key.upper(): value for key, value in env.items()}
        substitutions = {
            "{input}": str(ctx.source),
            "{output}": str(output),
            **{f"{{param.{key}}}": value for key, value in values.items()},
        }

        await ctx.run(executable, [substitutions.get(arg, arg) for arg in args], env={**os.environ, **env}, cwd=folder)
        final = ctx.destination(spec.output_extension)
        await publish(ctx, output, final)
        return Result(outputs=[final.relative_to(ctx.root).as_posix()])

    return Tool(
        name=spec.name,
        description=spec.description,
        options=spec.options(),
        execute=execute,
        availability=reason,
        supports_overwrite=spec.supports_overwrite,
    )
