import asyncio
import hashlib
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.library.Segments import Segments


class DummyFF:
    def __init__(self, v: bool, a: bool) -> None:
        self._v = v
        self._a = a

    def has_video(self) -> bool:
        return self._v

    def has_audio(self) -> bool:
        return self._a


@pytest.mark.asyncio
async def test_build_ffmpeg_args_video_and_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Create a dummy media file
    media = tmp_path / "file.mp4"
    media.write_bytes(b"data")

    # Patch ffprobe to report both video and audio
    async def fake_ffprobe(_file: Path):
        return DummyFF(v=True, a=True)

    monkeypatch.setattr("app.library.Segments.ffprobe", fake_ffprobe)

    seg = Segments(download_path=str(tmp_path), index=2, duration=5.5, vconvert=False, aconvert=False)

    args = await seg.build_ffmpeg_args(media)

    # Compute expected symlink path used by Segments
    tmpFile = Path(tempfile.gettempdir()).joinpath(
        f"ytptube_stream.{hashlib.sha256(str(media).encode()).hexdigest()}"
    )

    # Start time is duration * index with 6 decimals for non-zero index
    assert "-ss" in args
    assert args[args.index("-ss") + 1] == f"{5.5 * 2:.6f}"
    # Duration formatting
    assert "-t" in args
    assert args[args.index("-t") + 1] == f"{5.5:.6f}"
    # Input uses file:<symlink>
    assert "-i" in args
    assert args[args.index("-i") + 1] == f"file:{tmpFile}"
    # Includes video and audio mapping and codecs, forced convert True in __init__
    assert "-map" in args
    assert "0:v:0" in args
    assert "-codec:v" in args
    assert seg.vcodec in args
    assert "-codec:a" in args
    assert seg.acodec in args
    # Output format: ensure -f mpegts and pipe:1 present
    assert args[-1] == "pipe:1"
    assert "-f" in args
    assert args[args.index("-f") + 1] == "mpegts"


@pytest.mark.asyncio
async def test_build_ffmpeg_args_audio_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "file.mp3"
    media.write_bytes(b"data")

    async def fake_ffprobe(_file: Path):
        return DummyFF(v=False, a=True)

    monkeypatch.setattr("app.library.Segments.ffprobe", fake_ffprobe)

    seg = Segments(download_path=str(tmp_path), index=0, duration=9.0, vconvert=False, aconvert=False)
    args = await seg.build_ffmpeg_args(media)

    # Start at 0 for index 0
    assert "-ss" in args
    assert args[args.index("-ss") + 1] == f"{0:.6f}"
    # Should not include video mapping
    assert "0:v:0" not in args
    # Should include audio mapping and codec
    assert "-map" in args
    assert "0:a:0" in args
    assert "-codec:a" in args
    assert seg.acodec in args


class _FakeStdout:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def read(self, _size: int) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class _FakeProc:
    def __init__(self, chunks: list[bytes]) -> None:
        self.stdout = _FakeStdout(chunks)
        self.stderr = _FakeStdout([])
        self.terminated = False
        self.killed = False

    async def wait(self) -> int:
        return 0

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


class _FakeResp:
    def __init__(self, fail_with: Exception | None = None) -> None:
        self.data: bytearray = bytearray()
        self.eof = False
        self._exc = fail_with

    async def write(self, data: bytes) -> None:
        if self._exc:
            raise self._exc
        self.data.extend(data)

    async def write_eof(self) -> None:
        self.eof = True


@pytest.mark.asyncio
async def test_stream_normal_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_ffprobe(_file: Path):
        return DummyFF(v=True, a=True)

    monkeypatch.setattr("app.library.Segments.ffprobe", fake_ffprobe)

    # Process that yields two chunks and then EOF
    proc = _FakeProc([b"abc", b"def", b""])

    async def fake_create_subprocess_exec(*_args: Any, **_kwargs: Any):
        return proc

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    seg = Segments(download_path=str(tmp_path), index=0, duration=1.0, vconvert=True, aconvert=True)
    resp = _FakeResp()
    await seg.stream(tmp_path / "file.mp4", resp)

    assert bytes(resp.data) == b"abcdef"
    assert resp.eof is True


@pytest.mark.asyncio
async def test_stream_client_reset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_ffprobe(_file: Path):
        return DummyFF(v=True, a=True)

    monkeypatch.setattr("app.library.Segments.ffprobe", fake_ffprobe)

    proc = _FakeProc([b"abc", b"def"])  # will attempt to write and fail

    async def fake_create_subprocess_exec(*_args: Any, **_kwargs: Any):
        return proc

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    seg = Segments(download_path=str(tmp_path), index=0, duration=1.0, vconvert=True, aconvert=True)
    resp = _FakeResp(fail_with=ConnectionResetError())

    await seg.stream(tmp_path / "file.mp4", resp)

    # Should not write EOF due to client disconnect
    assert resp.eof is False


@pytest.mark.asyncio
async def test_stream_cancelled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_ffprobe(_file: Path):
        return DummyFF(v=True, a=True)

    monkeypatch.setattr("app.library.Segments.ffprobe", fake_ffprobe)

    proc = _FakeProc([b"abc"])  # only one chunk

    async def fake_create_subprocess_exec(*_args: Any, **_kwargs: Any):
        return proc

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    seg = Segments(download_path=str(tmp_path), index=0, duration=1.0, vconvert=True, aconvert=True)
    # Fail with CancelledError on write to hit inner disconnection branch
    resp = _FakeResp(fail_with=asyncio.CancelledError())
    await seg.stream(tmp_path / "file.mp4", resp)
    # Inner branch treats it as client disconnected; no EOF and no termination
    assert resp.eof is False
    assert proc.terminated is False
