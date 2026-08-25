import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
import time
from typing import Any, cast

import pytest
import pytest_asyncio
from aiohttp import web

from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.TerminalSessionManager import TerminalSessionManager
from app.library.config import Config
from app.library.encoder import Encoder
from app.routes.api.system import (
    cancel_terminal_session,
    create_terminal_session,
    get_active_terminal_session,
    list_terminal_sessions,
    get_terminal_session,
    stream_terminal_session,
)
from app.tests.helpers import url_for


class _FakeStdout:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def __aiter__(self) -> "_FakeStdout":
        return self

    async def __anext__(self) -> bytes:
        if not self._lines:
            raise StopAsyncIteration
        return self._lines.pop(0)


class _BlockingProc:
    def __init__(self, done_event: asyncio.Event) -> None:
        self.stdout = _FakeStdout([])
        self._done_event = done_event
        self.returncode: int | None = None

    async def wait(self) -> int:
        await self._done_event.wait()
        self.returncode = 0
        return 0


class _CompletedProc:
    def __init__(self, lines: list[bytes], exit_code: int = 0) -> None:
        self.stdout = _FakeStdout(lines)
        self._exit_code = exit_code
        self.returncode: int | None = None

    async def wait(self) -> int:
        await asyncio.sleep(0)
        self.returncode = self._exit_code
        return self._exit_code


class _TerminableProc:
    def __init__(self) -> None:
        self.stdout = _FakeStdout([])
        self.returncode: int | None = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_started = asyncio.Event()
        self._done_event = asyncio.Event()

    def terminate(self) -> None:
        self.terminate_calls += 1
        if self.returncode is None:
            self.returncode = -15
            self._done_event.set()

    def kill(self) -> None:
        self.kill_calls += 1
        if self.returncode is None:
            self.returncode = -9
            self._done_event.set()

    async def wait(self) -> int:
        self.wait_started.set()
        await self._done_event.wait()
        assert self.returncode is not None
        return self.returncode


@pytest_asyncio.fixture
async def terminal_setup(tmp_path: Path) -> AsyncIterator[tuple[Config, TerminalSessionManager, Encoder]]:
    Scheduler._reset_singleton()
    Services._reset_singleton()
    Config._reset_singleton()
    TerminalSessionManager._reset_singleton()

    config = Config.get_instance()
    config.console_enabled = True
    config.config_path = str(tmp_path / "config")
    config.download_path = str(tmp_path / "downloads")
    Path(config.config_path).mkdir(parents=True, exist_ok=True)
    Path(config.download_path).mkdir(parents=True, exist_ok=True)

    manager = TerminalSessionManager.get_instance()
    encoder = Encoder()
    try:
        yield config, manager, encoder
    finally:
        manager._shutdown_timeout = 0.05
        await asyncio.wait_for(manager.on_shutdown(cast(Any, None)), timeout=1)
        await asyncio.wait_for(Scheduler.get_instance().on_shutdown(web.Application()), timeout=1)
        TerminalSessionManager._reset_singleton()
        Scheduler._reset_singleton()
        Services._reset_singleton()
        Config._reset_singleton()


def _terminal_handlers(config: Config, encoder: Encoder, manager: TerminalSessionManager) -> dict[str, Any]:
    async def create(request):
        return await create_terminal_session(request, config, encoder, manager)

    async def list_sessions(_request):
        return await list_terminal_sessions(config, encoder, manager)

    async def active(_request):
        return await get_active_terminal_session(config, encoder, manager)

    async def get_session(request):
        return await get_terminal_session(request, config, encoder, manager)

    async def cancel(request):
        return await cancel_terminal_session(request, config, encoder, manager)

    async def stream(request):
        return await stream_terminal_session(request, config, manager)

    return {
        "system.terminal": create,
        "system.terminal.list": list_sessions,
        "system.terminal.active": active,
        "system.terminal.session": get_session,
        "system.terminal.cancel": cancel,
        "system.terminal.stream": stream,
    }


async def _wait_for_active(manager: TerminalSessionManager) -> None:
    async with asyncio.timeout(1):
        while manager._active is None:
            await asyncio.sleep(0)


async def _wait_for_status(manager: TerminalSessionManager, session_id: str, status: str) -> None:
    async with asyncio.timeout(1):
        while True:
            metadata = await manager.get_session(session_id)
            if metadata is not None and metadata["status"] == status:
                return
            await asyncio.sleep(0)


