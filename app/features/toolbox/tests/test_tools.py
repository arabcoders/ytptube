from __future__ import annotations

import asyncio
import errno
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.features.core.models import utcnow
from app.features.streaming.library import ffprobe as probe_module
from app.features.streaming.types import FFProbeError
from app.features.toolbox import service, tools
from app.features.toolbox.schemas import Extra, Job, Submission
from app.features.toolbox.service import Context, Toolbox, ToolboxError
from app.library.Services import Services


def context(toolbox: Toolbox, source: Path, identifier: int = 1, *, overwrite_source: bool = True) -> Context:
    return Context(
        service=toolbox,
        source=source,
        job=Job(
            id=identifier,
            tool="remux",
            file=source.name,
            extra=Extra(overwrite_source=overwrite_source),
            status="running",
            created_at=utcnow(),
        ),
    )


async def inspect_output(file: Path) -> dict:
    code, data, log = await service.process.run(
        "ffprobe",
        ["-v", "error", "-of", "json", "-show_streams", "-show_chapters", str(file)],
        deadline=10,
        max_bytes=65536,
    )
    assert code == 0, log
    return json.loads(data)


def test_unique_workspace(toolbox: Toolbox, source: Path) -> None:
    first, second = context(toolbox, source), context(toolbox, source)
    try:
        folder = first.workspace()
        assert folder.parent == Path(toolbox.config.temp_path)
        (folder / "partial").write_bytes(b"incomplete")
        assert second.workspace() != folder
    finally:
        first.cleanup()
        second.cleanup()
    assert not folder.exists() and source.read_bytes() == b"original"


