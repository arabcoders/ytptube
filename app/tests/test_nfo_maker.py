from __future__ import annotations

from pathlib import Path

from app.yt_dlp_plugins.postprocessor.nfo_maker import NFOMakerPP


def sample_info_tv(path: Path) -> dict:
    return {
        "id": "abc123",
        "title": "Test Show - S01E02",
        "uploader": "uploader_name",
        "upload_date": "20230102",
        "season_number": 1,
        "episode_number": 2,
        "description": "First line.\n#tag\n00:01:23 Intro",
        "extractor": "youtube",
        "filename": str(path),
    }


def sample_info_movie(path: Path) -> dict:
    return {
        "id": "mov001",
        "title": "Test Movie",
        "uploader": "studio",
        "release_date": "20221225",
        "duration": 7200,
        "thumbnail": "http://example.com/thumb.jpg",
        "webpage_url": "http://example.com/trailer",
        "filename": str(path),
    }


def test_generate_nfo_tv_mode(tmp_path: Path) -> None:
    media_file = tmp_path / "test_show_s01e02.mkv"
    info = sample_info_tv(media_file)
    media_file.write_text("dummy", encoding="utf-8")
    nfo_path = media_file.with_suffix(".nfo")
    nfo_path.unlink(missing_ok=True)

    res = NFOMakerPP.generate_nfo(info_dict=info, filepath=media_file, mode="tv", overwrite=True, prefix=True)

    assert res["success"] is True
    assert nfo_path.exists()

    content = nfo_path.read_text(encoding="utf-8")
    assert "<episodedetails>" in content
    assert "<title>Test Show - S01E02</title>" in content
    assert "Intro" not in content
    assert "#tag" not in content

    nfo_path.unlink()
    pp = NFOMakerPP(None, mode="tv", prefix=True)
    media_mtime = media_file.stat().st_mtime
    pp.run(info.copy())
    assert nfo_path.exists()
    nfo_mtime = nfo_path.stat().st_mtime
    assert abs(nfo_mtime - media_mtime) < 2.0


def test_generate_nfo_movie_mode_and_run_wrapper(tmp_path: Path) -> None:
    media_file = tmp_path / "test_movie.mp4"
    info = sample_info_movie(media_file)
    media_file.write_text("dummy-movie", encoding="utf-8")
    nfo_path = media_file.with_suffix(".nfo")
    nfo_path.unlink(missing_ok=True)

    res = NFOMakerPP.generate_nfo(info_dict=info, filepath=media_file, mode="movie", overwrite=True, prefix=False)

    assert res["success"] is True
    assert nfo_path.exists()
    content = nfo_path.read_text(encoding="utf-8")
    assert "<movie>" in content
    assert "<title>Test Movie</title>" in content
    assert "<runtime>7200</runtime>" in content or "<runtime>7200" in content

    nfo_path.unlink()

    pp = NFOMakerPP(None, mode="movie", prefix=False)
    assert media_file.exists()

    media_mtime = media_file.stat().st_mtime

    pp.run(info.copy())

    assert nfo_path.exists()

    nfo_mtime = nfo_path.stat().st_mtime
    assert abs(nfo_mtime - media_mtime) < 2.0
