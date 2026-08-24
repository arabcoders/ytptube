from pathlib import Path
from unittest.mock import patch

import pytest
from aiohttp import web

from app.features.streaming import router
from app.library.config import Config
from app.tests.helpers import url_for


def _player_handlers(config: Config) -> dict[str, object]:
    async def playlist(request):
        return await router.playlist_create(request, config, request.app)

    async def m3u8(request):
        return await router.m3u8_create(request, config, request.app)

    async def segments(request):
        return await router.segments_stream(request, config, request.app)

    return {"playlist_create": playlist, "m3u8_create": m3u8, "segments_stream": segments}


def _make_media(tmp_path: Path) -> Path:
    config = Config.get_instance()
    config.download_path = str(tmp_path)
    media = tmp_path / "video.mp4"
    media.write_text("x", encoding="utf-8")
    return media


@pytest.mark.asyncio
async def test_playlist_without_ffprobe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    media = _make_media(tmp_path)
    monkeypatch.setattr("app.features.streaming.router.get_file", lambda **_kwargs: (media, web.HTTPOk.status_code))

    client = await test_client(_player_handlers(Config.get_instance()))
    with patch("app.features.streaming.router.ffprobe_bin", return_value=None):
        response = await client.get(url_for("playlist_create", file="video.mp4"))

    assert response.status == web.HTTPServiceUnavailable.status_code
    body = await response.json()
    assert body["code"] == "FFPROBE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_m3u8_video_without_ffprobe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    media = _make_media(tmp_path)
    monkeypatch.setattr("app.features.streaming.router.get_file", lambda **_kwargs: (media, web.HTTPOk.status_code))

    client = await test_client(_player_handlers(Config.get_instance()))
    with patch("app.features.streaming.router.ffprobe_bin", return_value=None):
        response = await client.get(url_for("m3u8_create", mode="video", file="video.mp4"))

    assert response.status == web.HTTPServiceUnavailable.status_code
    body = await response.json()
    assert body["code"] == "FFPROBE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_m3u8_subtitle_without_ffprobe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    media = _make_media(tmp_path)
    monkeypatch.setattr("app.features.streaming.router.get_file", lambda **_kwargs: (media, web.HTTPOk.status_code))

    client = await test_client(_player_handlers(Config.get_instance()))
    with patch("app.features.streaming.router.ffprobe_bin", return_value=None):
        response = await client.get(url_for("m3u8_create", mode="subtitle", file="video.mp4", query={"duration": 10}))

    assert response.status == web.HTTPOk.status_code
    assert "EXT-X-ENDLIST" in await response.text()


@pytest.mark.asyncio
async def test_playlist_probe_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    from app.features.streaming.types import FFProbeError

    media = _make_media(tmp_path)
    monkeypatch.setattr("app.features.streaming.router.get_file", lambda **_kwargs: (media, web.HTTPOk.status_code))

    client = await test_client(_player_handlers(Config.get_instance()))
    with (
        patch("app.features.streaming.router.ffprobe_bin", return_value="/usr/bin/ffprobe"),
        patch("app.features.streaming.library.playlist.ffprobe", side_effect=FFProbeError("probe failed")),
    ):
        response = await client.get(url_for("playlist_create", file="video.mp4"))

    assert response.status == web.HTTPInternalServerError.status_code
    body = await response.json()
    assert body["code"] == "INTERNAL_ERROR", "probe failures must map to a clean 500 error"
    assert "probe failed" not in await response.text(), "raw probe errors must not leak to clients"


@pytest.mark.asyncio
async def test_m3u8_video_probe_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    from app.features.streaming.types import FFProbeError

    media = _make_media(tmp_path)
    monkeypatch.setattr("app.features.streaming.router.get_file", lambda **_kwargs: (media, web.HTTPOk.status_code))

    client = await test_client(_player_handlers(Config.get_instance()))
    with (
        patch("app.features.streaming.router.ffprobe_bin", return_value="/usr/bin/ffprobe"),
        patch("app.features.streaming.library.m3u8.ffprobe", side_effect=FFProbeError("probe failed")),
    ):
        response = await client.get(url_for("m3u8_create", mode="video", file="video.mp4"))

    assert response.status == web.HTTPInternalServerError.status_code
    body = await response.json()
    assert body["code"] == "INTERNAL_ERROR", "probe failures must map to a clean 500 error"
    assert "probe failed" not in await response.text(), "raw probe errors must not leak to clients"


@pytest.mark.asyncio
async def test_segments_without_ffmpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    media = _make_media(tmp_path)
    monkeypatch.setattr("app.features.streaming.router.get_file", lambda **_kwargs: (media, web.HTTPOk.status_code))

    client = await test_client(_player_handlers(Config.get_instance()))
    with patch("app.features.streaming.router.ffmpeg_bin", return_value=None):
        response = await client.get(url_for("segments_stream", segment=0, file="video.mp4"))

    assert response.status == web.HTTPServiceUnavailable.status_code
    body = await response.json()
    assert body["code"] == "FFMPEG_UNAVAILABLE"
