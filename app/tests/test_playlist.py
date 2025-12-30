from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from app.library.Playlist import Playlist
from app.library.Utils import StreamingError


@pytest.mark.asyncio
async def test_make_playlist_no_subtitles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Setup paths
    base = tmp_path / "downloads"
    base.mkdir()
    # Use a relative subpath with spaces to validate quoting behavior
    media = base / "My Video.mp4"
    media.write_text("x")

    # Mock ffprobe to return duration
    async def fake_ffprobe(_file: Path):
        return SimpleNamespace(metadata={"duration": "60"})

    monkeypatch.setattr("app.library.Playlist.ffprobe", fake_ffprobe)
    # No sidecar subtitles
    monkeypatch.setattr("app.library.Playlist.get_file_sidecar", lambda _f: {"subtitle": []})

    # Patch module-level quote to be robust for Path objects
    from urllib.parse import quote as _std_quote

    monkeypatch.setattr("app.library.Playlist.quote", lambda v: _std_quote(str(v)))

    pl = Playlist(download_path=base, url="http://localhost/")
    out = await pl.make(media)

    lines = out.splitlines()
    assert lines[0] == "#EXTM3U"
    # No subtitles group when none present
    assert lines[1] == "#EXT-X-STREAM-INF:PROGRAM-ID=1"
    # Final line should point to video endpoint with quoted relative path
    expected_ref = quote(str(Path("My Video.mp4")))
    assert lines[2] == f"http://localhost/api/player/m3u8/video/{expected_ref}.m3u8"


@pytest.mark.asyncio
async def test_make_playlist_with_subtitles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "downloads"
    base.mkdir()
    media = base / "dir" / "file.mp4"
    media.parent.mkdir()
    media.write_text("x")

    # ffprobe returns numeric duration
    async def fake_ffprobe(_file: Path):
        return SimpleNamespace(metadata={"duration": "12.5"})

    monkeypatch.setattr("app.library.Playlist.ffprobe", fake_ffprobe)

    # Build two subtitle sidecars with names and langs; ensure quoting/relative name used
    sub1 = media.with_suffix(".en.srt")
    sub2 = media.with_name("another sub.srt")
    sidecar = {
        "subtitle": [
            {"lang": "en", "file": sub1, "name": "English"},
            {"lang": "fr", "file": sub2, "name": "French"},
        ]
    }
    monkeypatch.setattr("app.library.Playlist.get_file_sidecar", lambda _f: sidecar)

    from urllib.parse import quote as _std_quote

    monkeypatch.setattr("app.library.Playlist.quote", lambda v: _std_quote(str(v)))

    pl = Playlist(download_path=base, url="https://server/")
    out = await pl.make(media)

    lines = out.splitlines()
    assert lines[0] == "#EXTM3U"
    # Two EXT-X-MEDIA lines for subtitles
    assert lines[1].startswith("#EXT-X-MEDIA:TYPE=SUBTITLES,")
    assert 'NAME="English"' in lines[1]
    assert 'LANGUAGE="en"' in lines[1]
    assert "duration=12.5" in lines[1]
    # URI uses the file name relative to base, replacing the name with sidecar file name and quoted
    expected_uri1 = quote(str(Path("dir").joinpath(sub1.name)))
    assert f"/subtitle/{expected_uri1}.m3u8" in lines[1]

    assert lines[2].startswith("#EXT-X-MEDIA:TYPE=SUBTITLES,")
    assert 'NAME="French"' in lines[2]
    assert 'LANGUAGE="fr"' in lines[2]
    expected_uri2 = quote(str(Path("dir").joinpath(sub2.name)))
    assert f"/subtitle/{expected_uri2}.m3u8" in lines[2]

    # Stream info with SUBTITLES group
    assert lines[3] == '#EXT-X-STREAM-INF:PROGRAM-ID=1,SUBTITLES="subs"'
    # Final video URL
    expected_ref = quote(str(Path("dir/file.mp4")))
    assert lines[4] == f"https://server/api/player/m3u8/video/{expected_ref}.m3u8"


@pytest.mark.asyncio
async def test_make_playlist_raises_without_duration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "downloads"
    base.mkdir()
    media = base / "file.mp4"
    media.write_text("x")

    # ffprobe missing duration
    async def fake_ffprobe(_file: Path):
        return SimpleNamespace(metadata={})

    monkeypatch.setattr("app.library.Playlist.ffprobe", fake_ffprobe)
    monkeypatch.setattr("app.library.Playlist.get_file_sidecar", lambda _f: {"subtitle": []})

    pl = Playlist(download_path=base, url="http://localhost/")

    with pytest.raises(StreamingError, match="Unable to get"):
        await pl.make(media)
