import asyncio
from asyncio.subprocess import Process
from pathlib import Path

import pytest

from app.features.streaming import utils
from app.features.streaming.types import StreamingError


class Reader:
    def __init__(self, chunks: list[bytes], blocked: asyncio.Event | None = None):
        self.chunks = chunks
        self.blocked = blocked

    async def read(self, _size: int) -> bytes:
        if self.chunks:
            return self.chunks.pop(0)
        if self.blocked is not None:
            self.blocked.set()
            await asyncio.wait_for(asyncio.Event().wait(), 5)
        return b""


class Child:
    def __init__(self, chunks: list[bytes], blocked: asyncio.Event | None = None):
        self.stdout = Reader(chunks, blocked)
        self.stderr = Reader([b"e" * (utils.MAX_STDERR * 2)])
        self.returncode: int | None = None
        self.terminated = False

    async def wait(self) -> int:
        self.returncode = 0
        return 0

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.terminated = True


@pytest.mark.asyncio
async def test_bounded_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    child = Child([b"complete"])

    async def spawn(*_args, **_kwargs) -> Child:
        return child

    monkeypatch.setattr(utils.asyncio, "create_subprocess_exec", spawn)
    file = tmp_path / "prepared.ts"
    code, _, stderr = await utils.run("fake-ffmpeg", [], deadline=1, max_bytes=8, output=file)
    assert code == 0 and file.read_bytes() == b"complete"
    assert len(stderr) == utils.MAX_STDERR
    child.stdout = Reader([b"too-large-output"])
    child.returncode = None
    with pytest.raises(StreamingError, match="size limit"):
        await utils.run("fake-ffmpeg", [], deadline=1, max_bytes=8, output=file)
    assert child.terminated and child.returncode == 0


@pytest.mark.asyncio
async def test_cancelled_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = asyncio.Event()
    child = Child([b"partial"], blocked)

    async def spawn(*_args, **_kwargs) -> Child:
        return child

    monkeypatch.setattr(utils.asyncio, "create_subprocess_exec", spawn)
    task = asyncio.create_task(utils.run("fake-ffmpeg", [], deadline=5, max_bytes=64, output=tmp_path / "partial.ts"))
    try:
        await asyncio.wait_for(blocked.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert child.terminated and child.returncode == 0
    finally:
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)


@pytest.mark.asyncio
async def test_admission_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = asyncio.Event()
    child = Child([], blocked)

    async def spawn(*_args, **_kwargs) -> Child:
        return child

    monkeypatch.setattr(utils.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(utils, "MAX_PROCESSES", 1)
    task = asyncio.create_task(utils.run("fake-ffmpeg", [], deadline=5, max_bytes=64))
    try:
        await asyncio.wait_for(blocked.wait(), 1)
        with pytest.raises(utils.PreparationBusyError):
            await utils.run("fake-ffmpeg", [], deadline=1, max_bytes=64)
    finally:
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)
    assert not utils._running


@pytest.mark.asyncio
async def test_continuous_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    child = Child([])

    async def spawn(*_args, **_kwargs) -> Child:
        return child

    monkeypatch.setattr(utils.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(utils, "MAX_PROCESSES", 1)
    proc = await asyncio.wait_for(utils.spawn("fake-ffmpeg", []), 1)
    try:
        with pytest.raises(utils.PreparationBusyError):
            await asyncio.wait_for(utils.run("fake-ffmpeg", [], deadline=1, max_bytes=64), 1)
        with pytest.raises(utils.PreparationBusyError):
            await asyncio.wait_for(utils.spawn("fake-ffmpeg", []), 1)
    finally:
        await asyncio.wait_for(utils.release(proc), 2)
    assert child.terminated and not utils._running


@pytest.mark.asyncio
async def test_whole_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    child = Child([], asyncio.Event())
    timeout_at = utils.asyncio.timeout_at

    async def spawn(*_args, **_kwargs) -> Child:
        return child

    monkeypatch.setattr(utils.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(utils.asyncio, "timeout_at", lambda _deadline: timeout_at(asyncio.get_running_loop().time()))
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(utils.run("fake-ffmpeg", [], deadline=1, max_bytes=64), 1)
    assert child.terminated and child.returncode == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [True, False])
@pytest.mark.parametrize("continuous", [True, False])
async def test_spawn_cleanup(monkeypatch: pytest.MonkeyPatch, cancel: bool, continuous: bool) -> None:
    started, draining, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    child = Child([b"discarded"])
    abort_spawn = utils._abort_spawn

    async def spawn(*_args, **_kwargs) -> Child:
        started.set()
        await asyncio.wait_for(release.wait(), 2)
        return child

    async def abort(task: asyncio.Task) -> None:
        draining.set()
        await abort_spawn(task)

    async def use() -> None:
        if continuous:
            await utils.spawn("fake-ffmpeg", [])
        else:
            await utils.run("fake-ffmpeg", [], deadline=5, max_bytes=64)

    monkeypatch.setattr(utils.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(utils, "_abort_spawn", abort)
    if not cancel:
        monkeypatch.setattr(utils, "SPAWN_TIMEOUT", 0)
    task = asyncio.create_task(use())
    try:
        await asyncio.wait_for(started.wait(), 1)
        if cancel:
            task.cancel()
        await asyncio.wait_for(draining.wait(), 1)
        if cancel:
            task.cancel()
        assert len(utils._running) == 1 and not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
            await asyncio.wait_for(task, 2)
        assert child.terminated and child.returncode == 0
        assert not utils._running
    finally:
        release.set()
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("continuous", [True, False])
async def test_spawn_unconfirmed(monkeypatch: pytest.MonkeyPatch, continuous: bool) -> None:
    started, release, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()
    child = Child([])
    stop_acquired = utils._stop_acquired
    leases = utils._running.copy()

    async def spawn(*_args, **_kwargs) -> Child:
        started.set()
        await asyncio.wait_for(release.wait(), 2)
        return child

    async def stop(proc: Process) -> None:
        try:
            await stop_acquired(proc)
        finally:
            cleaned.set()

    async def use() -> None:
        if continuous:
            await utils.spawn("fake-ffmpeg", [])
        else:
            await utils.run("fake-ffmpeg", [], deadline=5, max_bytes=64)

    monkeypatch.setattr(utils.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(utils, "_stop_acquired", stop)
    task = asyncio.create_task(use())
    try:
        await asyncio.wait_for(started.wait(), 1)
        monkeypatch.setattr(utils, "CLEANUP_TIMEOUT", 0)
        task.cancel()
        with pytest.raises(utils.ProcessExitError, match="acquisition"):
            await asyncio.wait_for(task, 1)
        assert len(utils._running) == len(leases) + 1
        monkeypatch.setattr(utils, "CLEANUP_TIMEOUT", 1)
        release.set()
        await asyncio.wait_for(cleaned.wait(), 2)
        assert child.terminated and child.returncode == 0
        assert len(utils._running) == len(leases) + 1, "unconfirmed acquisition remains fail-closed"
    finally:
        monkeypatch.setattr(utils, "CLEANUP_TIMEOUT", 1)
        release.set()
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)
        if utils._pending:
            await asyncio.wait_for(asyncio.gather(*utils._pending, return_exceptions=True), 2)
        utils._running.intersection_update(leases)
