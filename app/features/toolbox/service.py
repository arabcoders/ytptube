from __future__ import annotations

import asyncio
import errno
import logging
import re
import shutil
import tempfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.features.core.models import utcnow
from app.features.streaming import utils as process
from app.features.toolbox.repository import ToolboxRepository
from app.features.toolbox.schemas import TERMINAL, Job, Result, Status, Submission
from app.features.toolbox.tools import TOOLS
from app.library.config import Config
from app.library.Events import EventBus, Events
from app.library.Services import Services
from app.library.Utils import get_file

if TYPE_CHECKING:
    from aiohttp import web

LOG = logging.getLogger("toolbox")
QUEUE_LIMIT = 16
LOG_LIMIT = 16 * 1024
RUN_TIMEOUT = 24 * 60 * 60
SHUTDOWN_TIMEOUT = 30.0
PARTIAL = re.compile(r"(?:\.part(?:-Frag\d+)?|\.(?:ytdl|tmp|temp|download))$", re.IGNORECASE)


class ToolboxError(ValueError):
    def __init__(
        self,
        message: str,
        code: str = "TOOLBOX_ERROR",
        status: int = 400,
        params: dict[str, str | int | float | bool | None] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.status = status
        self.params = params


class SkipError(Exception):
    pass


@dataclass(kw_only=True)
class Context:
    service: Toolbox
    job: Job
    source: Path
    unsafe: bool = False
    folder: Path | None = None
    last_event: float = float("-inf")

    @property
    def root(self) -> Path:
        return Path(self.service.config.download_path).resolve()

    def check_source(self) -> None:
        source = self.service.source(self.source.relative_to(self.root).as_posix())
        if source != self.source:
            msg = "The source path changed."
            raise ToolboxError(msg, "SOURCE_CHANGED")

    def workspace(self) -> Path:
        folder = Path(tempfile.mkdtemp(prefix=f"ytp-tmp-{self.job.id}-", dir=self.service.config.temp_path))
        self.folder = folder
        return folder

    def destination(self, suffix: str, affix: str) -> Path:
        if self.job.extra.overwrite_source:
            return self.source if self.source.suffix.lower() == suffix else self.source.with_suffix(suffix)
        return self.source.with_name(f"{self.source.stem}{affix}{suffix}")

    def cleanup(self) -> None:
        if self.unsafe or self.folder is None:
            return
        try:
            shutil.rmtree(self.folder)
        except OSError:
            LOG.warning("Toolbox workspace retained for job %s.", self.job.id)

    def progress(self, value: float | None) -> None:
        self.job.progress = value
        now = asyncio.get_running_loop().time()
        if now - self.last_event >= 0.5:
            self.last_event = now
            self.service.emit(self.job)

    async def run(self, binary: str, args: list[str], duration: float | None = None) -> None:
        self.check_source()
        self.unsafe = True
        try:
            proc = await process.spawn(binary, args)
        except process.ProcessExitError:
            raise
        except BaseException:
            self.unsafe = False
            raise

        async def stdout() -> None:
            assert proc.stdout is not None
            pending = b""
            while chunk := await proc.stdout.read(4096):
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    if duration and line.startswith(b"out_time_us="):
                        try:
                            elapsed = int(line.split(b"=", 1)[1]) / 1_000_000
                        except ValueError:
                            continue
                        self.progress(min(99.0, max(0.0, elapsed / duration * 100)))
                pending = pending[-4096:]

        async def stderr() -> None:
            assert proc.stderr is not None
            tail = bytearray()
            while chunk := await proc.stderr.read(4096):
                tail.extend(chunk)
                del tail[:-LOG_LIMIT]
                self.job.log = tail.decode("utf-8", errors="replace")[-LOG_LIMIT:]

        readers = [asyncio.create_task(stdout()), asyncio.create_task(stderr())]
        try:
            async with asyncio.timeout(RUN_TIMEOUT):
                await asyncio.gather(*readers)
                code = await proc.wait()
            if code != 0:
                msg = "Operation failed. See the job log."
                raise ToolboxError(msg, "TOOL_FAILED")
        finally:

            async def cleanup() -> None:
                for reader in readers:
                    reader.cancel()
                await asyncio.wait_for(asyncio.gather(*readers, return_exceptions=True), process.CLEANUP_TIMEOUT)
                await process.release(proc)
                self.unsafe = False

            await process.settle(asyncio.create_task(cleanup()))


class Toolbox:
    def __init__(self, config: Config | None = None, repo: ToolboxRepository | None = None):
        self.config = config or Config.get_instance()
        self.repo = repo or ToolboxRepository()
        self.pending: deque[Context] = deque()
        self.active: Context | None = None
        self.execution: asyncio.Task[Result] | None = None
        self.worker: asyncio.Task[None] | None = None
        self.wake = asyncio.Event()
        self.lock = asyncio.Lock()
        self.closing = False
        self.blocked = False

    def attach(self, app: web.Application) -> None:
        Services.get_instance().add("toolbox", self)
        app.on_startup.append(self.start)
        app.on_shutdown.insert(0, self.shutdown)

    async def start(self, _: web.Application | None = None) -> None:
        from app.library.sqlite_store import SqliteStore

        await SqliteStore.get_instance().get_connection()
        await self.repo.interrupt()
        self.worker = asyncio.create_task(self.work(), name="toolbox")

    def emit(self, job: Job) -> None:
        EventBus.get_instance().emit(Events.TOOLBOX_JOB, data=job.model_dump(mode="json"))

    def tools(self) -> list[dict]:
        items = []
        for key, tool in TOOLS.items():
            reason = tool.reason()
            if self.blocked or self.closing:
                reason = "Toolbox is unavailable. Restart the server."
            items.append(
                {
                    "id": key,
                    "name": tool.name,
                    "description": tool.description,
                    "available": reason is None,
                    "reason": reason,
                    "options_schema": tool.options.model_json_schema(),
                }
            )
        return items

    def source(self, file: str) -> Path:
        path, status = get_file(self.config.download_path, file)
        if status not in (200, 302):
            msg = f"File '{file}' is no longer available."
            raise ToolboxError(msg, "FILE_UNAVAILABLE", 404, params={"file": file})
        if not path.is_file():
            msg = f"File '{file}' is not a regular file."
            raise ToolboxError(msg, "NOT_A_FILE")
        if PARTIAL.search(path.name) or Path(f"{path}.part").exists() or Path(f"{path}.ytdl").exists():
            msg = "Partial or active downloads cannot be processed."
            raise ToolboxError(msg, "ACTIVE_DOWNLOAD")
        queue = Services.get_instance().get("queue")
        if queue is not None:
            root = Path(self.config.download_path).resolve()
            for entry in queue.queue.items():
                info = entry[1].info
                for name in (info.filename, info.tmpfilename):
                    if name and (root / (info.folder or "") / name).resolve() == path:
                        msg = "Partial or active downloads cannot be processed."
                        raise ToolboxError(msg, "ACTIVE_DOWNLOAD")
        return path

    async def submit(self, data: Submission) -> Job:
        async with self.lock:
            if self.closing or self.blocked or self.worker is None or self.worker.done():
                msg = "Toolbox is unavailable."
                raise ToolboxError(msg, "UNAVAILABLE", 503)
            if len(self.pending) >= QUEUE_LIMIT:
                msg = "The Toolbox queue is full."
                raise ToolboxError(msg, "QUEUE_FULL", 429)
            if (tool := TOOLS.get(data.tool)) is None:
                msg = "Unknown Toolbox operation."
                raise ToolboxError(msg, "UNKNOWN_TOOL")
            if reason := tool.reason():
                raise ToolboxError(reason, "UNAVAILABLE", 503)
            options = tool.options.model_validate(data.extra.options).model_dump()
            source = self.source(data.file)
            job = await self.repo.create(
                {
                    "tool": data.tool,
                    "file": source.relative_to(Path(self.config.download_path).resolve()).as_posix(),
                    "extra": data.extra.model_copy(update={"options": options}).model_dump(),
                    "status": "queued",
                    "created_at": utcnow(),
                }
            )
            ctx = Context(service=self, job=job, source=source)
            self.pending.append(ctx)
            self.emit(job)
            self.wake.set()
            return job.model_copy(deep=True)

    async def get(self, identifier: int) -> Job:
        for ctx in ([self.active] if self.active else []) + list(self.pending):
            if ctx.job.id == identifier:
                return ctx.job.model_copy(deep=True)
        if job := await self.repo.get(identifier):
            return job
        msg = "Toolbox job not found."
        raise ToolboxError(msg, "JOB_NOT_FOUND", 404)

    async def cancel(self, identifier: int) -> Job:
        async with self.lock:
            job = await self.get(identifier)
            if job.status in TERMINAL:
                return job
            for ctx in self.pending:
                if ctx.job.id == identifier:
                    self.pending.remove(ctx)
                    await self.finish(ctx, "cancelled")
                    return ctx.job.model_copy(deep=True)
            if self.active and self.active.job.id == identifier and self.execution and not self.execution.done():
                self.active.job.message = "Cancelling"
                self.execution.cancel()
                self.emit(self.active.job)
                return self.active.job.model_copy(deep=True)
            return await self.get(identifier)

    async def delete(self, identifier: int) -> None:
        async with self.lock:
            if (await self.get(identifier)).status not in TERMINAL:
                msg = "Only finished jobs can be deleted."
                raise ToolboxError(msg, "CONFLICT", 409)
            await self.repo.delete(identifier)

    async def finish(self, ctx: Context, status: Status) -> None:
        job = ctx.job
        job.status = status
        job.finished_at = utcnow()
        job.progress = 100 if status == "succeeded" else None
        if status != "skipped":
            job.message = "Completed" if status == "succeeded" else status.capitalize()
        await self.repo.save(job)
        self.emit(job)

    async def work(self) -> None:
        while not self.closing and not self.blocked:
            await self.wake.wait()
            async with self.lock:
                if not self.pending:
                    self.wake.clear()
                    continue
                ctx = self.pending.popleft()
                self.active = ctx
                ctx.job.status = "running"
                ctx.job.message = "Running"
                ctx.job.started_at = utcnow()
                await self.repo.save(ctx.job)
                self.emit(ctx.job)
                self.execution = asyncio.create_task(self.execute(ctx), name=f"toolbox-{ctx.job.id}")
            status: Status = "succeeded"
            try:
                ctx.job.result = await self.execution
            except SkipError as exc:
                status = "skipped"
                ctx.job.message = str(exc)
            except asyncio.CancelledError:
                status = "interrupted" if self.closing else "cancelled"
            except process.ProcessExitError:
                ctx.unsafe = True
                self.blocked = True
                status = "interrupted"
                ctx.job.error = "Could not confirm the process stopped. Restart the server."
                ctx.job.error_code = "PROCESS_EXIT_UNCONFIRMED"
                LOG.exception("Toolbox child ownership unresolved for %s.", ctx.job.id)
            except OSError as exc:
                status = "failed"
                if exc.errno == errno.ENOSPC:
                    ctx.job.error = "Not enough disk space."
                    ctx.job.error_code = "DISK_FULL"
                else:
                    ctx.job.error = "File operation failed. See the server log."
                    ctx.job.error_code = "FILE_FAILED"
                LOG.exception("Toolbox file operation failed for %s.", ctx.job.id)
            except Exception as exc:
                status = "failed"
                ctx.job.error = str(exc) if isinstance(exc, ValueError) else "Operation failed. See the server log."
                ctx.job.error_code = exc.code if isinstance(exc, ToolboxError) else "TOOL_FAILED"
                LOG.exception("Toolbox job %s failed.", ctx.job.id)
            if ctx.unsafe:
                self.blocked = True
                status = "interrupted"
                ctx.job.error = "Could not confirm the process stopped. Restart the server."
                ctx.job.error_code = "PROCESS_EXIT_UNCONFIRMED"
            ctx.cleanup()
            async with self.lock:
                await self.finish(ctx, status)
                self.active = None
                self.execution = None

    async def execute(self, ctx: Context) -> Result:
        tool = TOOLS[ctx.job.tool]
        if reason := tool.reason():
            raise ToolboxError(reason, "UNAVAILABLE")
        ctx.check_source()
        if tool.pre and (reason := await tool.pre(ctx)):
            raise SkipError(reason)
        return await tool.execute(ctx)

    async def shutdown(self, _: web.Application | None = None) -> None:
        async with self.lock:
            self.closing = True
            self.wake.set()
            if self.execution and not self.execution.done():
                self.execution.cancel()
            while self.pending:
                await self.finish(self.pending.popleft(), "interrupted")
        if self.worker is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self.worker), SHUTDOWN_TIMEOUT)
            except TimeoutError:
                LOG.error("Toolbox shutdown timed out; live child workspace retained.")
