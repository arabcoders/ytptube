from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.yt_dlp_plugins.postprocessor.nfo_maker import NFOMakerPP

TEST_DIR = Path("var/tmp/tests_nfo")
TEST_DIR.mkdir(parents=True, exist_ok=True)


def _clean_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def sample_info_tv() -> dict:
    return {
        "id": "abc123",
        "title": "Test Show - S01E02",
        "uploader": "uploader_name",
        "upload_date": "20230102",
        "season_number": 1,
        "episode_number": 2,
        "description": "First line.\n#tag\n00:01:23 Intro",
        "extractor": "youtube",
        "filename": str(TEST_DIR / "test_show_s01e02.mkv"),
    }


def sample_info_movie() -> dict:
    return {
        "id": "mov001",
        "title": "Test Movie",
        "uploader": "studio",
        "release_date": "20221225",
        "duration": 7200,
        "thumbnail": "http://example.com/thumb.jpg",
        "webpage_url": "http://example.com/trailer",
        "filename": str(TEST_DIR / "test_movie.mp4"),
    }


def test_generate_nfo_tv_mode(tmp_path):
    # arrange
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    info = sample_info_tv()
    media_file = Path(info["filename"])
    media_file.write_text("dummy")
    nfo_path = media_file.with_suffix(".nfo")
    _clean_file(nfo_path)

    # act
    res = NFOMakerPP.generate_nfo(info_dict=info, filepath=media_file, mode="tv", overwrite=True, prefix=True)

    # assert
    assert res["success"] is True
    assert nfo_path.exists()

    content = nfo_path.read_text(encoding="utf-8")
    assert "<episodedetails>" in content
    assert "<title>Test Show - S01E02</title>" in content
    # description cleaned (no timestamps / hashtags)
    assert "Intro" not in content
    assert "#tag" not in content

    # also ensure PostProcessor.run wrapper produces the same result and syncs mtime
    _clean_file(nfo_path)
    pp = NFOMakerPP(None, mode="tv", prefix=True)
    media_mtime = media_file.stat().st_mtime
    _, info_out = pp.run(info.copy())
    assert nfo_path.exists()
    nfo_mtime = nfo_path.stat().st_mtime
    assert abs(nfo_mtime - media_mtime) < 2.0

    # cleanup
    media_file.unlink()
    nfo_path.unlink()


def test_generate_nfo_movie_mode_and_run_wrapper(tmp_path):
    # arrange
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    info = sample_info_movie()
    media_file = Path(info["filename"])
    media_file.write_text("dummy-movie")
    nfo_path = media_file.with_suffix(".nfo")
    _clean_file(nfo_path)

    # act: generate_nfo static
    res = NFOMakerPP.generate_nfo(info_dict=info, filepath=media_file, mode="movie", overwrite=True, prefix=False)

    # assert static helper
    assert res["success"] is True
    assert nfo_path.exists()
    content = nfo_path.read_text(encoding="utf-8")
    assert "<movie>" in content
    assert "<title>Test Movie</title>" in content
    assert "<runtime>7200</runtime>" in content or "<runtime>7200" in content

    # cleanup nfo and re-run via PP.run wrapper
    nfo_path.unlink()

    # call through instance run() to ensure wrapper works (mtime sync path exercised)
    pp = NFOMakerPP(None, mode="movie", prefix=False)
    # ensure file exists
    assert media_file.exists()

    # capture media file mtime before run
    media_mtime = media_file.stat().st_mtime

    _, info_out = pp.run(info.copy())

    # run() should not raise and should produce nfo file
    assert nfo_path.exists()

    # verify mtime was synced (allow small rounding differences)
    nfo_mtime = nfo_path.stat().st_mtime
    assert abs(nfo_mtime - media_mtime) < 2.0

    # cleanup
    media_file.unlink()
    nfo_path.unlink()
