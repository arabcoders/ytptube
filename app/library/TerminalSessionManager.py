from __future__ import annotations

import asyncio
import errno
import json
import logging
import os
import shlex
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiohttp import web

from app.library.config import Config
from app.library.Services import Services
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from asyncio.events import AbstractEventLoop
    from asyncio.subprocess import Process

    from aiohttp.web import Request

LOG: logging.Logger = logging.getLogger("terminal_manager")

ACTIVE_FILE_NAME = "active.json"
METADATA_FILE_NAME = "metadata.json"
TRANSCRIPT_FILE_NAME = "transcript.jsonl"
DEFAULT_DRAIN_TTL = 30.0
DEFAULT_KEEPALIVE_INTERVAL = 15.0
DEFAULT_SHUTDOWN_TIMEOUT = 5.0


class TerminalSessionConflictError(RuntimeError):
    pass


@dataclass(slots=True)
class ActiveTerminalSession:
    session_id: str
    task: asyncio.Task[None]
    process: Process | None = None
    subscribers: set[asyncio.Queue[dict[str, Any] | None]] = field(default_factory=set)
    interrupted: bool = False


class TerminalSessionManager(metaclass=Singleton):
    def __init__(self) -> None:
        self.config: Config = Config.get_instance()
        self.root_path: Path = Path(self.config.config_path) / "runtime" / "terminal"
        self._lock = asyncio.Lock()
        self._active: ActiveTerminalSession | None = None
        self._drain_ttl: float = DEFAULT_DRAIN_TTL
        self._keepalive_interval: float = DEFAULT_KEEPALIVE_INTERVAL
        self._shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT

    @staticmethod
    def get_instance() -> TerminalSessionManager:
        return TerminalSessionManager()

    def attach(self, app: web.Application) -> None:
        self._ensure_root()
        Services.get_instance().add("terminal_manager", self)
        app.on_startup.append(self.on_startup)
        app.on_shutdown.append(self.on_shutdown)

    async def on_startup(self, _: web.Application) -> None:
        await self.initialize()

    async def on_shutdown(self, _: web.Application) -> None:
        session_id: str | None = None
        task: asyncio.Task[None] | None = None

        async with self._lock:
            runtime = self._active
            if runtime is None:
                return

            runtime.interrupted = True
            session_id = runtime.session_id
            task = runtime.task

            self._signal_process(runtime.process)
            if runtime.process is None and task.done() is False:
                task.cancel()

            for subscriber in list(runtime.subscribers):
                subscriber.put_nowait(None)

        assert session_id is not None
        assert task is not None

        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=self._shutdown_timeout)
            return
        except TimeoutError:
            async with self._lock:
                runtime = self._active
                if runtime is not None and runtime.session_id == session_id:
                    self._signal_process(runtime.process, force=True)
                    if task.done() is False:
                        task.cancel()

            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=self._shutdown_timeout)
                return
            except TimeoutError:
                LOG.warning("Terminal session '%s' did not finish during shutdown.", session_id)

        await self._force_interrupt_session(session_id)

    async def initialize(self) -> None:
        async with self._lock:
            self._ensure_root()
            self._cleanup_expired_sessions(time.time())
            self._recover_orphaned_active_session(time.time())

    async def cleanup(self) -> None:
        async with self._lock:
            self._cleanup_expired_sessions(time.time())

    async def create_session(self, command: str) -> dict[str, Any]:
        async with self._lock:
            now = time.time()
            self._cleanup_expired_sessions(now)

            active_session = self._get_active_session_locked()
            if active_session is not None:
                msg = "A terminal session is already active."
                raise TerminalSessionConflictError(msg)

            session_id = uuid.uuid4().hex
            session_dir = self._session_dir(session_id)
            session_dir.mkdir(parents=True, exist_ok=True)

            metadata = {
                "session_id": session_id,
                "command": command,
                "status": "starting",
                "created_at": now,
                "started_at": now,
                "finished_at": None,
                "expires_at": None,
                "exit_code": None,
                "last_sequence": 0,
            }
            self._write_json(self._metadata_path(session_id), metadata)
            self._transcript_path(session_id).touch(exist_ok=True)
            self._set_active_marker(session_id)

            task = asyncio.create_task(
                self._run_session(session_id=session_id, command=command), name=f"terminal_{session_id}"
            )
            self._active = ActiveTerminalSession(session_id=session_id, task=task)
            return dict(metadata)

    async def get_active_session(self) -> dict[str, Any] | None:
        async with self._lock:
            self._cleanup_expired_sessions(time.time())
            metadata = self._get_active_session_locked()
            return None if metadata is None else dict(metadata)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        async with self._lock:
            self._cleanup_expired_sessions(time.time())
            metadata = self._load_metadata(session_id)
            return None if metadata is None else dict(metadata)

    async def cancel_session(self, session_id: str) -> dict[str, Any]:
        async with self._lock:
            self._cleanup_expired_sessions(time.time())

            metadata = self._load_metadata(session_id)
            if metadata is None:
                msg = f"Unknown terminal session '{session_id}'."
                raise FileNotFoundError(msg)

            runtime = self._active
            if runtime is None or runtime.session_id != session_id:
                msg = "Terminal session is not active."
                raise RuntimeError(msg)

            runtime.interrupted = True
            self._signal_process(runtime.process)
            if runtime.process is None and runtime.task.done() is False:
                runtime.task.cancel()

            return dict(metadata)

    async def stream_session(self, session_id: str, request: Request) -> web.StreamResponse:
        since = self._parse_since(request)

        response = web.StreamResponse(
            status=web.HTTPOk.status_code,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)

        queue: asyncio.Queue[dict[str, Any] | None] | None = None
        last_sent = since

        try:
            replay_events = self._read_transcript(session_id=session_id, since=since)
            for event in replay_events:
                if await self._emit_sse(request=request, response=response, event=event) is False:
                    return response
                last_sent = event["seq"]

            replay_until = last_sent
            async with self._lock:
                metadata = self._load_metadata(session_id)
                if metadata is not None:
                    replay_until = int(metadata.get("last_sequence", last_sent))

                runtime = self._active
                if runtime is not None and runtime.session_id == session_id:
                    queue = asyncio.Queue()
                    runtime.subscribers.add(queue)

            if replay_until > last_sent:
                replay_events = self._read_transcript(session_id=session_id, since=last_sent, until=replay_until)
                for event in replay_events:
                    if await self._emit_sse(request=request, response=response, event=event) is False:
                        return response
                    last_sent = event["seq"]

            if queue is None:
                return response

            while True:
                if self._is_request_disconnected(request):
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=self._keepalive_interval)
                except TimeoutError:
                    if await self._emit_keepalive(request=request, response=response) is False:
                        break
                    continue

                if event is None:
                    break

                if event["seq"] <= last_sent:
                    continue

                if await self._emit_sse(request=request, response=response, event=event) is False:
                    break
                last_sent = event["seq"]
        finally:
            if queue is not None:
                async with self._lock:
                    if self._active is not None and self._active.session_id == session_id:
                        self._active.subscribers.discard(queue)

            try:
                await response.write_eof()
            except ConnectionResetError:
                pass

        return response

    async def _run_session(self, session_id: str, command: str) -> None:
        return_code = -1
        final_status = "completed"
        proc: Process | None = None
        read_task: asyncio.Task[None] | None = None
        master_fd: int | None = None

        try:
            LOG.info("Cli command from client. '%s'", command)
            args = ["yt-dlp", *shlex.split(command, posix=os.name != "nt")]
            env_vars = self._build_env()

            pty_handles = self._open_pty()
            if pty_handles is None:
                stdin_arg = asyncio.subprocess.DEVNULL
                stdout_arg = asyncio.subprocess.PIPE
                stderr_arg = asyncio.subprocess.STDOUT
                use_pty = False
                slave_fd = None
            else:
                master_fd, slave_fd = pty_handles
                stdin_arg = asyncio.subprocess.DEVNULL
                stdout_arg = slave_fd
                stderr_arg = slave_fd
                use_pty = True

            creationflags = 0
            if os.name == "nt":
                import subprocess

                creationflags = subprocess.CREATE_NO_WINDOW

            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=self.config.download_path,
                stdin=stdin_arg,
                stdout=stdout_arg,
                stderr=stderr_arg,
                env=env_vars,
                creationflags=creationflags,
            )

            async with self._lock:
                metadata = self._load_metadata(session_id)
                if metadata is not None:
                    metadata["status"] = "running"
                    self._write_json(self._metadata_path(session_id), metadata)

                if self._active is not None and self._active.session_id == session_id:
                    self._active.process = proc

            if use_pty is True and slave_fd is not None:
                try:
                    os.close(slave_fd)
                except Exception as exc:
                    LOG.error("Error closing PTY. '%s'.", str(exc))

            read_task = asyncio.create_task(
                self._read_process_output(session_id=session_id, proc=proc, use_pty=use_pty, master_fd=master_fd),
                name=f"terminal_reader_{session_id}",
            )

            return_code = await proc.wait()
            await read_task
        except asyncio.CancelledError:
            final_status = "interrupted"
        except Exception as exc:
            final_status = "failed"
            LOG.error("CLI execute exception was thrown.")
            LOG.exception(exc)
            await self._append_event(session_id, "output", {"type": "stderr", "line": str(exc)})
        finally:
            final_status = await self._resolve_final_status(session_id=session_id, status=final_status)

            if final_status == "interrupted" and proc is not None and getattr(proc, "returncode", None) is None:
                self._signal_process(proc)
                try:
                    return_code = await asyncio.wait_for(proc.wait(), timeout=self._shutdown_timeout)
                except TimeoutError:
                    self._signal_process(proc, force=True)
                    try:
                        return_code = await asyncio.wait_for(proc.wait(), timeout=self._shutdown_timeout)
                    except TimeoutError:
                        LOG.warning("Terminal session '%s' process did not exit cleanly.", session_id)

            if proc is not None:
                proc_returncode = getattr(proc, "returncode", None)
                if proc_returncode is not None:
                    return_code = int(proc_returncode)

            await self._append_event(session_id, "close", {"exitcode": return_code})
            await self._finalize_session(session_id=session_id, status=final_status, exit_code=return_code)

            if read_task is not None and not read_task.done():
                read_task.cancel()

            if master_fd is not None:
                try:
                    os.close(master_fd)
                except OSError:
                    pass

    async def _read_process_output(self, session_id: str, proc: Process, use_pty: bool, master_fd: int | None) -> None:
        if use_pty is False:
            assert proc.stdout is not None
            async for raw_line in proc.stdout:
                line = raw_line.rstrip(b"\n")
                await self._append_event(
                    session_id,
                    "output",
                    {"type": "stdout", "line": line.decode("utf-8", errors="replace")},
                )
            return

        assert master_fd is not None
        loop: AbstractEventLoop = asyncio.get_running_loop()
        buffer = b""

        while True:
            try:
                chunk = await loop.run_in_executor(None, lambda: os.read(master_fd, 1024))
            except OSError as exc:
                if exc.errno == errno.EIO:
                    break
                raise

            if not chunk:
                if buffer:
                    await self._append_event(
                        session_id,
                        "output",
                        {"type": "stdout", "line": buffer.decode("utf-8", errors="replace")},
                    )
                break

            buffer += chunk
            *lines, buffer = buffer.split(b"\n")
            for line in lines:
                await self._append_event(
                    session_id,
                    "output",
                    {"type": "stdout", "line": line.decode("utf-8", errors="replace")},
                )

    async def _append_event(self, session_id: str, event: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            metadata = self._load_metadata(session_id)
            if metadata is None:
                msg = f"Unknown terminal session '{session_id}'."
                raise FileNotFoundError(msg)

            next_sequence = int(metadata.get("last_sequence", 0)) + 1
            metadata["last_sequence"] = next_sequence
            self._write_json(self._metadata_path(session_id), metadata)

            record = {"seq": next_sequence, "event": event, "data": data}
            with self._transcript_path(session_id).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")

            if self._active is not None and self._active.session_id == session_id:
                for subscriber in list(self._active.subscribers):
                    subscriber.put_nowait(record)

            return record

    async def _finalize_session(self, session_id: str, status: str, exit_code: int) -> None:
        async with self._lock:
            metadata = self._load_metadata(session_id)
            if metadata is None:
                return

            now = time.time()
            metadata["status"] = status
            metadata["exit_code"] = exit_code
            metadata["finished_at"] = now
            metadata["expires_at"] = now + self._drain_ttl
            self._write_json(self._metadata_path(session_id), metadata)

            if self._load_active_marker() == session_id:
                self._clear_active_marker()

            runtime = self._active
            if runtime is not None and runtime.session_id == session_id:
                subscribers = list(runtime.subscribers)
                self._active = None
                for subscriber in subscribers:
                    subscriber.put_nowait(None)

    def _get_active_session_locked(self) -> dict[str, Any] | None:
        session_id = self._load_active_marker()
        if session_id is None:
            return None

        metadata = self._load_metadata(session_id)
        if metadata is None:
            self._clear_active_marker()
            return None

        return metadata

    def _recover_orphaned_active_session(self, now: float) -> None:
        session_id = self._load_active_marker()
        if session_id is None:
            return

        metadata = self._load_metadata(session_id)
        if metadata is None:
            self._clear_active_marker()
            return

        metadata["status"] = "interrupted"
        metadata["finished_at"] = now
        metadata["expires_at"] = now + self._drain_ttl
        metadata["exit_code"] = -1 if metadata.get("exit_code") is None else metadata["exit_code"]
        self._write_json(self._metadata_path(session_id), metadata)
        self._clear_active_marker()

    def _cleanup_expired_sessions(self, now: float) -> None:
        self._ensure_root()
        active_session_id = self._load_active_marker()

        for path in self.root_path.iterdir():
            if path.name == ACTIVE_FILE_NAME or path.is_dir() is False:
                continue

            metadata = self._load_metadata(path.name)
            if metadata is None:
                shutil.rmtree(path, ignore_errors=True)
                continue

            expires_at = metadata.get("expires_at")
            if expires_at is None or float(expires_at) > now:
                continue

            if active_session_id == path.name:
                self._clear_active_marker()
                active_session_id = None

            shutil.rmtree(path, ignore_errors=True)

    def _parse_since(self, request: Request) -> int:
        values: list[int] = []
        candidates = [request.query.get("since"), request.headers.get("Last-Event-ID")]
        for candidate in candidates:
            if candidate in (None, ""):
                continue
            try:
                value = int(candidate)
            except ValueError as exc:
                msg = "Resume cursor must be an integer."
                raise ValueError(msg) from exc

            if value < 0:
                msg = "Resume cursor must be zero or greater."
                raise ValueError(msg)

            values.append(value)

        return max(values, default=0)

    async def _force_interrupt_session(self, session_id: str) -> None:
        async with self._lock:
            metadata = self._load_metadata(session_id)
            if metadata is None:
                return

            now = time.time()
            metadata["status"] = "interrupted"
            metadata["finished_at"] = now
            metadata["expires_at"] = now + self._drain_ttl
            metadata["exit_code"] = -1 if metadata.get("exit_code") is None else metadata["exit_code"]
            self._write_json(self._metadata_path(session_id), metadata)

            if self._load_active_marker() == session_id:
                self._clear_active_marker()

            runtime = self._active
            if runtime is not None and runtime.session_id == session_id:
                subscribers = list(runtime.subscribers)
                self._active = None
                for subscriber in subscribers:
                    subscriber.put_nowait(None)

    async def _resolve_final_status(self, session_id: str, status: str) -> str:
        async with self._lock:
            runtime = self._active
            if runtime is not None and runtime.session_id == session_id and runtime.interrupted:
                return "interrupted"

            metadata = self._load_metadata(session_id)
            if metadata is not None and metadata.get("status") == "interrupted":
                return "interrupted"

        return status

    def _signal_process(self, process: Process | None, *, force: bool = False) -> None:
        if process is None or getattr(process, "returncode", None) is not None:
            return

        action = process.kill if force else process.terminate
        try:
            action()
        except ProcessLookupError:
            return

    async def _emit_sse(self, request: Request, response: web.StreamResponse, event: dict[str, Any]) -> bool:
        if self._is_request_disconnected(request):
            return False

        payload = f"id: {event['seq']}\nevent: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
        try:
            await response.write(payload.encode("utf-8"))
        except ConnectionResetError:
            return False

        return True

    async def _emit_keepalive(self, request: Request, response: web.StreamResponse) -> bool:
        if self._is_request_disconnected(request):
            return False

        try:
            await response.write(b": keepalive\n\n")
        except ConnectionResetError:
            return False

        return True

    def _read_transcript(self, session_id: str, since: int, until: int | None = None) -> list[dict[str, Any]]:
        transcript_path = self._transcript_path(session_id)
        if transcript_path.exists() is False:
            return []

        events: list[dict[str, Any]] = []
        with transcript_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue

                event = json.loads(line)
                sequence = int(event["seq"])
                if sequence <= since:
                    continue
                if until is not None and sequence > until:
                    break
                events.append(event)

        return events

    def _build_env(self) -> dict[str, str]:
        env_vars = os.environ.copy()
        env_vars.update(
            {
                "PWD": self.config.download_path,
                "FORCE_COLOR": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )

        if os.name != "nt":
            env_vars.update(
                {
                    "TERM": "xterm-256color",
                    "LANG": "en_US.UTF-8",
                    "LC_ALL": "en_US.UTF-8",
                    "SHELL": "/bin/bash",
                }
            )

        return env_vars

    def _open_pty(self) -> tuple[int, int] | None:
        try:
            import pty

            return pty.openpty()
        except ImportError:
            return None

    def _is_request_disconnected(self, request: Request) -> bool:
        return request.transport is None or request.transport.is_closing()

    def _ensure_root(self) -> None:
        self.root_path.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        return self.root_path / session_id

    def _metadata_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / METADATA_FILE_NAME

    def _transcript_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / TRANSCRIPT_FILE_NAME

    def _active_marker_path(self) -> Path:
        return self.root_path / ACTIVE_FILE_NAME

    def _set_active_marker(self, session_id: str) -> None:
        self._write_json(self._active_marker_path(), {"session_id": session_id})

    def _clear_active_marker(self) -> None:
        self._active_marker_path().unlink(missing_ok=True)

    def _load_active_marker(self) -> str | None:
        data = self._read_json(self._active_marker_path())
        if not isinstance(data, dict):
            return None
        session_id = data.get("session_id")
        return session_id if isinstance(session_id, str) and session_id else None

    def _load_metadata(self, session_id: str) -> dict[str, Any] | None:
        data = self._read_json(self._metadata_path(session_id))
        return data if isinstance(data, dict) else None

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if path.exists() is False:
            return None

        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        temp_path.replace(path)
