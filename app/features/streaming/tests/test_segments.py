from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.features.streaming.library.ffprobe import FFProbeResult
from app.features.streaming.types import StreamingError
from app.features.streaming.utils import Segments, segment_window


@pytest.fixture
def probe() -> FFProbeResult:
    result = FFProbeResult()
    result.deserialize(
        {
            "metadata": {"duration": "13"},
            "video": [{"index": 1, "codec_type": "video", "codec_name": "h264"}],
            "audio": [
                {"index": 0, "codec_type": "audio", "codec_name": "aac"},
                {"index": 4, "codec_type": "audio", "codec_name": "aac", "disposition": {"default": 1}},
            ],
        }
    )
    return result


@pytest.mark.asyncio
async def test_final_segment(tmp_path: Path, probe: FFProbeResult) -> None:
    segment = Segments(2, probe=probe, audio=4)
    args = await segment.build_ffmpeg_args(tmp_path / "video.mp4", "libx264")
    assert args[args.index("-ss") + 1] == "12.000000"
    assert args[args.index("-t") + 1] == "1.000000"
    assert "0:4" in args
    assert "0:1" in args, "video must use its absolute stream index when audio is the first source stream"
    assert segment_window(1, 13) == (6, 6)


@pytest.mark.parametrize(
    "index,duration", [(-1, 13), (3, 13), (True, 13), (0, float("nan")), (0, float("inf")), (0, 0)]
)
def test_invalid_windows(index: int, duration: float) -> None:
    with pytest.raises(StreamingError):
        segment_window(index, duration)


@pytest.mark.asyncio
async def test_validated_audio(tmp_path: Path, probe: FFProbeResult) -> None:
    segment = Segments(0, probe=probe, audio=2)
    with pytest.raises(StreamingError, match="Unknown audio"):
        await segment.build_ffmpeg_args(tmp_path / "video.mp4", "libx264")


@pytest.mark.asyncio
async def test_prepared_fallback(tmp_path: Path, probe: FFProbeResult, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.streaming.utils.ffmpeg_bin", lambda: "fake-ffmpeg")
    monkeypatch.setattr("app.features.streaming.utils.select_encoder", AsyncMock(return_value="h264_nvenc"))
    Segments._encoders.clear()
    artifacts = []
    attempts = []

    async def run(_binary: str, args: list[str], *, output: Path, **_kwargs) -> tuple[int, bytes, str]:
        if artifacts:
            assert not artifacts[-1].exists(), "failed bytes must be discarded before fallback"
        artifacts.append(output)
        attempts.append(args[args.index("-codec:v") + 1])
        output.write_bytes(b"failed-prefix" if len(artifacts) == 1 else b"complete-segment")
        return (1, b"", "hardware unavailable") if len(artifacts) == 1 else (0, b"", "")

    monkeypatch.setattr("app.features.streaming.utils.run", run)
    segment = Segments(0, probe=probe)
    artifact = await segment.prepare(tmp_path / "video.mp4", tmp_path)
    assert artifact.read_bytes() == b"complete-segment"
    assert artifacts[0] != artifacts[1]
    assert attempts == ["h264_nvenc", "libx264"]


@pytest.mark.asyncio
async def test_empty_output(tmp_path: Path, probe: FFProbeResult, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.streaming.utils.ffmpeg_bin", lambda: "fake-ffmpeg")
    monkeypatch.setattr("app.features.streaming.utils.select_encoder", AsyncMock(return_value="libx264"))
    monkeypatch.setattr("app.features.streaming.utils.run", AsyncMock(return_value=(0, b"", "")))
    Segments._encoders.clear()
    segment = Segments(0, probe=probe)
    with pytest.raises(StreamingError, match="Unable to prepare"):
        await segment.prepare(tmp_path / "video.mp4", tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_cached_encoder_failure(tmp_path: Path, probe: FFProbeResult, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.streaming.utils.ffmpeg_bin", lambda: "fake-ffmpeg")
    select = AsyncMock(return_value="h264_nvenc")
    monkeypatch.setattr("app.features.streaming.utils.select_encoder", select)
    Segments._encoders.clear()
    attempts = []

    async def run(_binary: str, args: list[str], *, output: Path, **_kwargs) -> tuple[int, bytes, str]:
        codec = args[args.index("-codec:v") + 1]
        attempts.append(codec)
        output.write_bytes(b"prepared")
        return (1 if len(attempts) == 2 else 0), b"", "runtime hardware failure"

    monkeypatch.setattr("app.features.streaming.utils.run", run)
    for _ in range(2):
        segment = Segments(0, probe=probe)
        artifact = await segment.prepare(tmp_path / "video.mp4", tmp_path)
        artifact.unlink()
    assert attempts == ["h264_nvenc", "h264_nvenc", "libx264"]
    assert select.await_count == 1
