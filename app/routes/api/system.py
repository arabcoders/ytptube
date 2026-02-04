import asyncio
import errno
import logging
import os
import shlex
import time
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.web import Request, Response
from aiohttp.web_runner import GracefulExit

from app.features.dl_fields.service import DLFields
from app.features.presets.service import Presets
from app.library.config import Config
from app.library.downloads import DownloadQueue
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.router import route
from app.library.UpdateChecker import UpdateChecker
from app.library.Utils import list_folders

if TYPE_CHECKING:
    from asyncio import Task
    from asyncio.events import AbstractEventLoop
    from asyncio.subprocess import Process

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/system/configuration", "system.configuration")
async def system_config(queue: DownloadQueue, config: Config, encoder: Encoder) -> Response:
    """
    Pause non-active downloads.

    Args:
        queue (DownloadQueue): The download queue instance.
        config (Config): The config instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    return web.json_response(
        data={
            "app": config.frontend(),
            "presets": Presets.get_instance().get_all(),
            "dl_fields": await DLFields.get_instance().get_all_serialized(),
            "paused": queue.is_paused(),
            "folders": list_folders(
                path=Path(config.download_path),
                base=Path(config.download_path),
                depth_limit=config.download_path_depth - 1,
            ),
            "history_count": await queue.done.get_total_count(),
            "queue": (await queue.get("queue"))["queue"],
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/system/pause", "system.pause")
async def downloads_pause(queue: DownloadQueue, encoder: Encoder, notify: EventBus) -> Response:
    """
    Pause non-active downloads.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    if queue.is_paused():
        return web.json_response(
            {"message": "Non-active downloads are already paused."},
            status=web.HTTPNotAcceptable.status_code,
            dumps=encoder.encode,
        )

    queue.pause()

    msg = "Non-active downloads have been paused."
    notify.emit(
        Events.PAUSED,
        data={"paused": True, "at": time.time()},
        title="Downloads Paused",
        message=msg,
    )

    return web.json_response(data={"message": msg}, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/system/resume", "system.resume")
async def downloads_resume(queue: DownloadQueue, encoder: Encoder, notify: EventBus) -> Response:
    """
    Resume non-active downloads.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    if not queue.is_paused():
        return web.json_response(
            {"message": "Non-active downloads are not paused."},
            status=web.HTTPNotAcceptable.status_code,
            dumps=encoder.encode,
        )

    queue.resume()

    msg = "Resumed all downloads."
    notify.emit(
        Events.RESUMED,
        data={"paused": False, "at": time.time()},
        title="Downloads Resumed",
        message=msg,
    )

    return web.json_response(data={"message": msg}, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/system/shutdown", "system.shutdown")
async def shutdown_system(request: Request, config: Config, encoder: Encoder, notify: EventBus) -> Response:
    """
    Initiate application shutdown.

    Args:
        request (Request): The request object.
        config (Config): The config instance.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    if config.is_native is not True:
        return web.json_response(
            {"error": "Shutdown is only available in the native mode."},
            status=web.HTTPBadRequest.status_code,
        )

    app = request.app

    async def do_shutdown():
        notify.emit(
            Events.SHUTDOWN,
            data={"app": app},
            title="Application Shutdown",
            message="Shutdown initiated by user request.",
        )
        await asyncio.sleep(0.5)
        await app.shutdown()
        await app.cleanup()
        raise GracefulExit

    # Schedule shutdown after response
    asyncio.create_task(do_shutdown())
    LOG.info("Shutdown initiated by user request. Stopping the server...")
    return web.json_response(
        data={
            "message": "The application shutting down.",
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/system/check-updates", "system.check_updates")
async def check_updates(config: Config, encoder: Encoder, update_checker: UpdateChecker) -> Response:
    """
    Manually trigger update check.

    Args:
        config (Config): The config instance.
        encoder (Encoder): The encoder instance.
        update_checker (UpdateChecker): The update checker instance.

    Returns:
        Response: The response object.

    """
    if config.new_version or config.yt_new_version:
        return web.json_response(
            data={
                "app": {
                    "status": "update_available" if config.new_version else "up_to_date",
                    "current_version": config.app_version,
                    "new_version": config.new_version or None,
                },
                "ytdlp": {
                    "status": "update_available" if config.yt_new_version else "up_to_date",
                    "current_version": config._ytdlp_version(),
                    "new_version": config.yt_new_version or None,
                },
            },
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )

    (app_status, app_new_version), (ytdlp_status, ytdlp_new_version) = await update_checker.check_for_updates()

    return web.json_response(
        data={
            "app": {
                "status": app_status,
                "current_version": config.app_version,
                "new_version": app_new_version,
            },
            "ytdlp": {
                "status": ytdlp_status,
                "current_version": config._ytdlp_version(),
                "new_version": ytdlp_new_version,
            },
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/system/terminal", "system.terminal")
async def stream_terminal(request: Request, config: Config, encoder: Encoder) -> Response | web.StreamResponse:
    if not config.console_enabled:
        return web.json_response(
            {"error": "Console feature is disabled."},
            status=web.HTTPForbidden.status_code,
        )

    if not request.can_read_body:
        return web.json_response(
            {"error": "Request body is required."},
            status=web.HTTPBadRequest.status_code,
        )

    payload = await request.json()
    if not isinstance(payload, dict):
        return web.json_response(
            {"error": "Invalid request payload."},
            status=web.HTTPBadRequest.status_code,
        )

    raw_command = payload.get("command")
    if not isinstance(raw_command, str) or not raw_command.strip():
        return web.json_response(
            {"error": "Command is required."},
            status=web.HTTPBadRequest.status_code,
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

    async def emit_event(event: str, data: dict) -> None:
        if request.transport is None or request.transport.is_closing():
            return
        payload: str = f"event: {event}\ndata: {encoder.encode(data)}\n\n"
        await response.write(payload.encode("utf-8"))

    returncode: int = -1
    try:
        LOG.info("Cli command from client. '%s'", raw_command)

        args: list[str] = ["yt-dlp", *shlex.split(raw_command, posix=os.name != "nt")]
        env_vars: dict[str, str] = os.environ.copy()
        env_vars.update(
            {
                "PWD": config.download_path,
                "FORCE_COLOR": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )

        if "nt" != os.name:
            env_vars.update(
                {
                    "TERM": "xterm-256color",
                    "LANG": "en_US.UTF-8",
                    "LC_ALL": "en_US.UTF-8",
                    "SHELL": "/bin/bash",
                }
            )

        try:
            import pty

            master_fd, slave_fd = pty.openpty()
            stdin_arg = asyncio.subprocess.DEVNULL
            stdout_arg = stderr_arg = slave_fd
            use_pty = True
        except ImportError:
            use_pty = False
            master_fd = slave_fd = None
            stdin_arg = asyncio.subprocess.DEVNULL
            stdout_arg = asyncio.subprocess.PIPE
            stderr_arg = asyncio.subprocess.STDOUT

        creationflags = 0
        if os.name == "nt":
            import subprocess

            creationflags = subprocess.CREATE_NO_WINDOW

        proc: Process = await asyncio.create_subprocess_exec(
            *args,
            cwd=config.download_path,
            stdin=stdin_arg,
            stdout=stdout_arg,
            stderr=stderr_arg,
            env=env_vars,
            creationflags=creationflags,
        )

        if use_pty:
            assert slave_fd is not None
            try:
                os.close(slave_fd)
            except Exception as e:
                LOG.error("Error closing PTY. '%s'.", str(e))

        async def reader() -> None:
            if use_pty is False:
                assert proc.stdout is not None
                async for raw_line in proc.stdout:
                    line = raw_line.rstrip(b"\n")
                    await emit_event("output", {"type": "stdout", "line": line.decode("utf-8", errors="replace")})
                return

            assert master_fd is not None
            read_fd = master_fd
            loop: AbstractEventLoop = asyncio.get_running_loop()
            buffer: bytes = b""
            while True:
                try:
                    chunk: bytes = await loop.run_in_executor(None, lambda: os.read(read_fd, 1024))
                except OSError as e:
                    if e.errno == errno.EIO:
                        break
                    raise

                if not chunk:
                    if buffer:
                        await emit_event(
                            "output",
                            {"type": "stdout", "line": buffer.decode("utf-8", errors="replace")},
                        )
                    break

                buffer += chunk
                *lines, buffer = buffer.split(b"\n")

                for line in lines:
                    await emit_event(
                        "output",
                        {"type": "stdout", "line": line.decode("utf-8", errors="replace")},
                    )
            if master_fd is None:
                return
            try:
                os.close(master_fd)
            except Exception as e:
                LOG.error("Error closing PTY. '%s'.", str(e))

        read_task: Task = asyncio.create_task(reader(), name="cli_reader")

        returncode = await proc.wait()
        await read_task
    except Exception as e:
        LOG.error("CLI execute exception was thrown.")
        LOG.exception(e)
        await emit_event("output", {"type": "stderr", "line": str(e)})
    finally:
        await emit_event("close", {"exitcode": returncode})
        await response.write_eof()

    return response
