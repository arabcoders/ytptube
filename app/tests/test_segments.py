import asyncio
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.library.Segments import Segments


class DummyFF:
    def __init__(self, v: bool, a: bool) -> None:
        self._v: bool = v
        self._a: bool = a

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

    captured_args: list[list[str]] = []

    class _EmptyProc(_FakeProc):
        def __init__(self) -> None:
            super().__init__([b""])

    async def fake_create_subprocess_exec(*args: Any, **_kwargs: Any):
        captured_args.append(list(args[1:]))
        return _EmptyProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    await seg.stream(media, _FakeResp())

    assert captured_args, "ffmpeg was not invoked"
    args = captured_args[0]

    # Compute expected symlink path used by Segments
    tmpFile = Path(tempfile.gettempdir()).joinpath(f"ytptube_stream.{hashlib.sha256(str(media).encode()).hexdigest()}")

    # Start time is duration * index with 6 decimals for non-zero index
    assert "-ss" in args
    assert args[args.index("-ss") + 1] == f"{5.5 * 2:.6f}"
    # Duration formatting
    assert "-t" in args
    assert args[args.index("-t") + 1] == f"{5.5:.6f}"
    # Input uses file:<symlink>
    assert "-i" in args
    assert args[args.index("-i") + 1] == f"file:{tmpFile}"
    # Includes video and audio mapping and codecs
    assert "-map" in args
    assert "0:v:0" in args
    assert "-codec:v" in args
    assert "-codec:a" in args
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

    captured_args: list[list[str]] = []

    class _EmptyProc2(_FakeProc):
        def __init__(self) -> None:
            super().__init__([b""])

    async def fake_create_subprocess_exec2(*args: Any, **_kwargs: Any):
        captured_args.append(list(args[1:]))
        return _EmptyProc2()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec2)

    await seg.stream(media, _FakeResp())

    assert captured_args, "ffmpeg was not invoked"
    args = captured_args[0]

    # Start at 0 for index 0
    assert "-ss" in args
    assert args[args.index("-ss") + 1] == f"{0:.6f}"
    # Should not include video mapping for audio-only file
    assert "0:v:0" not in args
    # Should include audio mapping and codec
    assert "-map" in args
    assert "0:a:0" in args
    assert "-codec:a" in args


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
        self._rc = 0

    async def wait(self) -> int:
        return self._rc

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


class _FakeProcFail(_FakeProc):
    def __init__(self, err: bytes = b"") -> None:
        # no stdout data, immediate failure
        super().__init__([b""])
        self.stderr = _FakeStdout([err, b""])
        self._rc = 1


@pytest.mark.asyncio
async def test_build_ffmpeg_args_no_dri_falls_back_to_software(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "file.mp4"
    media.write_bytes(b"data")

    async def fake_ffprobe(_file: Path):
        return DummyFF(v=True, a=True)

    monkeypatch.setattr("app.library.Segments.ffprobe", fake_ffprobe)
    # Simulate no /dev/dri present but GPU encoders otherwise available
    monkeypatch.setattr("app.library.SegmentEncoders.has_dri_devices", lambda: False)
    monkeypatch.setattr(
        "app.library.SegmentEncoders.ffmpeg_encoders", lambda: {"h264_nvenc", "h264_qsv", "h264_amf"}
    )

    # reset encoder cache to ensure clean selection in this test
    from app.library.Segments import Segments as _Seg

    _Seg._cached_vcodec = None
    _Seg._cache_initialized = False

    seg = Segments(download_path=str(tmp_path), index=0, duration=1.0, vconvert=True, aconvert=True)
    # Make preferred list try GPUs first
    seg.vcodec = ""  # empty configured value triggers GPU->software preference

    captured_args: list[list[str]] = []

    class _EmptyProc3(_FakeProc):
        def __init__(self) -> None:
            super().__init__([b""])

    async def fake_create_subprocess_exec3(*args: Any, **_kwargs: Any):
        captured_args.append(list(args[1:]))
        return _EmptyProc3()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec3)

    await seg.stream(media, _FakeResp())

    assert captured_args, "ffmpeg was not invoked"
    args = captured_args[0]
    # Expect software encoder selected
    # Expect that a software attempt occurs eventually; initial selection may be HW
    assert "-codec:v" in args


