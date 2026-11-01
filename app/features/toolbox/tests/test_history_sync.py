from __future__ import annotations

import asyncio
import dataclasses
import errno
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from aiohttp.test_utils import make_mocked_request

from app.features.downloads.items import ItemDTO
from app.features.downloads.repository import DownloadsRepository
from app.features.downloads.runtime.core import Download
from app.features.downloads.store import DataStore, StoreType
from app.features.toolbox import tools
from app.features.toolbox.schemas import Extra, Submission
from app.features.toolbox.service import Context, Toolbox, ToolboxError
from app.library.Events import EventBus, Events
from app.library.Services import Services
from app.library.Utils import get_file_sidecar
from app.routes.api.browser import path_actions


@pytest_asyncio.fixture
async def history(toolbox: Toolbox) -> AsyncIterator[DataStore]:
    DownloadsRepository._reset_singleton()
    repository = DownloadsRepository(flush_interval=0)
    store = DataStore(StoreType.HISTORY, repository)
    Services.get_instance().add("queue", SimpleNamespace(done=store, queue=SimpleNamespace(items=lambda: [])))
    try:
        yield store
    finally:
        Services.get_instance().remove("queue")
        await asyncio.wait_for(repository.shutdown(), 5)
        DownloadsRepository._reset_singleton()


async def save(history: DataStore, file: Path, root: Path, shape: str = "basename") -> ItemDTO:
    info = ItemDTO(
        id=file.parent.name,
        title=file.stem,
        url=f"https://example.test/{file.relative_to(root).as_posix()}",
        folder="" if shape == "directory" else file.parent.relative_to(root).as_posix(),
        download_dir=str(file.parent) if shape == "directory" else None,
        filename=file.relative_to(root).as_posix() if shape == "relative" else file.name,
        sidecar=get_file_sidecar(file),
        status="finished",
    )
    await history.put(Download(info=info))
    await asyncio.wait_for(history.flush(), 5)
    return info


