from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.features.toolbox import service, tools
from app.features.toolbox.schemas import Extra, Job, Result, Submission
from app.features.toolbox.service import Context, Toolbox, ToolboxError
from app.library.Services import Services
from app.library.Events import EventBus, Events


@pytest.mark.asyncio
@pytest.mark.parametrize("overwrite_source", [True, False])
async def test_job_persistence(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, overwrite_source: bool
) -> None:
    result = Result(outputs=[source.name if overwrite_source else f"{source.stem}.remux.mp4"])
    emitted: list[Job] = []
    emit = toolbox.emit

    def publish(job: Job) -> None:
        emitted.append(job.model_copy(deep=True))
        emit(job)

    monkeypatch.setattr(toolbox, "emit", publish)
    execute = AsyncMock(return_value=result)
    monkeypatch.setitem(tools.TOOLS, "remux", replace(tools.TOOLS["remux"], execute=execute))
    accepted = await toolbox.submit(
        Submission(tool="remux", file=source.name, extra=Extra(overwrite_source=overwrite_source))
    )
    assert accepted.status == "queued"
    assert isinstance(accepted.id, int) and accepted.id > 0
    assert toolbox.pending[0].job.id == emitted[0].id == accepted.id
    queued = await toolbox.repo.get(accepted.id)
    assert queued is not None and queued.id == accepted.id
    job = await terminal(accepted.id)
    assert job.status == "succeeded"
    assert job.result == result
    saved = await toolbox.repo.get(job.id)
    assert saved and saved.result == job.result and saved.finished_at is not None
    assert saved.extra.overwrite_source is overwrite_source and saved.extra.options == {}
    items, total, _, _ = await toolbox.repo.list_paginated(1, 20, None)
    assert total == 1 and [item.id for item in items] == [accepted.id]
    assert source.read_bytes() == b"original"


@pytest.mark.asyncio
async def test_dispatch_options(toolbox: Toolbox, source: Path) -> None:
    with pytest.raises(ToolboxError, match="Unknown"):
        await toolbox.submit(Submission(tool="missing", file=source.name))
    with pytest.raises(ValidationError):
        await toolbox.submit(Submission(tool="remux", file=source.name, extra=Extra(options={"overwrite": True})))
    with pytest.raises(ValidationError):
        Submission.model_validate({"tool": "remux", "file": source.name, "extra": {"overwrite_source": "false"}})


@pytest.mark.parametrize("overwrite_source", [True, False])
def test_socket_overwrite(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, overwrite_source: bool
) -> None:
    from app.features.core.models import utcnow

    job = Job(
        id=1,
        tool="remux",
        file=source.name,
        extra=Extra(overwrite_source=overwrite_source),
        status="succeeded",
        created_at=utcnow(),
    )
    emit = Mock()
    monkeypatch.setattr(EventBus.get_instance(), "emit", emit)
    Toolbox.emit(toolbox, job)
    emit.assert_called_once_with(Events.TOOLBOX_JOB, data=job.model_dump(mode="json"))
    assert emit.call_args.kwargs["data"]["extra"] == {"overwrite_source": overwrite_source, "options": {}}
    assert emit.call_args.kwargs["data"]["id"] == 1


@pytest.mark.parametrize(
    ("file", "code", "status"),
    [
        ("../escape", "FILE_UNAVAILABLE", 404),
        ("/etc/passwd", "FILE_UNAVAILABLE", 404),
        ("missing.mp4", "FILE_UNAVAILABLE", 404),
        (".", "NOT_A_FILE", 400),
        ("video.part", "ACTIVE_DOWNLOAD", 400),
    ],
)
def test_invalid_files(toolbox: Toolbox, source: Path, file: str, code: str, status: int) -> None:
    if file == "video.part":
        (source.parent / file).write_bytes(b"partial")
    with pytest.raises(ToolboxError) as error:
        toolbox.source(file)
    assert error.value.code == code and error.value.status == status
    if status == 404:
        assert error.value.params == {"file": file}


def test_multipart_filename(toolbox: Toolbox, source: Path) -> None:
    file = source.with_name("Movie.part.1.mp4")
    file.write_bytes(b"complete")
    assert toolbox.source(file.name) == file