class TestTerminalSessionRoutes:
    @pytest.mark.asyncio
    async def test_attach_registers_cleanup_job(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder]
    ) -> None:
        _config, manager, _encoder = terminal_setup
        app = web.Application()

        manager.attach(app)

        scheduler = Scheduler.get_instance()
        assert scheduler.has(f"{TerminalSessionManager.__name__}.{TerminalSessionManager.cleanup.__name__}")
        assert manager._cleanup_job_id == f"{TerminalSessionManager.__name__}.{TerminalSessionManager.cleanup.__name__}"

    @pytest.mark.asyncio
    async def test_start_conflict_meta(
        self,
        terminal_setup: tuple[Config, TerminalSessionManager, Encoder],
        monkeypatch: pytest.MonkeyPatch,
        test_client,
    ) -> None:
        config, manager, encoder = terminal_setup
        await manager.initialize()

        done_event = asyncio.Event()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return _BlockingProc(done_event)

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)
        client = await test_client(_terminal_handlers(config, encoder, manager))

        response = await client.post(url_for("system.terminal"), json={"command": "--help"})
        payload = await response.json()

        assert 200 == response.status
        assert payload["session_id"]
        assert "starting" == payload["status"]

        await asyncio.sleep(0)

        conflict = await client.post(url_for("system.terminal"), json={"command": "--help"})
        assert 409 == conflict.status
        assert "already active" in (await conflict.text()).lower()

        active = await client.get(url_for("system.terminal.active"))
        active_payload = await active.json()
        assert payload["session_id"] == active_payload["session_id"]

        assert manager._active is not None
        task = manager._active.task
        done_event.set()
        await task

    @pytest.mark.asyncio
    async def test_stream_replays_resume(
        self,
        terminal_setup: tuple[Config, TerminalSessionManager, Encoder],
        monkeypatch: pytest.MonkeyPatch,
        test_client,
    ) -> None:
        config, manager, encoder = terminal_setup
        await manager.initialize()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return _CompletedProc([b"first\n", b"second\n"])

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)
        client = await test_client(_terminal_handlers(config, encoder, manager))

        start_response = await client.post(url_for("system.terminal"), json={"command": "--version"})
        session_id = (await start_response.json())["session_id"]

        await _wait_for_status(manager, session_id, "completed")

        status_response = await client.get(url_for("system.terminal.session", session_id=session_id))
        status_payload = await status_response.json()
        assert "completed" == status_payload["status"]
        assert 3 == status_payload["last_sequence"]
        assert 0 == status_payload["exit_code"]

        stream_response = await client.get(url_for("system.terminal.stream", session_id=session_id))
        stream_payload = await stream_response.text()

        assert "id: 1" in stream_payload
        assert "id: 2" in stream_payload
        assert "id: 3" in stream_payload
        assert 'data: {"type": "stdout", "line": "first"}' in stream_payload
        assert 'data: {"exitcode": 0}' in stream_payload

        resumed_response = await client.get(
            url_for("system.terminal.stream", session_id=session_id, query={"since": "1"})
        )
        resumed_payload = await resumed_response.text()

        assert "id: 1" not in resumed_payload
        assert "id: 2" in resumed_payload
        assert "id: 3" in resumed_payload

    @pytest.mark.asyncio
    async def test_completed_expires(
        self,
        terminal_setup: tuple[Config, TerminalSessionManager, Encoder],
        monkeypatch: pytest.MonkeyPatch,
        test_client,
    ) -> None:
        config, manager, encoder = terminal_setup
        manager._completed_retention = 60.0
        await manager.initialize()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return _CompletedProc([b"done\n"])

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)
        client = await test_client(_terminal_handlers(config, encoder, manager))

        start_response = await client.post(url_for("system.terminal"), json={"command": "--help"})
        session_id = (await start_response.json())["session_id"]

        await _wait_for_status(manager, session_id, "completed")

        before_expiry = await manager.get_session(session_id)
        assert before_expiry is not None

        before_expiry["expires_at"] = time.time() - 1
        manager._write_json(manager._metadata_path(session_id), before_expiry)

        expired = await manager.get_session(session_id)
        assert expired is None
        assert (manager.root_path / session_id).exists()

        await manager.cleanup()

        assert not (manager.root_path / session_id).exists()

    @pytest.mark.asyncio
    async def test_list_keeps_recent_done(
        self,
        terminal_setup: tuple[Config, TerminalSessionManager, Encoder],
        monkeypatch: pytest.MonkeyPatch,
        test_client,
    ) -> None:
        config, manager, encoder = terminal_setup
        now = 1000.0
        monkeypatch.setattr("app.library.TerminalSessionManager.time.time", lambda: now)
        manager._completed_retention = 20.0
        manager._drain_ttl = 1.0
        await manager.initialize()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return _CompletedProc([b"done\n"])

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)
        client = await test_client(_terminal_handlers(config, encoder, manager))

        start_response = await client.post(url_for("system.terminal"), json={"command": "--help"})
        session_id = (await start_response.json())["session_id"]

        await _wait_for_status(manager, session_id, "completed")

        now += 3.0

        listed_response = await client.get(url_for("system.terminal.list"))
        listed_payload = await listed_response.json()

        assert 200 == listed_response.status
        assert 1 == len(listed_payload["items"])
        assert session_id == listed_payload["items"][0]["session_id"]
        assert "completed" == listed_payload["items"][0]["status"]
        assert listed_payload["items"][0]["available_until"] is not None

        persisted = await manager.get_session(session_id)
        assert persisted is not None

        now += 19.0

        expired = await manager.get_session(session_id)
        assert expired is None
        assert (manager.root_path / session_id).exists()

        await manager.cleanup()

        assert not (manager.root_path / session_id).exists()

    @pytest.mark.asyncio
    async def test_list_orders_newest(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder], test_client
    ) -> None:
        config, manager, encoder = terminal_setup
        await manager.initialize()

        first_id = "first"
        second_id = "second"
        expired_id = "expired"

        for session_id in [first_id, second_id, expired_id]:
            session_dir = manager.root_path / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            manager._transcript_path(session_id).touch(exist_ok=True)

        manager._write_json(
            manager._metadata_path(first_id),
            {
                "session_id": first_id,
                "command": "--first",
                "status": "completed",
                "created_at": 10.0,
                "started_at": 11.0,
                "finished_at": 20.0,
                "expires_at": time.time() + 60,
                "exit_code": 0,
                "last_sequence": 2,
            },
        )
        manager._write_json(
            manager._metadata_path(second_id),
            {
                "session_id": second_id,
                "command": "--second",
                "status": "running",
                "created_at": 30.0,
                "started_at": 31.0,
                "finished_at": None,
                "expires_at": None,
                "exit_code": None,
                "last_sequence": 4,
            },
        )
        manager._write_json(
            manager._metadata_path(expired_id),
            {
                "session_id": expired_id,
                "command": "--expired",
                "status": "completed",
                "created_at": 1.0,
                "started_at": 2.0,
                "finished_at": 3.0,
                "expires_at": time.time() - 1,
                "exit_code": 1,
                "last_sequence": 1,
            },
        )

        client = await test_client(_terminal_handlers(config, encoder, manager))
        listed_response = await client.get(url_for("system.terminal.list"))
        listed_payload = await listed_response.json()

        assert 200 == listed_response.status
        assert [second_id, first_id] == [item["session_id"] for item in listed_payload["items"]]
        assert (manager.root_path / expired_id).exists()

        await manager.cleanup()

        assert not (manager.root_path / expired_id).exists()

    @pytest.mark.asyncio
    async def test_shutdown_clears_active(
        self,
        terminal_setup: tuple[Config, TerminalSessionManager, Encoder],
        monkeypatch: pytest.MonkeyPatch,
        test_client,
    ) -> None:
        config, manager, encoder = terminal_setup
        manager._shutdown_timeout = 0.05
        await manager.initialize()

        proc = _TerminableProc()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return proc

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)
        client = await test_client(_terminal_handlers(config, encoder, manager))

        start_response = await client.post(url_for("system.terminal"), json={"command": "--help"})
        session_id = (await start_response.json())["session_id"]

        await asyncio.wait_for(proc.wait_started.wait(), timeout=1)
        await manager.on_shutdown(cast(Any, None))

        metadata = await manager.get_session(session_id)
        transcript = manager._read_transcript(session_id=session_id, since=0)

        assert metadata is not None
        assert "interrupted" == metadata["status"]
        assert -15 == metadata["exit_code"]
        assert metadata["finished_at"] is not None
        assert metadata["expires_at"] is not None
        assert 1 == proc.terminate_calls
        assert 0 == proc.kill_calls
        assert manager._active is None
        assert manager._load_active_marker() is None
        assert "close" == transcript[-1]["event"]
        assert -15 == transcript[-1]["data"]["exitcode"]

    @pytest.mark.asyncio
    async def test_stream_keepalive(
        self,
        terminal_setup: tuple[Config, TerminalSessionManager, Encoder],
        monkeypatch: pytest.MonkeyPatch,
        test_client,
    ) -> None:
        config, manager, encoder = terminal_setup
        manager._keepalive_interval = 0.01
        await manager.initialize()

        done_event = asyncio.Event()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return _BlockingProc(done_event)

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)
        keepalive = asyncio.Event()
        emit_keepalive = manager._emit_keepalive

        async def track_keepalive(*, request, response):
            emitted = await emit_keepalive(request=request, response=response)
            keepalive.set()
            return emitted

        monkeypatch.setattr(manager, "_emit_keepalive", track_keepalive)
        client = await test_client(_terminal_handlers(config, encoder, manager))

        start_response = await client.post(url_for("system.terminal"), json={"command": "--version"})
        session_id = (await start_response.json())["session_id"]
        assert manager._active is not None
        session_task = manager._active.task

        stream_task = asyncio.create_task(client.get(url_for("system.terminal.stream", session_id=session_id)))
        try:
            await asyncio.wait_for(keepalive.wait(), timeout=1)
            done_event.set()
            await asyncio.wait_for(session_task, timeout=1)
            stream_response = await asyncio.wait_for(stream_task, timeout=1)
            stream_payload = await stream_response.text()
        finally:
            done_event.set()
            if not stream_task.done():
                stream_task.cancel()
            await asyncio.gather(stream_task, return_exceptions=True)

        assert ": keepalive" in stream_payload
        assert "id: 1" in stream_payload
        assert 'data: {"exitcode": 0}' in stream_payload

    @pytest.mark.asyncio
    async def test_cancel_active(
        self,
        terminal_setup: tuple[Config, TerminalSessionManager, Encoder],
        monkeypatch: pytest.MonkeyPatch,
        test_client,
    ) -> None:
        config, manager, encoder = terminal_setup
        await manager.initialize()

        proc = _TerminableProc()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return proc

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)
        client = await test_client(_terminal_handlers(config, encoder, manager))

        start_response = await client.post(url_for("system.terminal"), json={"command": "--help"})
        session_id = (await start_response.json())["session_id"]

        await _wait_for_active(manager)
        assert manager._active is not None
        active_task = manager._active.task
        await asyncio.wait_for(proc.wait_started.wait(), timeout=1)

        cancel_response = await client.delete(url_for("system.terminal.cancel", session_id=session_id))
        cancel_payload = await cancel_response.json()

        assert 200 == cancel_response.status
        assert session_id == cancel_payload["session_id"]

        await asyncio.wait_for(active_task, timeout=1)

        metadata = await manager.get_session(session_id)
        transcript = manager._read_transcript(session_id=session_id, since=0)

        assert metadata is not None
        assert "interrupted" == metadata["status"]
        assert -15 == metadata["exit_code"]
        assert 1 == proc.terminate_calls
        assert 0 == proc.kill_calls
        assert transcript[-1]["event"] == "close"
        assert -15 == transcript[-1]["data"]["exitcode"]

    @pytest.mark.asyncio
    async def test_cancel_inactive_conflict(
        self,
        terminal_setup: tuple[Config, TerminalSessionManager, Encoder],
        monkeypatch: pytest.MonkeyPatch,
        test_client,
    ) -> None:
        config, manager, encoder = terminal_setup
        await manager.initialize()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return _CompletedProc([b"done\n"])

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)
        client = await test_client(_terminal_handlers(config, encoder, manager))

        start_response = await client.post(url_for("system.terminal"), json={"command": "--version"})
        session_id = (await start_response.json())["session_id"]

        await _wait_for_status(manager, session_id, "completed")

        cancel_response = await client.delete(url_for("system.terminal.cancel", session_id=session_id))

        assert 409 == cancel_response.status
        assert "not active" in (await cancel_response.text()).lower()

    @pytest.mark.asyncio
    async def test_cancel_unknown(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder], test_client
    ) -> None:
        config, manager, encoder = terminal_setup
        await manager.initialize()

        client = await test_client(_terminal_handlers(config, encoder, manager))
        cancel_response = await client.delete(url_for("system.terminal.cancel", session_id="missing"))

        assert 404 == cancel_response.status
        assert "not found" in (await cancel_response.text()).lower()
