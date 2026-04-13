import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.library.Services import Services
from app.library.TerminalSessionManager import TerminalSessionManager
from app.library.config import Config
from app.library.encoder import Encoder
from app.routes.api.system import (
    cancel_terminal_session,
    create_terminal_session,
    get_active_terminal_session,
    get_terminal_session,
    stream_terminal_session,
)


class _FakeTransport:
    def __init__(self) -> None:
        self._closing = False

    def is_closing(self) -> bool:
        return self._closing


class _FakeRequest:
    def __init__(
        self,
        *,
        payload: dict | None = None,
        match_info: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        can_read_body: bool = False,
    ) -> None:
        self._payload = payload
        self.match_info = match_info or {}
        self.query = query or {}
        self.headers = headers or {}
        self.can_read_body = can_read_body
        self.transport = _FakeTransport()

    async def json(self) -> dict | None:
        return self._payload


class _FakeStreamResponse:
    def __init__(self, *, status: int, headers: dict[str, str]) -> None:
        self.status = status
        self.headers = headers
        self.payload = bytearray()
        self.prepared = False
        self.closed = False

    async def prepare(self, _request: _FakeRequest) -> "_FakeStreamResponse":
        self.prepared = True
        return self

    async def write(self, data: bytes) -> None:
        self.payload.extend(data)

    async def write_eof(self) -> None:
        self.closed = True


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


@pytest.fixture
def terminal_setup(tmp_path: Path) -> tuple[Config, TerminalSessionManager, Encoder]:
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
    return config, manager, encoder