@pytest.mark.asyncio
@pytest.mark.parametrize("renamed", [False, True])
async def test_resolved_submission(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, renamed: bool
) -> None:
    folder = source.parent / "tester/bar/日本語 #フォルダ 🧪"
    folder.mkdir(parents=True)
    media = folder / ("Renamed [youtube-dQw4w9WgXcQ].mp4" if renamed else "#360度ロック 🎵 #乃木坂46.mp4")
    media.write_bytes(b"original")
    requested = folder / "Old title [youtube-dQw4w9WgXcQ].mp4" if renamed else media
    relative = requested.relative_to(source.parent).as_posix()
    assert service.get_file(toolbox.config.download_path, relative) == (media, 302 if renamed else 200)
    contexts: list[Context] = []

    async def execute(ctx: Context) -> Result:
        assert ctx.source == media
        ctx.check_source()
        contexts.append(ctx)
        return Result()

    monkeypatch.setitem(tools.TOOLS, "remux", replace(tools.TOOLS["remux"], execute=execute))
    accepted = await toolbox.submit(Submission(tool="remux", file=relative))
    assert accepted.status == "queued" and accepted.file == media.relative_to(source.parent).as_posix()
    assert (await terminal(accepted.id)).status == "succeeded"
    media.unlink()
    with pytest.raises(ToolboxError) as error:
        contexts[0].check_source()
    assert error.value.code == "FILE_UNAVAILABLE"
    assert error.value.params == {"file": media.relative_to(source.parent).as_posix()}


def test_symlink_escape(toolbox: Toolbox, source: Path, tmp_path: Path) -> None:
    (tmp_path / "escape").symlink_to(tmp_path.parent)
    with pytest.raises(ToolboxError):
        toolbox.source(f"escape/{source.parent.name}/{source.name}/../../outside")
    (tmp_path / "outside").symlink_to("/etc/passwd")
    with pytest.raises(ToolboxError):
        toolbox.source("outside")


def test_active_file(toolbox: Toolbox, source: Path) -> None:
    queue = SimpleNamespace(
        queue=SimpleNamespace(
            items=lambda: [
                ("id", SimpleNamespace(info=SimpleNamespace(filename=source.name, tmpfilename=None, folder="")))
            ]
        )
    )
    Services.get_instance().add("queue", queue)
    try:
        with pytest.raises(ToolboxError, match="active"):
            toolbox.source(source.name)
    finally:
        Services.get_instance().remove("queue")