@pytest.mark.asyncio
@pytest.mark.parametrize("shape", ["basename", "relative", "directory"])
async def test_browser_history(
    toolbox: Toolbox, history: DataStore, source: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    root = source.parent
    media, other = root / "nested/video.mp4", root / "other/video.mp4"
    for file in (media, other):
        file.parent.mkdir()
        file.write_bytes(b"original")
    subtitle = media.with_suffix(".en.srt")
    subtitle.write_bytes(b"subtitle")
    selected = await save(history, media, root, shape)
    unrelated = await save(history, other, root)
    nested = root / "other/nested/video.mp4"
    nested.parent.mkdir()
    nested.write_bytes(b"different file")
    partial = await save(history, nested, root)
    partial.filename = "nested/video.mp4"
    partial.folder = "other"
    await history.put(Download(info=partial))
    await asyncio.wait_for(history.flush(), 5)
    history._dict.clear()
    request = make_mocked_request("POST", "/api/file/actions")
    monkeypatch.setattr(
        request,
        "json",
        AsyncMock(return_value=[{"action": "rename", "path": "nested/video.mp4", "new_name": "new.mp4"}]),
    )
    notify = Mock()
    config = SimpleNamespace(download_path=str(root), browser_control_enabled=True)
    queue = Services.get_instance().get("queue")
    response = await path_actions(request, config, queue, notify)
    assert response.status == 200
    await asyncio.wait_for(history.flush(), 5)
    renamed = media.with_name("new.mp4")
    stored = await history._connection.get_by_id(StoreType.HISTORY.value, selected._id)
    untouched = await history._connection.get_by_id(StoreType.HISTORY.value, unrelated._id)
    nested_record = await history._connection.get_by_id(StoreType.HISTORY.value, partial._id)
    assert stored and stored.filename == "new.mp4"
    assert stored.folder == selected.folder and stored.download_dir == selected.download_dir
    assert stored.sidecar["subtitle"][0]["file"] == str(renamed.with_suffix(".en.srt"))
    assert untouched and untouched.filename == "video.mp4" and untouched.folder == "other"
    assert nested_record and nested_record.filename == "nested/video.mp4" and nested_record.folder == "other"
    assert nested.read_bytes() == b"different file"
    assert renamed.read_bytes() == b"original" and other.read_bytes() == b"original"
    assert not media.exists() and not subtitle.exists()
    notify.emit.assert_called_once()
    assert notify.emit.call_args.args[0] == Events.ITEM_UPDATED
    assert notify.emit.call_args.kwargs["data"]._id == selected._id


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["success", "failure", "cancel", "collision", "publish", "post", "untracked"])
@pytest.mark.parametrize("overwrite_source", [True, False])
async def test_remux_history(
    toolbox: Toolbox,
    history: DataStore,
    source: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal,
    mode: str,
    overwrite_source: bool,
) -> None:
    root = source.parent
    media, other = root / "nested/video.mkv", root / "other/video.mkv"
    for file in (media, other):
        file.parent.mkdir()
        file.write_bytes(b"original")
    media.with_suffix(".en.srt").write_bytes(b"subtitle")
    selected = await save(history, media, root) if mode != "untracked" else None
    unrelated = await save(history, other, root)
    history._dict.clear()
    find = AsyncMock(wraps=history.get_by_file)
    monkeypatch.setattr(history, "get_by_file", find)
    notify = Mock()
    monkeypatch.setattr(EventBus.get_instance(), "emit", notify)
    entered, release = asyncio.Event(), asyncio.Event()
    target = media.with_suffix(".mp4") if overwrite_source else media.with_name("video.remux.mp4")
    if mode == "collision":
        target.write_bytes(b"unrelated")
    if mode == "publish":
        replace = Path.replace

        def replace_file(self: Path, destination: Path) -> Path:
            if destination == target:
                raise OSError(errno.EIO, "publish failed")
            return replace(self, destination)

        monkeypatch.setattr(Path, "replace", replace_file)

    async def run(_: Context, _binary: str, args: list[str], _duration: float | None = None) -> None:
        Path(args[-1]).write_bytes(b"remuxed")
        if mode == "failure":
            raise ToolboxError("Operation failed", "TOOL_FAILED")
        if mode == "cancel":
            entered.set()
            await asyncio.wait_for(release.wait(), 5)

    monkeypatch.setattr(Context, "run", run)
    if mode == "post":
        monkeypatch.setitem(
            tools.TOOLS,
            "remux",
            dataclasses.replace(tools.TOOLS["remux"], post=AsyncMock(side_effect=ValueError("Output rejected."))),
        )
    try:
        accepted = await toolbox.submit(
            Submission(tool="remux", file="nested/video.mkv", extra=Extra(overwrite_source=overwrite_source))
        )
        if mode == "cancel":
            await asyncio.wait_for(entered.wait(), 5)
            await toolbox.cancel(accepted.id)
        job = await terminal(accepted.id)
        assert job.status == (
            "failed"
            if mode in {"failure", "collision", "publish", "post"}
            else "cancelled"
            if mode == "cancel"
            else "succeeded"
        )
        await asyncio.wait_for(history.flush(), 5)
        if selected:
            stored = await history._connection.get_by_id(StoreType.HISTORY.value, selected._id)
            assert stored
            assert stored.folder == selected.folder and stored.download_dir == selected.download_dir
            if mode == "success" and overwrite_source:
                assert stored.filename == "video.mp4" and not media.exists()
                assert media.with_suffix(".mp4").read_bytes() == b"remuxed"
                assert stored.sidecar["subtitle"][0]["file"] == str(media.with_suffix(".en.srt"))
                find.assert_awaited_once_with(media, root)
                notify.assert_called_once()
                assert notify.call_args.args[0] == Events.ITEM_UPDATED
                assert notify.call_args.kwargs["data"]._id == selected._id
            else:
                assert (
                    stored.filename == selected.filename
                    and stored.sidecar == selected.to_download_model("done").data["sidecar"]
                )
                assert media.read_bytes() == b"original"
                if mode == "publish" and overwrite_source:
                    find.assert_awaited_once_with(media, root)
                else:
                    find.assert_not_awaited()
                notify.assert_not_called()
        else:
            assert media.exists() != overwrite_source and target.read_bytes() == b"remuxed"
            notify.assert_not_called()
        untouched = await history._connection.get_by_id(StoreType.HISTORY.value, unrelated._id)
        assert untouched and untouched.filename == unrelated.filename and untouched.folder == "other"
        assert other.read_bytes() == b"original"
        if mode == "collision":
            assert job.error == "The output name already exists."
            assert target.read_bytes() == b"unrelated"
        if mode == "publish":
            assert not target.exists()
        if mode in {"success", "untracked"} and not overwrite_source:
            assert job.result and job.result.outputs == ["nested/video.remux.mp4"]
            assert target.read_bytes() == b"remuxed" and media.read_bytes() == b"original"
        assert not list(root.rglob("*.part"))
        assert not list((root / "work").iterdir())
    finally:
        release.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["success", "failure", "cancel"])
