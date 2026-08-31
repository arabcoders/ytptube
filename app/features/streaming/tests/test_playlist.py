from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from app.features.streaming.library.playlist import Playlist
from app.features.streaming.types import StreamingError


@pytest.mark.asyncio
async def test_playlist_without_subs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "downloads"
    base.mkdir()
    media = base / "My Video.mp4"
    media.write_text("x")

    async def fake_ffprobe(_file: Path):
        return SimpleNamespace(metadata={"duration": "60"})

    monkeypatch.setattr("app.features.streaming.library.playlist.ffprobe", fake_ffprobe)
    monkeypatch.setattr("app.features.streaming.library.playlist.get_file_sidecar", lambda _f: {"subtitle": []})

    pl = Playlist(download_path=base, url="http://localhost/")
    out = await pl.make(media)

    lines = out.splitlines()
    assert lines[0] == "#EXTM3U"
    assert lines[1] == "#EXT-X-STREAM-INF:PROGRAM-ID=1"
    expected_ref = quote(str(Path("My Video.mp4")))
    assert lines[2] == f"http://localhost/api/player/m3u8/video/{expected_ref}.m3u8"


@pytest.mark.asyncio
async def test_playlist_with_subs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "downloads"
    base.mkdir()
    media = base / "dir" / "file.mp4"
    media.parent.mkdir()
    media.write_text("x")

    async def fake_ffprobe(_file: Path):
        return SimpleNamespace(metadata={"duration": "12.5"})

    monkeypatch.setattr("app.features.streaming.library.playlist.ffprobe", fake_ffprobe)

    sub1 = media.with_suffix(".en.srt")
    sub2 = media.with_name("another sub.srt")
    sidecar = {
        "subtitle": [
            {"lang": "en", "file": sub1, "name": "English"},
            {"lang": "fr", "file": sub2, "name": "French"},
        ]
    }
    monkeypatch.setattr("app.features.streaming.library.playlist.get_file_sidecar", lambda _f: sidecar)

    pl = Playlist(download_path=base, url="https://server/")
    out = await pl.make(media)

    lines = out.splitlines()
    assert lines[0] == "#EXTM3U"
    assert lines[1].startswith("#EXT-X-MEDIA:TYPE=SUBTITLES,")
    assert 'NAME="English"' in lines[1]
    assert 'LANGUAGE="en"' in lines[1]
    assert "duration=12.5" in lines[1]
    expected_uri1 = quote(str(Path("dir").joinpath(sub1.name)))
    assert f"/subtitle/{expected_uri1}.m3u8" in lines[1]

    assert lines[2].startswith("#EXT-X-MEDIA:TYPE=SUBTITLES,")
    assert 'NAME="French"' in lines[2]
    assert 'LANGUAGE="fr"' in lines[2]
    expected_uri2 = quote(str(Path("dir").joinpath(sub2.name)))
    assert f"/subtitle/{expected_uri2}.m3u8" in lines[2]

    assert lines[3] == '#EXT-X-STREAM-INF:PROGRAM-ID=1,SUBTITLES="subs"'
    expected_ref = quote(str(Path("dir/file.mp4")))
    assert lines[4] == f"https://server/api/player/m3u8/video/{expected_ref}.m3u8"


@pytest.mark.asyncio
async def test_playlist_missing_duration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "downloads"
    base.mkdir()
    media = base / "file.mp4"
    media.write_text("x")

    async def fake_ffprobe(_file: Path):
        return SimpleNamespace(metadata={})

    monkeypatch.setattr("app.features.streaming.library.playlist.ffprobe", fake_ffprobe)
    monkeypatch.setattr("app.features.streaming.library.playlist.get_file_sidecar", lambda _f: {"subtitle": []})

    pl = Playlist(download_path=base, url="http://localhost/")

    with pytest.raises(StreamingError, match="Unable to get"):
        await pl.make(media)
