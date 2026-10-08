from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.features.streaming.library import ffprobe as module
from app.features.streaming import utils
from app.features.streaming.types import FFProbeError


@pytest.fixture(autouse=True)
def _probe_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "ffprobe_bin", lambda: "fake-ffprobe")
    module._probe.cache_clear()


@pytest.mark.asyncio
async def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        await module.ffprobe(tmp_path / "missing.mp4")


@pytest.mark.asyncio
async def test_missing_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file = tmp_path / "video.mp4"
    file.touch()
    monkeypatch.setattr(module, "ffprobe_bin", lambda: None)
    with pytest.raises(FFProbeError):
        await module.ffprobe(file)


@pytest.mark.asyncio
async def test_generation_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file = tmp_path / "video.mp4"
    file.write_bytes(b"source")
    run = AsyncMock(return_value=(0, b'{"format":{"duration":"13"},"streams":[]}', ""))
    monkeypatch.setattr(utils, "run", run)
    first = await module.ffprobe(file)
    second = await module.ffprobe(str(file))
    assert first.serialize() == second.serialize()
    assert run.await_count == 1
    file.write_bytes(b"replacement-source")
    await module.ffprobe(file)
    assert run.await_count == 2


@pytest.mark.asyncio
async def test_probe_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file = tmp_path / "video.mp4"
    file.touch()
    monkeypatch.setattr(utils, "run", AsyncMock(return_value=(1, b"", "invalid media")))
    with pytest.raises(FFProbeError):
        await module.ffprobe(file)


def test_probe_streams() -> None:
    result = module.FFProbeResult()
    result.deserialize(
        {
            "metadata": {"duration": "13"},
            "video": [{"index": 0, "codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080}],
            "audio": [{"index": 1, "codec_type": "audio", "codec_name": "aac"}],
        }
    )
    assert result.has_video() and result.has_audio()
    assert result.video[0].frame_size() == (1920, 1080)
    assert result.serialize()["metadata"] == {"duration": "13"}