@pytest.mark.parametrize("overwrite_source", [True, False])
async def test_staged_move(
    toolbox: Toolbox,
    history: DataStore,
    source: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal,
    mode: str,
    overwrite_source: bool,
) -> None:
    media = source.with_name("tracked.mkv")
    media.write_bytes(b"original")
    info = await save(history, media, source.parent)
    history._dict.clear()
    find = AsyncMock(wraps=history.get_by_file)
    monkeypatch.setattr(history, "get_by_file", find)
    notify = Mock()
    monkeypatch.setattr(EventBus.get_instance(), "emit", notify)
    target = media.with_suffix(".mp4") if overwrite_source else media.with_name("tracked.remux.mp4")
    entered, exited, settling = asyncio.Event(), asyncio.Event(), asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    original_move, original_settle = tools.shutil.move, tools.process.settle
    moves: list[tuple[Path, Path]] = []

    def move(temporary: Path, stage: Path) -> None:
        try:
            stage.write_bytes(b"partial")
            moves.append((temporary, stage))
            loop.call_soon_threadsafe(entered.set)
            if not release.wait(5):
                raise TimeoutError("Test did not release the move.")
            if mode == "failure":
                raise OSError(errno.ENOSPC, "copy failed")
            original_move(temporary, stage)
        finally:
            loop.call_soon_threadsafe(exited.set)

    async def settle(task):
        settling.set()
        return await original_settle(task)

    async def run(_: Context, _binary: str, args: list[str], _duration: float | None = None) -> None:
        Path(args[-1]).write_bytes(b"remuxed")

    monkeypatch.setattr(tools.shutil, "move", move)
    monkeypatch.setattr(tools.process, "settle", settle)
    monkeypatch.setattr(Context, "run", run)
    try:
        accepted = await toolbox.submit(
            Submission(tool="remux", file=media.name, extra=Extra(overwrite_source=overwrite_source))
        )
        await asyncio.wait_for(entered.wait(), 5)
        temporary, stage = moves[0]
        assert temporary.parent.parent == Path(toolbox.config.temp_path)
        assert stage.parent == target.parent and stage.name.startswith(".") and stage.suffix == ".part"
        assert len(stage.stem) == 33 and int(stage.stem[1:], 16) >= 0
        assert stage.read_bytes() == b"partial" and temporary.read_bytes() == b"remuxed"
        assert not target.exists() and media.read_bytes() == b"original"
        if mode == "cancel":
            await toolbox.cancel(accepted.id)
            await asyncio.wait_for(settling.wait(), 5)
            assert toolbox.execution is not None and not toolbox.execution.done()
            assert stage.exists() and temporary.exists()
            await toolbox.cancel(accepted.id)
        release.set()
        job = await terminal(accepted.id)
        assert job.status == {"success": "succeeded", "failure": "failed", "cancel": "cancelled"}[mode]
        await asyncio.wait_for(history.flush(), 5)
        stored = await history._connection.get_by_id(StoreType.HISTORY.value, info._id)
        assert stored
        if mode == "success":
            assert target.read_bytes() == b"remuxed"
            assert job.result and job.result.outputs == [target.name]
        else:
            assert not target.exists() and media.read_bytes() == b"original"
            assert job.result is None
        if mode == "failure":
            assert job.error_code == "DISK_FULL"
        if mode == "success" and overwrite_source:
            assert stored.filename == target.name and not media.exists()
            notify.assert_called_once_with(Events.ITEM_UPDATED, data=history._dict[info._id].info)
        else:
            assert stored.filename == media.name and media.read_bytes() == b"original"
            notify.assert_not_called()
        if overwrite_source:
            find.assert_awaited_once_with(media, source.parent)
        else:
            find.assert_not_awaited()
        assert not stage.exists() and not temporary.parent.exists()
    finally:
        release.set()
        if entered.is_set():
            await asyncio.wait_for(exited.wait(), 5)
        await asyncio.wait_for(toolbox.shutdown(), 5)


@pytest.mark.asyncio
async def test_committed_history(
    toolbox: Toolbox, history: DataStore, source: Path, monkeypatch: pytest.MonkeyPatch, terminal
) -> None:
    media = source.with_name("tracked.mkv")
    target = media.with_suffix(".mp4")
    media.write_bytes(b"original")
    info = await save(history, media, source.parent)
    history._dict.clear()
    update = history.update_file
    entered, release = asyncio.Event(), asyncio.Event()
    notify = Mock()
    monkeypatch.setattr(EventBus.get_instance(), "emit", notify)

    async def update_file(*args) -> None:
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        await update(*args)

    async def run(_: Context, _binary: str, args: list[str], _duration: float | None = None) -> None:
        Path(args[-1]).write_bytes(b"remuxed")

    monkeypatch.setattr(history, "update_file", update_file)
    monkeypatch.setattr(Context, "run", run)
    try:
        accepted = await toolbox.submit(Submission(tool="remux", file=media.name))
        await asyncio.wait_for(entered.wait(), 5)
        assert not media.exists() and target.read_bytes() == b"remuxed"
        await toolbox.cancel(accepted.id)
        release.set()
        assert (await terminal(accepted.id)).status == "succeeded"
        await asyncio.wait_for(history.flush(), 5)
        stored = await history._connection.get_by_id(StoreType.HISTORY.value, info._id)
        assert stored and stored.filename == target.name
        notify.assert_called_once()
    finally:
        release.set()