@pytest.mark.parametrize("overwrite_source", [True, False])
def test_tool_destination(toolbox: Toolbox, source: Path, overwrite_source: bool) -> None:
    ctx = context(toolbox, source, overwrite_source=overwrite_source)
    expected = "video.webm" if overwrite_source else "video.converted.webm"
    assert ctx.destination(".webm", ".converted") == source.with_name(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("overwrite_source", [True, False])
@pytest.mark.parametrize("suffix", [".mp4", ".mkv"])
async def test_media_publish(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, overwrite_source: bool, suffix: str
) -> None:
    source = source.rename(source.with_suffix(suffix))
    source.chmod(0o640)
    ctx = context(toolbox, source, overwrite_source=overwrite_source)
    commands = []

    async def run(_: Context, binary: str, args: list[str], _duration: float | None = None) -> None:
        commands.append((binary, args))
        Path(args[-1]).write_bytes(b"new-media")

    monkeypatch.setattr(Context, "run", run)
    try:
        result = await toolbox.execute(ctx)
    finally:
        ctx.cleanup()
    expected = source.with_suffix(".mp4").name if overwrite_source else f"{source.stem}.remux.mp4"
    assert result.outputs == [expected]
    assert (source.parent / result.outputs[0]).read_bytes() == b"new-media"
    if overwrite_source and suffix != ".mp4":
        assert not source.exists()
    else:
        assert source.read_bytes() == (b"new-media" if overwrite_source else b"original")
    assert (source.parent / expected).stat().st_mode & 0o777 == 0o640
    assert ctx.folder is not None and not ctx.folder.exists()
    args = commands[0][1]
    assert args[args.index("-map") + 1] == "0" and "-n" in args and "-nostdin" in args
    assert args[args.index("-c") + 1] == "copy"
    assert args[args.index("-movflags") + 1] == "+faststart"
    await toolbox.repo.save(ctx.job.model_copy(update={"status": "succeeded", "result": result}))
    await toolbox.delete(ctx.job.id)
    assert await toolbox.repo.get(ctx.job.id) is None
    assert (source.parent / result.outputs[0]).read_bytes() == b"new-media"


@pytest.mark.asyncio
@pytest.mark.parametrize("overwrite_source", [True, False])
async def test_cross_filesystem(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, overwrite_source: bool
) -> None:
    ctx = context(toolbox, source, overwrite_source=overwrite_source)
    original_rename = os.rename

    def rename(file: Path, target: Path) -> None:
        if Path(file).name == "output.part.mp4":
            raise OSError(errno.EXDEV, "different filesystems")
        original_rename(file, target)

    async def run(_: Context, _binary: str, args: list[str], _duration: float | None = None) -> None:
        Path(args[-1]).write_bytes(b"new-media")

    monkeypatch.setattr(Context, "run", run)
    monkeypatch.setattr(os, "rename", rename)
    try:
        result = await toolbox.execute(ctx)
    finally:
        ctx.cleanup()
    assert (source.parent / result.outputs[0]).read_bytes() == b"new-media"
    assert source.read_bytes() == (b"new-media" if overwrite_source else b"original")
    assert not list(source.parent.rglob("*.part"))
    assert not list((source.parent / "work").iterdir())


@pytest.mark.asyncio
async def test_invalid_source(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = context(toolbox, source.with_suffix(".mkv"))
    temporary = source.parent / "output.part.mp4"
    temporary.write_bytes(b"new-media")
    final = source.with_name("output.mp4")
    find = AsyncMock()
    move = Mock(wraps=tools.shutil.move)
    Services.get_instance().add("queue", SimpleNamespace(done=SimpleNamespace(get_by_file=find)))
    monkeypatch.setattr(tools.shutil, "move", move)
    try:
        with pytest.raises(ToolboxError) as error:
            await tools.publish(ctx, temporary, final)
        assert error.value.code == "FILE_UNAVAILABLE"
        move.assert_not_called()
        find.assert_not_awaited()
        assert temporary.read_bytes() == b"new-media" and source.read_bytes() == b"original"
        assert not final.exists() and not ctx.source.exists()
    finally:
        Services.get_instance().remove("queue")


@pytest.mark.asyncio
@pytest.mark.parametrize("collision", [False, True])
@pytest.mark.parametrize("overwrite_source", [True, False])
async def test_extension_replace(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, collision: bool, overwrite_source: bool
) -> None:
    media = source.with_name("input.mkv")
    media.write_bytes(b"original")
    target = media.with_suffix(".mp4") if overwrite_source else media.with_name("input.remux.mp4")
    if collision:
        target.write_bytes(b"unrelated")
    move = Mock(wraps=tools.shutil.move)
    monkeypatch.setattr(tools.shutil, "move", move)

    async def run(_: Context, _binary: str, args: list[str], _duration: float | None = None) -> None:
        Path(args[-1]).write_bytes(b"new-media")

    monkeypatch.setattr(Context, "run", run)
    accepted = await toolbox.submit(
        Submission(tool="remux", file=media.name, extra=Extra(overwrite_source=overwrite_source))
    )
    job = await terminal(accepted.id)
    assert job.file == media.name
    if collision:
        assert job.status == "failed" and job.error and "already exists" in job.error
        move.assert_not_called()
        assert media.read_bytes() == b"original" and target.read_bytes() == b"unrelated"
    else:
        assert job.status == "succeeded" and job.result
        assert job.result.outputs == [target.name]
        assert target.read_bytes() == b"new-media"
        if overwrite_source:
            assert not media.exists()
        else:
            assert media.read_bytes() == b"original"
    assert not list(source.parent.rglob("*.part"))
    assert not list((source.parent / "work").iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["disk-full", "missing"])
async def test_remux_failure(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, failure: str
) -> None:
    async def run(_: Context, _binary: str, args: list[str], _duration: float | None = None) -> None:
        if failure == "disk-full":
            raise OSError(errno.ENOSPC, "No space left")
        Path(args[-1]).write_bytes(b"new")
        if failure == "missing":
            source.unlink()

    monkeypatch.setattr(Context, "run", run)
    accepted = await toolbox.submit(Submission(tool="remux", file=source.name))
    finished = await terminal(accepted.id)
    assert finished.status == "failed" and finished.result is None
    assert not list((source.parent / "work").iterdir())
    if failure == "disk-full":
        assert source.read_bytes() == b"original"
        assert finished.error_code == "DISK_FULL"
    else:
        assert not source.exists()
        assert finished.error_code == "FILE_UNAVAILABLE"
        assert finished.error == f"File '{source.name}' is no longer available."


@pytest.mark.asyncio
async def test_ffmpeg_failure(toolbox: Toolbox, source: Path, terminal) -> None:
    if not shutil.which("ffmpeg"):
        pytest.skip("A local FFmpeg binary is required.")
    accepted = await toolbox.submit(Submission(tool="remux", file=source.name))
    job = await terminal(accepted.id)
    assert job.status == "failed" and job.error_code == "TOOL_FAILED"
    assert source.name in job.log and job.error and "job log" in job.error
    assert source.read_bytes() == b"original"
    assert not list((source.parent / "work").iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize(("elapsed", "expected"), [(6000000, 50), (18000000, 99), (-100, 0)])
async def test_bounded_process(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, elapsed: int, expected: int
) -> None:
    ctx = context(toolbox, source)
    stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
    stdout.feed_data(b"x" * 100000 + f"\nout_time_us={elapsed}\n".encode())
    stdout.feed_eof()
    stderr.feed_data(b"diagnostic" * 10000)
    stderr.feed_eof()
    proc = SimpleNamespace(stdout=stdout, stderr=stderr, wait=AsyncMock(return_value=0))
    spawn, release = AsyncMock(return_value=proc), AsyncMock()
    monkeypatch.setattr(service.process, "spawn", spawn)
    monkeypatch.setattr(service.process, "release", release)
    await asyncio.wait_for(ctx.run("ffmpeg", ["fixed-args"], 12), 5)
    assert len(ctx.job.log) <= service.LOG_LIMIT and "diagnostic" in ctx.job.log
    assert ctx.job.progress == expected
    assert not ctx.unsafe
    release.assert_awaited_once_with(proc)


@pytest.mark.asyncio
async def test_progress_throttle(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = context(toolbox, source)
    emitted: list[Job] = []
    clock = SimpleNamespace(value=0.0, time=lambda: clock.value)
    monkeypatch.setattr(toolbox, "emit", lambda job: emitted.append(job.model_copy(deep=True)))
    with monkeypatch.context() as patch:
        patch.setattr(service.asyncio, "get_running_loop", lambda: clock)
        for value in (0.0, 0.1, 0.49, 0.5, 0.99, 1.0):
            clock.value = value
            ctx.progress(value * 99)
    assert len(emitted) == 3 and ctx.job.progress == 99
    await toolbox.finish(ctx, "succeeded")
    assert len(emitted) == 4 and emitted[-1].progress == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("duration", ["available", "missing", "failed", "invalid"])
async def test_optional_duration(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, duration: str
) -> None:
    if duration == "missing":
        monkeypatch.setattr(probe_module, "ffprobe_bin", lambda: None)
        monkeypatch.setattr(tools, "ffprobe", probe_module.ffprobe)
    elif duration == "failed":
        monkeypatch.setattr(tools, "ffprobe", AsyncMock(side_effect=FFProbeError("Duration unavailable")))
    else:
        metadata = probe_module.FFProbeResult()
        metadata.metadata["duration"] = "12" if duration == "available" else "nan"
        monkeypatch.setattr(tools, "ffprobe", AsyncMock(return_value=metadata))
    stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
    stdout.feed_data(b"out_time_us=6000000\n")
    stdout.feed_eof()
    stderr.feed_eof()
    proc = SimpleNamespace(stdout=stdout, stderr=stderr, wait=AsyncMock(return_value=0))

    async def spawn(_binary: str, args: list[str]):
        Path(args[-1]).write_bytes(b"remuxed")
        return proc

    release = AsyncMock()
    monkeypatch.setattr(service.process, "spawn", spawn)
    monkeypatch.setattr(service.process, "release", release)
    publish = tools.publish
    progress: list[float | None] = []

    async def publish_output(ctx: Context, temporary: Path, final: Path) -> None:
        progress.append(ctx.job.progress)
        await publish(ctx, temporary, final)
        progress.append(ctx.job.progress)

    monkeypatch.setattr(tools, "publish", publish_output)
    assert toolbox.tools()[0]["available"]
    accepted = await toolbox.submit(Submission(tool="remux", file=source.name))
    job = await terminal(accepted.id)
    assert job.status == "succeeded" and job.result and job.result.outputs == [source.name]
    assert source.read_bytes() == b"remuxed"
    expected = 50 if duration == "available" else None
    assert progress == [expected, expected]
    release.assert_awaited_once_with(proc)
    assert not list((source.parent / "work").iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("unconfirmed", [False, True])
async def test_process_cancellation(
    toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, unconfirmed: bool
) -> None:
    entered, releasing, released = asyncio.Event(), asyncio.Event(), asyncio.Event()
    proc = SimpleNamespace(stdout=asyncio.StreamReader(), stderr=asyncio.StreamReader(), wait=AsyncMock(return_value=0))
    folders: list[Path] = []

    async def spawn(_binary: str, _args: list[str]):
        entered.set()
        return proc

    async def release_child(_proc) -> None:
        releasing.set()
        await asyncio.wait_for(released.wait(), 5)
        if unconfirmed:
            raise service.process.ProcessExitError("unconfirmed")

    release = AsyncMock(side_effect=release_child)
    monkeypatch.setattr(service.process, "spawn", spawn)
    monkeypatch.setattr(service.process, "release", release)

    workspace = Context.workspace

    def create_workspace(ctx: Context) -> Path:
        folder = workspace(ctx)
        folders.append(folder)
        return folder

    monkeypatch.setattr(Context, "workspace", create_workspace)
    try:
        accepted = await toolbox.submit(Submission(tool="remux", file=source.name))
        await asyncio.wait_for(entered.wait(), 5)
        (folders[0] / "output.part.mp4").write_bytes(b"partial")
        await toolbox.cancel(accepted.id)
        await asyncio.wait_for(releasing.wait(), 5)
        assert (folders[0] / "output.part.mp4").read_bytes() == b"partial"
        released.set()
        job = await terminal(accepted.id)
        assert job.status == ("interrupted" if unconfirmed else "cancelled")
        assert len(folders) == 1 and folders[0].exists() == unconfirmed
        assert toolbox.blocked == unconfirmed and source.read_bytes() == b"original"
        release.assert_awaited_once_with(proc)
        if unconfirmed:
            with pytest.raises(ToolboxError) as error:
                await toolbox.submit(Submission(tool="remux", file=source.name))
            assert error.value.status == 503
            assert all(not tool["available"] for tool in toolbox.tools())
    finally:
        released.set()


@pytest.mark.asyncio
async def test_chapter_remux(toolbox: Toolbox, source: Path, terminal) -> None:
    binary = shutil.which("ffmpeg")
    if not binary or not shutil.which("ffprobe"):
        pytest.skip("Local FFmpeg and ffprobe binaries are required.")
    chapters = source.with_name("chapters.txt")
    chapters.write_text(";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=1000\ntitle=One\n")
    media = source.with_suffix(".mkv")
    code, _, log = await service.process.run(
        binary,
        [
            "-nostdin",
            "-n",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=16x16:r=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000",
            "-i",
            str(chapters),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-map_metadata",
            "2",
            "-map_chapters",
            "2",
            "-t",
            "1",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            str(media),
        ],
        deadline=10,
        max_bytes=65536,
    )
    assert code == 0, log
    original = media.read_bytes()
    accepted = await toolbox.submit(Submission(tool="remux", file=media.name, extra=Extra(overwrite_source=False)))
    job = await terminal(accepted.id)
    assert job.status == "succeeded", job.error or job.log
    assert job.result
    output = await inspect_output(source.parent / job.result.outputs[0])
    assert output["chapters"][0]["tags"]["title"] == "One"
    streams = output["streams"]
    assert [(s["codec_type"], s["codec_name"]) for s in streams] == [
        ("video", "mpeg4"),
        ("audio", "aac"),
        ("data", "bin_data"),
    ]
    assert media.read_bytes() == original


@pytest.mark.asyncio
@pytest.mark.parametrize("overwrite_source", [True, False])
async def test_faststart_remux(toolbox: Toolbox, source: Path, terminal, overwrite_source: bool) -> None:
    binary = shutil.which("ffmpeg")
    if not binary or not shutil.which("ffprobe"):
        pytest.skip("Local FFmpeg and ffprobe binaries are required.")
    media = source.with_name("input.mp4")
    code, _, log = await service.process.run(
        binary,
        [
            "-nostdin",
            "-n",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=16x16:r=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-map",
            "1:a",
            "-t",
            "1",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            str(media),
        ],
        deadline=10,
        max_bytes=65536,
    )
    assert code == 0, log
    original = media.read_bytes()
    assert original.index(b"moov") > original.index(b"mdat")
    accepted = await toolbox.submit(
        Submission(tool="remux", file=media.name, extra=Extra(overwrite_source=overwrite_source))
    )
    job = await terminal(accepted.id)
    assert job.status == "succeeded", job.error or job.log
    assert job.result
    expected = media.name if overwrite_source else f"{media.stem}.remux.mp4"
    assert job.result.outputs == [expected]
    output = await inspect_output(source.parent / expected)
    assert [(stream["codec_type"], stream["codec_name"]) for stream in output["streams"]] == [
        ("video", "mpeg4"),
        ("audio", "aac"),
        ("audio", "aac"),
    ]
    data = (source.parent / expected).read_bytes()
    assert data.index(b"moov") < data.index(b"mdat")
    assert media.read_bytes() == (data if overwrite_source else original)
    assert not list((source.parent / "work").iterdir())
