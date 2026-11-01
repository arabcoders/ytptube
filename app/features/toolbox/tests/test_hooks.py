from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.features.toolbox import service, tools
from app.features.toolbox.schemas import Extra, Result, Submission
from app.features.toolbox.service import Context, Toolbox, ToolboxError
from app.library.Services import Services


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", [None, ""])
async def test_pre_proceeds(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, reason) -> None:
    pre = AsyncMock(return_value=reason)
    execute = AsyncMock(return_value=Result())
    monkeypatch.setitem(tools.TOOLS, "remux", replace(tools.TOOLS["remux"], pre=pre, execute=execute))
    accepted = await toolbox.submit(Submission(tool="remux", file=source.name))
    assert (await terminal(accepted.id)).status == "succeeded"
    pre.assert_awaited_once()
    execute.assert_awaited_once_with(pre.call_args.args[0])


@pytest.mark.asyncio
async def test_pre_skips(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal) -> None:
    reason = "No work is needed."
    pre, execute, post = AsyncMock(return_value=reason), AsyncMock(), AsyncMock()
    workspace, spawn, publish, find = Mock(), AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setitem(tools.TOOLS, "remux", replace(tools.TOOLS["remux"], pre=pre, execute=execute, post=post))
    monkeypatch.setattr(Context, "workspace", workspace)
    monkeypatch.setattr(service.process, "spawn", spawn)
    monkeypatch.setattr(tools, "publish", publish)
    Services.get_instance().add(
        "queue", SimpleNamespace(queue=SimpleNamespace(items=lambda: []), done=SimpleNamespace(get_by_file=find))
    )
    try:
        accepted = await toolbox.submit(Submission(tool="remux", file=source.name))
        job = await terminal(accepted.id)
        saved = await toolbox.repo.get(job.id)
        assert saved == job and job.status == "skipped" and job.message == reason
        assert job.finished_at is not None and job.started_at is not None
        assert job.progress is None and job.result is None and job.error is None and job.error_code is None
        execute.assert_not_awaited()
        post.assert_not_awaited()
        workspace.assert_not_called()
        spawn.assert_not_awaited()
        publish.assert_not_awaited()
        find.assert_not_awaited()
        assert source.read_bytes() == b"original"
    finally:
        Services.get_instance().remove("queue")


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ValueError("Rejected input."), ToolboxError("Rejected input.", "REJECTED")])
async def test_pre_rejects(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, error) -> None:
    execute = AsyncMock()
    monkeypatch.setitem(
        tools.TOOLS, "remux", replace(tools.TOOLS["remux"], pre=AsyncMock(side_effect=error), execute=execute)
    )
    accepted = await toolbox.submit(Submission(tool="remux", file=source.name))
    job = await terminal(accepted.id)
    assert job.status == "failed" and job.error == str(error) and job.result is None
    assert job.error_code == (error.code if isinstance(error, ToolboxError) else "TOOL_FAILED")
    execute.assert_not_awaited()
    assert source.read_bytes() == b"original" and not list(Path(toolbox.config.temp_path).iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["success", "failure", "collision"])
@pytest.mark.parametrize("overwrite_source", [True, False])
async def test_post_boundary(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, mode: str, overwrite_source: bool
) -> None:
    media = source.with_suffix(".mkv")
    source.rename(media)
    target = media.with_suffix(".mp4") if overwrite_source else media.with_name("video.remux.mp4")
    if mode == "collision":
        target.write_bytes(b"existing")
    phases: list[str] = []
    move = Mock(wraps=tools.shutil.move)
    find, update = AsyncMock(return_value=["tracked"]), AsyncMock()
    Services.get_instance().add(
        "queue",
        SimpleNamespace(
            queue=SimpleNamespace(items=lambda: []), done=SimpleNamespace(get_by_file=find, update_file=update)
        ),
    )

    async def execute(ctx: Context) -> Result:
        temporary = ctx.workspace() / "output.mp4"
        temporary.write_bytes(b"completed")
        phases.append("executed")
        await tools.publish(ctx, temporary, target)
        return Result(outputs=[target.name])

    async def post(ctx: Context, temporary: Path) -> None:
        assert phases == ["executed"] and ctx.source == media
        assert temporary.read_bytes() == b"completed" and media.read_bytes() == b"original"
        assert not target.exists()
        find.assert_not_awaited()
        move.assert_not_called()
        phases.append("checked")
        if mode == "failure":
            raise ToolboxError("Output rejected.", "INVALID_OUTPUT")

    check = AsyncMock(side_effect=post)
    monkeypatch.setitem(tools.TOOLS, "remux", replace(tools.TOOLS["remux"], execute=execute, post=check))
    monkeypatch.setattr(tools.shutil, "move", move)
    try:
        accepted = await toolbox.submit(
            Submission(tool="remux", file=media.name, extra=Extra(overwrite_source=overwrite_source))
        )
        job = await terminal(accepted.id)
        assert job.status == ("succeeded" if mode == "success" else "failed")
        if mode == "success":
            assert phases == ["executed", "checked"] and target.read_bytes() == b"completed"
            assert media.exists() != overwrite_source
            assert find.await_count == update.await_count == int(overwrite_source)
        else:
            assert media.read_bytes() == b"original" and job.result is None
            assert target.read_bytes() == b"existing" if mode == "collision" else not target.exists()
            assert check.await_count == int(mode == "failure")
            find.assert_not_awaited()
            update.assert_not_awaited()
            move.assert_not_called()
        assert not list(Path(toolbox.config.temp_path).iterdir()) and not list(media.parent.glob(".*.part"))
    finally:
        Services.get_instance().remove("queue")


@pytest.mark.asyncio
@pytest.mark.parametrize("hook", ["pre", "post"])
@pytest.mark.parametrize("shutdown", [False, True])
async def test_hook_cancellation(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, hook: str, shutdown: bool
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    folders: list[Path] = []

    async def check(*_args) -> None:
        entered.set()
        await asyncio.wait_for(release.wait(), 5)

    async def execute(ctx: Context) -> Result:
        folder = ctx.workspace()
        folders.append(folder)
        temporary = folder / "output.mp4"
        temporary.write_bytes(b"completed")
        await tools.publish(ctx, temporary, source)
        return Result(outputs=[source.name])

    executor = AsyncMock(side_effect=execute)
    monkeypatch.setitem(tools.TOOLS, "remux", replace(tools.TOOLS["remux"], execute=executor, **{hook: check}))
    try:
        accepted = await toolbox.submit(Submission(tool="remux", file=source.name))
        await asyncio.wait_for(entered.wait(), 5)
        if shutdown:
            await asyncio.wait_for(toolbox.shutdown(), 5)
        else:
            await toolbox.cancel(accepted.id)
        job = await terminal(accepted.id)
        assert job.status == ("interrupted" if shutdown else "cancelled")
        assert job.error is None and job.result is None and source.read_bytes() == b"original"
        assert executor.await_count == int(hook == "post")
        assert len(folders) == int(hook == "post") and all(not folder.exists() for folder in folders)
    finally:
        release.set()
