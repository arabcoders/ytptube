import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from app.features.streaming import utils
from app.features.streaming.library.ffprobe import FFProbeResult
from app.features.streaming.types import StreamingError
from app.features.streaming.utils import Segments, segment_window
from app.library.config import Config


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
async def test_continuous_args(tmp_path: Path, probe: FFProbeResult) -> None:
    args = await Segments(1, probe=probe).build_ffmpeg_args(tmp_path / "video.mp4", "libx264")
    assert args[args.index("-ss") + 1] == "6.000000"
    assert args[args.index("-t") + 1] == "7.000000", "the encoder must continue beyond the requested segment"
    assert args[args.index("-output_ts_offset") + 1] == "6.000000"
    assert args[args.index("-force_key_frames") + 1] == "expr:gte(t,n_forced*6.000000)"
    assert args[args.index("-bf") + 1] == "0"
    assert args[args.index("-readrate_initial_burst") + 1] == "18.000000"
    assert args[args.index("-hls_flags") + 1] == "single_file+independent_segments"
    assert args[-3:] == ["-hls_segment_filename", "pipe:1", "pipe:2"]


@pytest.mark.asyncio
async def test_bitmap_args(tmp_path: Path, probe: FFProbeResult) -> None:
    probe.deserialize({**probe.serialize(), "subtitle": [{"index": 7, "codec_type": "subtitle"}]})
    args = await Segments(0, probe=probe, subtitle=7).build_ffmpeg_args(tmp_path / "video.mkv", "libx264")
    assert args[args.index("-filter_complex") + 1] == "[0:1][0:7]overlay[v]"
    assert args[args.index("-force_key_frames") + 1] == "expr:gte(t,n_forced*6.000000)"


@pytest.mark.asyncio
async def test_qsv_render_nodes(tmp_path: Path, probe: FFProbeResult, monkeypatch: pytest.MonkeyPatch) -> None:
    vainfo = tmp_path / "vainfo"
    vainfo.touch()
    run = AsyncMock(
        side_effect=[
            (0, b"      VAProfileH264High :\tVAEntrypointEncSlice  \n", ""),
            (0, b"      VAProfileH264High :\tVAEntrypointEncSliceLP\n", ""),
        ]
    )
    monkeypatch.setattr(utils, "shutil", SimpleNamespace(which=lambda _: str(vainfo)))
    monkeypatch.setattr(utils, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(utils, "has_dri_devices", lambda: True)
    monkeypatch.setattr(utils, "run", run)

    config = Config.get_instance()
    segment = Segments(0, probe=probe)
    file = tmp_path / "video.mp4"
    async with asyncio.timeout(5):
        monkeypatch.setattr(config, "vaapi_device", "/dev/dri/renderD129")
        full = await segment.build_ffmpeg_args(file, "h264_qsv")
        monkeypatch.setattr(config, "vaapi_device", "/dev/dri/renderD130")
        low = await segment.build_ffmpeg_args(file, "h264_qsv")

    assert run.await_args_list == [
        call(str(vainfo), ["--display", "drm", "--device", device], deadline=5, max_bytes=256 * 1024)
        for device in ("/dev/dri/renderD129", "/dev/dri/renderD130")
    ]
    assert full[full.index("-init_hw_device") + 1] == "qsv=hw:hw,child_device=/dev/dri/renderD129"
    assert full[full.index("-rc_mode") + 1] == "cqp"
    assert "-low_power" not in full
    assert low[low.index("-init_hw_device") + 1] == "qsv=hw:hw,child_device=/dev/dri/renderD130"
    assert low[low.index("-low_power") + 1] == "1"
    assert low[low.index("-b:v") + 1] == "3M"
