from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from app.features.streaming.library.m3u8 import M3u8
from app.features.streaming.types import StreamingError


class _Stream:
    def __init__(self, v: bool, a: bool, codec: str):
        self.codec_name = codec
        self._v = v
        self._a = a

    def is_video(self) -> bool:
        return self._v

    def is_audio(self) -> bool:
        return self._a


@pytest.mark.asyncio
async def test_make_stream_basic_ok_codecs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "dl"
    base.mkdir()
    media = base / "dir with space" / "file.mp4"
    media.parent.mkdir()
    media.write_text("x")

    async def fake_ffprobe(_file: Path):
        return SimpleNamespace(
            metadata={"duration": "12"},
            streams=lambda: [
                _Stream(v=True, a=False, codec="h264"),
                _Stream(v=False, a=True, codec="aac"),
            ],
        )

    monkeypatch.setattr("app.features.streaming.library.m3u8.ffprobe", fake_ffprobe)

    m3 = M3u8(download_path=base, url="http://host/")
    out = await m3.make_stream(media)
    lines = out.splitlines()

    # Headers
    assert lines[0] == "#EXTM3U"
    assert lines[1] == "#EXT-X-VERSION:3"
    assert lines[2] == "#EXT-X-TARGETDURATION:6"
    assert lines[3] == "#EXT-X-MEDIA-SEQUENCE:0"
    assert lines[4] == "#EXT-X-PLAYLIST-TYPE:VOD"

    # Two segments: 0 (no params), 1 (sd present)
    rel = quote(str(Path("dir with space/file.mp4")))
    assert lines[5] == "#EXTINF:6.000000,"
    assert lines[6] == f"http://host/api/player/segments/0/{rel}.ts"

    assert lines[7] == "#EXTINF:6.000000,"
    assert lines[8].startswith(f"http://host/api/player/segments/1/{rel}.ts?")
    assert "sd=6.000000" in lines[8]

    assert lines[9] == "#EXT-X-ENDLIST"


@pytest.mark.asyncio
async def test_make_stream_transcode_flags_and_remainder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "dl"
    base.mkdir()
    media = base / "v.mp4"
    media.write_text("x")

    async def fake_ffprobe(_file: Path):
        return SimpleNamespace(
            metadata={"duration": "13"},
            streams=lambda: [
                _Stream(v=True, a=False, codec="hevc"),
                _Stream(v=False, a=True, codec="flac"),
            ],
        )

    monkeypatch.setattr("app.features.streaming.library.m3u8.ffprobe", fake_ffprobe)

    m3 = M3u8(download_path=base, url="https://s/")
    out = await m3.make_stream(media)
    lines = out.splitlines()

    # 3 segments, last has 1.000000 duration and includes vc/ac + sd
    rel = quote(str(Path("v.mp4")))
    # First
    assert lines[5] == "#EXTINF:6.000000,"
    assert lines[6].startswith(f"https://s/api/player/segments/0/{rel}.ts?")
    assert "vc=1" in lines[6]
    assert "ac=1" in lines[6]
    # Second
    assert lines[7] == "#EXTINF:6.000000,"
    assert lines[8].startswith(f"https://s/api/player/segments/1/{rel}.ts?")
    assert "vc=1" in lines[8]
    assert "ac=1" in lines[8]
    # Third
    assert lines[9] == "#EXTINF:1.000000,"
    assert lines[10].startswith(f"https://s/api/player/segments/2/{rel}.ts?")
    assert "vc=1" in lines[10]
    assert "ac=1" in lines[10]
    assert "sd=1.000000" in lines[10]
    assert lines[11] == "#EXT-X-ENDLIST"


@pytest.mark.asyncio
async def test_make_stream_raises_without_duration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "dl"
    base.mkdir()
    media = base / "v.mp4"
    media.write_text("x")

    async def fake_ffprobe(_file: Path):
        return SimpleNamespace(metadata={})

    monkeypatch.setattr("app.features.streaming.library.m3u8.ffprobe", fake_ffprobe)

    m3 = M3u8(download_path=base, url="http://s/")
    with pytest.raises(StreamingError, match="Unable to get"):
        await m3.make_stream(media)


@pytest.mark.asyncio
async def test_make_subtitle(tmp_path: Path) -> None:
    base = tmp_path / "dl"
    base.mkdir()
    sub = base / "dir" / "cap.srt"
    sub.parent.mkdir()
    sub.write_text("x")

    m3 = M3u8(download_path=base, url="http://h/")
    out = await m3.make_subtitle(sub, duration=42.5)
    lines = out.splitlines()

    assert lines[0] == "#EXTM3U"
    assert lines[1] == "#EXT-X-VERSION:3"
    assert lines[2] == "#EXT-X-TARGETDURATION:6"
    assert lines[3] == "#EXT-X-MEDIA-SEQUENCE:0"
    assert lines[4] == "#EXT-X-PLAYLIST-TYPE:VOD"
    assert lines[5] == "#EXTINF:42.5,"
    rel = quote(str(Path("dir/cap.srt")))
    assert lines[6] == f"http://h/api/player/subtitle/{rel}.vtt"
    assert lines[7] == "#EXT-X-ENDLIST"