@pytest.mark.asyncio
async def test_bounded_queue(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    count = 0

    async def execute(_: Context) -> Result:
        nonlocal count
        count += 1
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return Result()

    monkeypatch.setitem(tools.TOOLS, "remux", replace(tools.TOOLS["remux"], execute=execute))
    first = await toolbox.submit(Submission(tool="remux", file=source.name))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        waiting = [await toolbox.submit(Submission(tool="remux", file=source.name)) for _ in range(service.QUEUE_LIMIT)]
        ids = [first.id, *(job.id for job in waiting)]
        assert len(set(ids)) == len(ids) and ids == sorted(ids)
        with pytest.raises(ToolboxError) as error:
            await toolbox.submit(Submission(tool="remux", file=source.name))
        assert error.value.status == 429 and count == 1
        with pytest.raises(ToolboxError) as error:
            await toolbox.delete(first.id)
        assert error.value.status == 409
        cancelled = await toolbox.cancel(waiting[0].id)
        assert cancelled.status == "cancelled" and count == 1
        assert (await toolbox.cancel(waiting[0].id)).status == "cancelled"
        release.set()
        assert (await terminal(first.id)).status == "succeeded"
        assert (await terminal(waiting[-1].id)).status == "succeeded"
        assert count == service.QUEUE_LIMIT
    finally:
        release.set()


@pytest.mark.asyncio
async def test_queued_missing(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def execute(_: Context) -> Result:
        nonlocal calls
        calls += 1
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return Result()

    monkeypatch.setitem(tools.TOOLS, "remux", replace(tools.TOOLS["remux"], execute=execute))
    first = await toolbox.submit(Submission(tool="remux", file=source.name))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        second = await toolbox.submit(Submission(tool="remux", file=source.name))
        source.unlink()
        release.set()
        assert (await terminal(first.id)).status == "succeeded"
        assert (await terminal(second.id)).error_code == "FILE_UNAVAILABLE" and calls == 1
    finally:
        release.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [0, 1])
async def test_second_tool(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, code: int
) -> None:
    stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
    stdout.feed_eof()
    stderr.feed_data(b"tool diagnostic\n")
    stderr.feed_eof()
    proc = SimpleNamespace(stdout=stdout, stderr=stderr, wait=AsyncMock(return_value=code))
    release = AsyncMock()
    monkeypatch.setattr(service.process, "spawn", AsyncMock(return_value=proc))
    monkeypatch.setattr(service.process, "release", release)
    monkeypatch.setattr(tools, "ffmpeg_bin", lambda: None)

    async def execute(ctx: Context) -> Result:
        assert ctx.job.message == "Running"
        temporary = ctx.workspace() / "output.webm"
        temporary.write_bytes(b"converted")
        await ctx.run("converter", [])
        final = ctx.destination(".webm", ".converted")
        await tools.publish(ctx, temporary, final)
        return Result(outputs=[final.relative_to(ctx.root).as_posix()])

    monkeypatch.setitem(
        tools.TOOLS,
        "convert",
        tools.Tool(name="Convert", description="Convert media.", options=tools.RemuxOptions, execute=execute),
    )
    available = {item["id"]: item["available"] for item in toolbox.tools()}
    assert available == {"remux": False, "convert": True}
    job = await toolbox.submit(Submission(tool="convert", file=source.name, extra=Extra(overwrite_source=False)))
    job = await terminal(job.id)
    assert job.status == ("succeeded" if code == 0 else "failed")
    if code == 0:
        assert job.result == Result(outputs=["video.converted.webm"])
        assert source.with_name("video.converted.webm").read_bytes() == b"converted"
    else:
        assert job.error_code == "TOOL_FAILED" and job.error == "Operation failed. See the job log."
        assert job.log == "tool diagnostic\n" and job.result is None
    assert source.read_bytes() == b"original"
    assert not list(Path(toolbox.config.temp_path).iterdir())
    release.assert_awaited_once_with(proc)


@pytest.mark.asyncio
async def test_restart_interruption(toolbox: Toolbox, source: Path) -> None:
    from app.features.core.models import utcnow

    jobs = [
        await toolbox.repo.create(
            {
                "tool": "remux",
                "file": source.name,
                "extra": Extra(overwrite_source=status == "running").model_dump(),
                "status": status,
                "created_at": utcnow(),
            }
        )
        for status in ("queued", "running")
    ]
    folder = source.parent / "work" / "ytp-tmp-running"
    folder.mkdir()
    partial = folder / "output.part.mp4"
    partial.write_bytes(b"retained")
    await toolbox.repo.interrupt()
    for job in jobs:
        saved = await toolbox.get(job.id)
        assert saved.status == "interrupted" and saved.finished_at is not None
        assert saved.extra == job.extra and saved.extra.options == {}
    assert partial.read_bytes() == b"retained"


@pytest.mark.asyncio
async def test_shutdown_queue(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    entered = asyncio.Event()

    async def execute(ctx: Context) -> Result:
        folders.append(ctx.workspace())
        entered.set()
        await asyncio.wait_for(asyncio.Event().wait(), 5)
        return Result()

    folders: list[Path] = []
    monkeypatch.setitem(tools.TOOLS, "remux", replace(tools.TOOLS["remux"], execute=execute))
    first = await toolbox.submit(Submission(tool="remux", file=source.name))
    await asyncio.wait_for(entered.wait(), 5)
    second = await toolbox.submit(Submission(tool="remux", file=source.name))
    await asyncio.wait_for(toolbox.shutdown(), 5)
    assert (await toolbox.get(first.id)).status == "interrupted"
    assert (await toolbox.get(second.id)).status == "interrupted"
    assert len(folders) == 1 and not folders[0].exists()
    assert source.read_bytes() == b"original"