class TestTerminalSessionRoutes:
    @pytest.mark.asyncio
    async def test_start_returns_session_metadata_and_active_conflict(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder], monkeypatch: pytest.MonkeyPatch
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

        request = _FakeRequest(payload={"command": "--help"}, can_read_body=True)
        response = await create_terminal_session(request, config, encoder, manager)
        payload = json.loads(response.body.decode("utf-8"))

        assert 200 == response.status
        assert payload["session_id"]
        assert "starting" == payload["status"]

        await asyncio.sleep(0)

        conflict = await create_terminal_session(request, config, encoder, manager)
        assert 409 == conflict.status
        assert b"already active" in conflict.body.lower()

        active = await get_active_terminal_session(config, encoder, manager)
        active_payload = json.loads(active.body.decode("utf-8"))
        assert payload["session_id"] == active_payload["session_id"]

        assert manager._active is not None
        task = manager._active.task
        done_event.set()
        await task

    @pytest.mark.asyncio
    async def test_stream_endpoint_replays_persisted_events_and_resume_cursor(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config, manager, encoder = terminal_setup
        await manager.initialize()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return _CompletedProc([b"first\n", b"second\n"])

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)
        monkeypatch.setattr("app.library.TerminalSessionManager.web.StreamResponse", _FakeStreamResponse)

        start_request = _FakeRequest(payload={"command": "--version"}, can_read_body=True)
        start_response = await create_terminal_session(start_request, config, encoder, manager)
        session_id = json.loads(start_response.body.decode("utf-8"))["session_id"]

        assert manager._active is not None
        task = manager._active.task
        await task

        status_response = await get_terminal_session(
            _FakeRequest(match_info={"session_id": session_id}), config, encoder, manager
        )
        status_payload = json.loads(status_response.body.decode("utf-8"))
        assert "completed" == status_payload["status"]
        assert 3 == status_payload["last_sequence"]
        assert 0 == status_payload["exit_code"]

        stream_request = _FakeRequest(match_info={"session_id": session_id})
        stream_response = await stream_terminal_session(stream_request, config, manager)
        stream_payload = stream_response.payload.decode("utf-8")

        assert "id: 1" in stream_payload
        assert "id: 2" in stream_payload
        assert "id: 3" in stream_payload
        assert 'data: {"type": "stdout", "line": "first"}' in stream_payload
        assert 'data: {"exitcode": 0}' in stream_payload

        resumed_request = _FakeRequest(match_info={"session_id": session_id}, query={"since": "1"})
        resumed_response = await stream_terminal_session(resumed_request, config, manager)
        resumed_payload = resumed_response.payload.decode("utf-8")

        assert "id: 1" not in resumed_payload
        assert "id: 2" in resumed_payload
        assert "id: 3" in resumed_payload

    @pytest.mark.asyncio
    async def test_completed_session_expires_after_drain_window(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config, manager, encoder = terminal_setup
        manager._drain_ttl = 0.05
        await manager.initialize()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return _CompletedProc([b"done\n"])

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)

        start_request = _FakeRequest(payload={"command": "--help"}, can_read_body=True)
        start_response = await create_terminal_session(start_request, config, encoder, manager)
        session_id = json.loads(start_response.body.decode("utf-8"))["session_id"]

        assert manager._active is not None
        task = manager._active.task
        await task

        before_expiry = await manager.get_session(session_id)
        assert before_expiry is not None

        await asyncio.sleep(0.06)

        expired = await manager.get_session(session_id)
        assert expired is None
        assert not (manager.root_path / session_id).exists()

    @pytest.mark.asyncio
    async def test_shutdown_interrupts_active_session_and_clears_active_marker(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder], monkeypatch: pytest.MonkeyPatch
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

        start_request = _FakeRequest(payload={"command": "--help"}, can_read_body=True)
        start_response = await create_terminal_session(start_request, config, encoder, manager)
        session_id = json.loads(start_response.body.decode("utf-8"))["session_id"]

        await proc.wait_started.wait()
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
    async def test_stream_endpoint_emits_keepalive_for_silent_active_session(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder], monkeypatch: pytest.MonkeyPatch
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
        monkeypatch.setattr("app.library.TerminalSessionManager.web.StreamResponse", _FakeStreamResponse)

        start_request = _FakeRequest(payload={"command": "--version"}, can_read_body=True)
        start_response = await create_terminal_session(start_request, config, encoder, manager)
        session_id = json.loads(start_response.body.decode("utf-8"))["session_id"]
        assert manager._active is not None
        session_task = manager._active.task

        stream_request = _FakeRequest(match_info={"session_id": session_id})
        stream_task = asyncio.create_task(_stream_session(stream_request, config, manager))

        await asyncio.sleep(0.03)
        done_event.set()
        await session_task
        stream_response = await stream_task
        stream_payload = stream_response.payload.decode("utf-8")

        assert ": keepalive" in stream_payload
        assert "id: 1" in stream_payload
        assert 'data: {"exitcode": 0}' in stream_payload

    @pytest.mark.asyncio
    async def test_cancel_endpoint_interrupts_active_session(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder], monkeypatch: pytest.MonkeyPatch
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

        start_request = _FakeRequest(payload={"command": "--help"}, can_read_body=True)
        start_response = await create_terminal_session(start_request, config, encoder, manager)
        session_id = json.loads(start_response.body.decode("utf-8"))["session_id"]

        await proc.wait_started.wait()

        cancel_response = await cancel_terminal_session(
            _FakeRequest(match_info={"session_id": session_id}), config, encoder, manager
        )
        cancel_payload = json.loads(cancel_response.body.decode("utf-8"))

        assert 200 == cancel_response.status
        assert session_id == cancel_payload["session_id"]

        assert manager._active is not None
        active_task = manager._active.task
        await active_task

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
    async def test_cancel_endpoint_returns_conflict_for_inactive_session(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config, manager, encoder = terminal_setup
        await manager.initialize()

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return _CompletedProc([b"done\n"])

        monkeypatch.setattr(
            "app.library.TerminalSessionManager.asyncio.create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(manager, "_open_pty", lambda: None)

        start_request = _FakeRequest(payload={"command": "--version"}, can_read_body=True)
        start_response = await create_terminal_session(start_request, config, encoder, manager)
        session_id = json.loads(start_response.body.decode("utf-8"))["session_id"]

        assert manager._active is not None
        await manager._active.task

        cancel_response = await cancel_terminal_session(
            _FakeRequest(match_info={"session_id": session_id}), config, encoder, manager
        )

        assert 409 == cancel_response.status
        assert b"not active" in cancel_response.body.lower()

    @pytest.mark.asyncio
    async def test_cancel_endpoint_returns_not_found_for_unknown_session(
        self, terminal_setup: tuple[Config, TerminalSessionManager, Encoder]
    ) -> None:
        config, manager, encoder = terminal_setup
        await manager.initialize()

        cancel_response = await cancel_terminal_session(
            _FakeRequest(match_info={"session_id": "missing"}), config, encoder, manager
        )

        assert 404 == cancel_response.status
        assert b"not found" in cancel_response.body.lower()


async def _stream_session(
    request: _FakeRequest, config: Config, manager: TerminalSessionManager
) -> _FakeStreamResponse:
    response = await stream_terminal_session(request, config, manager)
    assert isinstance(response, _FakeStreamResponse)
    return response
