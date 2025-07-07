import logging
import os
from typing import TYPE_CHECKING

from app.library.config import Config
from app.library.Events import EventBus, Events, error
from app.library.router import RouteType, route

if TYPE_CHECKING:
    from asyncio import Task
    from asyncio.events import AbstractEventLoop
    from asyncio.subprocess import Process

LOG: logging.Logger = logging.getLogger(__name__)


@route(RouteType.SOCKET, "cli_post", "socket_cli_post")
async def cli_post(config: Config, notify: EventBus, sid: str, data: str):
    if not config.console_enabled:
        await notify.emit(Events.ERROR, data=error("Console is disabled."), to=sid)
        return

    if not data:
        await notify.emit(Events.CLI_CLOSE, data={"exitcode": 0}, to=sid)
        return

    import asyncio
    import errno
    import shlex
    import subprocess  # ignore

    try:
        LOG.info(f"Cli command from client '{sid}'. '{data}'")

        args: list[str] = ["yt-dlp", *shlex.split(data)]
        _env: dict[str, str] = os.environ.copy()
        _env.update(
            {
                "TERM": "xterm-256color",
                "LANG": "en_US.UTF-8",
                "SHELL": "/bin/bash",
                "LC_ALL": "en_US.UTF-8",
                "PWD": config.download_path,
                "FORCE_COLOR": "1",
                "PYTHONUNBUFFERED": "1",
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

        proc: Process = await asyncio.create_subprocess_exec(
            *args,
            cwd=config.download_path,
            stdin=stdin_arg,
            stdout=stdout_arg,
            stderr=stderr_arg,
            env=_env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        if use_pty:
            try:
                os.close(slave_fd)
            except Exception as e:
                LOG.error(f"Error closing PTY. '{e!s}'.")

        async def reader(sid: str):
            if use_pty is False:
                assert proc.stdout is not None
                async for raw_line in proc.stdout:
                    line = raw_line.rstrip(b"\n")
                    await notify.emit(
                        Events.CLI_OUTPUT,
                        data={"type": "stdout", "line": line.decode("utf-8", errors="replace")},
                        to=sid,
                    )
                return

            loop: AbstractEventLoop = asyncio.get_running_loop()
            buffer: bytes = b""
            while True:
                try:
                    chunk: bytes = await loop.run_in_executor(None, lambda: os.read(master_fd, 1024))
                except OSError as e:
                    if e.errno == errno.EIO:
                        break
                    raise

                if not chunk:
                    if buffer:
                        await notify.emit(
                            Events.CLI_OUTPUT,
                            data={"type": "stdout", "line": buffer.decode("utf-8", errors="replace")},
                            to=sid,
                        )
                    break

                buffer += chunk
                *lines, buffer = buffer.split(b"\n")

                for line in lines:
                    await notify.emit(
                        Events.CLI_OUTPUT,
                        data={"type": "stdout", "line": line.decode("utf-8", errors="replace")},
                        to=sid,
                    )
            try:
                os.close(master_fd)
            except Exception as e:
                LOG.error(f"Error closing PTY. '{e!s}'.")

        read_task: Task = asyncio.create_task(reader(sid=sid), name=f"cli_reader_{sid}")

        returncode: int = await proc.wait()

        await read_task

        await notify.emit(Events.CLI_CLOSE, data={"exitcode": returncode}, to=sid)
    except Exception as e:
        LOG.error(f"CLI execute exception was thrown for client '{sid}'.")
        LOG.exception(e)
        await notify.emit(Events.CLI_OUTPUT, data={"type": "stderr", "line": str(e)}, to=sid)
        await notify.emit(Events.CLI_CLOSE, data={"exitcode": -1}, to=sid)