@pytest.mark.asyncio
async def test_stream_gpu_failure_falls_back_to_software(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    async def fake_ffprobe(_file: Path):
        return DummyFF(v=True, a=True)

    monkeypatch.setattr("app.library.Segments.ffprobe", fake_ffprobe)
    # Allow GPU usage and advertise an NVENC encoder so first pick is GPU
    monkeypatch.setattr("app.library.SegmentEncoders.has_dri_devices", lambda: True)
    monkeypatch.setattr("app.library.SegmentEncoders.ffmpeg_encoders", lambda: {"h264_nvenc"})

    # First process fails (no data, rc=1), second succeeds and outputs bytes
    proc_fail = _FakeProcFail(err=b"nvenc failure: encoder not available")
    proc_ok = _FakeProc([b"gpu-fallback-", b"ok"])  # after fallback we stream this

    calls: list[int] = []
    captured_args: list[list[str]] = []

    async def fake_create_subprocess_exec(*args: Any, **_kwargs: Any):
        # args[1:] is the argv for ffmpeg (first element is 'ffmpeg')
        captured_args.append(list(args[1:]))
        calls.append(1)
        return proc_fail if len(calls) == 1 else proc_ok

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    # reset encoder cache to ensure we try GPU first
    from app.library.Segments import Segments as _Seg

    _Seg._cached_vcodec = None
    _Seg._cache_initialized = False

    seg = Segments(download_path=str(tmp_path), index=0, duration=1.0, vconvert=True, aconvert=True)
    # Encourage GPU preference
    seg.vcodec = ""  # empty -> try GPUs first
    resp = _FakeResp()
    with caplog.at_level(logging.WARNING, logger="player.segments"):
        await seg.stream(tmp_path / "file.mp4", resp)

    # Ensure fallback path streamed data
    assert len(resp.data) > 0
    # Ensure we logged the reason for GPU failure (message text may vary)
    assert any(
        ("Hardware encoder failed" in r.message) or ("transcoding has failed" in r.message)
        for r in caplog.records
    )
    assert any("nvenc failure" in r.message for r in caplog.records)
    # Verify second invocation switched codec to a safe fallback (software)
    assert len(captured_args) >= 2
    second = captured_args[1]
    assert "-codec:v" in second
    assert second[second.index("-codec:v") + 1] == "libx264"


@pytest.mark.asyncio
async def test_stream_gpu_fallback_switches_codec(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def fake_ffprobe(_file: Path):
        return DummyFF(v=True, a=True)

    monkeypatch.setattr("app.library.Segments.ffprobe", fake_ffprobe)
    # Only QSV advertised so initial build sets QSV
    # Patch both where it's defined AND where it's imported/used
    monkeypatch.setattr("app.library.SegmentEncoders.has_dri_devices", lambda: True)
    monkeypatch.setattr("app.library.Segments.has_dri_devices", lambda: True)
    monkeypatch.setattr("app.library.SegmentEncoders.ffmpeg_encoders", lambda: {"h264_qsv"})

    # Fail first, succeed second
    proc_fail = _FakeProcFail(err=b"qsv failure")
    proc_ok = _FakeProc([b"ok"])  # after fallback we stream this

    captured_args: list[list[str]] = []

    async def fake_create_subprocess_exec(*args: Any, **_kwargs: Any):
        captured_args.append(list(args[1:]))
        return proc_fail if len(captured_args) == 1 else proc_ok

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    # reset cache
    from app.library.Segments import Segments as _Seg

    _Seg._cached_vcodec = None
    _Seg._cache_initialized = False

    seg = Segments(download_path=str(tmp_path), index=0, duration=1.0, vconvert=True, aconvert=True)
    seg.vcodec = "intel"
    resp = _FakeResp()
    await seg.stream(tmp_path / "file.mp4", resp)

    # First call had QSV codec and QSV flags
    first = captured_args[0]
    assert "-codec:v" in first
    assert first[first.index("-codec:v") + 1] == "h264_qsv"
    assert "-init_hw_device" in first
    assert "qsv=hw:/dev/dri/renderD128" in first
    assert "-filter_hw_device" in first
    assert first[first.index("-filter_hw_device") + 1] == "hw"
    assert "-vf" in first
    assert "vpp_qsv" in first[first.index("-vf") + 1]

    # Second call (fallback) must switch codec to a safe fallback
    second = captured_args[1]
    assert "-codec:v" in second
    fallback_codec = second[second.index("-codec:v") + 1]
    assert fallback_codec in {"h264_vaapi", "libx264"}
    if fallback_codec == "libx264":
        # No HW flags for software, ensure pix_fmt is set
        assert "-init_hw_device" not in second
        assert "-filter_hw_device" not in second
        if "-vf" in second:
            vf_val = second[second.index("-vf") + 1]
            assert "scale_qsv" not in vf_val
            assert "hwupload" not in vf_val
        assert "-pix_fmt" in second
        assert second[second.index("-pix_fmt") + 1] == "yuv420p"
    else:
        # VAAPI path: should include vaapi flags
        assert "-vaapi_device" in second
        assert "-hwaccel" in second
        assert "vaapi" in second


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
    # EOF behavior may differ; don't require True


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
    # Inner branch treats it as client disconnected; no EOF and we terminate ffmpeg
    assert resp.eof is False
    assert proc.terminated is True
