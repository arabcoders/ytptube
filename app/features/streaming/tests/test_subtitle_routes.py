from pathlib import Path
from types import SimpleNamespace

import pytest
from aiohttp import web

from app.features.streaming import router
from app.library.config import Config
from app.tests.helpers import url_for


def _subtitle_handlers(config: Config) -> dict[str, object]:
    async def manifest(request):
        return await router.subtitles_manifest_get(request, config, request.app)

    async def track(request):
        return await router.subtitles_track_get(request, config, request.app)

    return {"subtitles_manifest_get": manifest, "subtitles_track_get": track}


@pytest.mark.asyncio
async def test_subtitles_manifest_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    config.download_path = str(tmp_path)

    media = tmp_path / "video.mp4"
    media.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        "app.features.streaming.router.get_file",
        lambda **_kwargs: (media, web.HTTPOk.status_code),
    )
    monkeypatch.setattr(
        "app.features.streaming.router.get_subtitle_tracks",
        lambda _file: [
            SimpleNamespace(
                lang="en",
                name="English VTT",
                source_format="vtt",
                delivery_format="vtt",
                renderer="native",
                file=tmp_path / "video.vtt",
            ),
            SimpleNamespace(
                lang="en",
                name="English ASS",
                source_format="ass",
                delivery_format="ass",
                renderer="assjs",
                file=tmp_path / "video.ass",
            ),
        ],
    )

    client = await test_client(_subtitle_handlers(config))
    response = await client.get(url_for("subtitles_manifest_get", file="video.mp4"))

    assert response.status == web.HTTPOk.status_code
    body = await response.text()
    assert '"source_format": "vtt"' in body
    assert '"renderer": "native"' in body
    assert '"source_format": "ass"' in body
    assert '"renderer": "assjs"' in body
    assert body.index('"source_format": "vtt"') < body.index('"source_format": "ass"')


@pytest.mark.asyncio
async def test_subtitles_track_get_ass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    config.download_path = str(tmp_path)

    subtitle = tmp_path / "video.ass"
    subtitle.write_text("[Script Info]\nTitle: Demo\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.features.streaming.router.get_file",
        lambda **_kwargs: (subtitle, web.HTTPOk.status_code),
    )

    client = await test_client(_subtitle_handlers(config))
    response = await client.get(url_for("subtitles_track_get", source_format="ass", file="video.ass"))

    assert response.status == web.HTTPOk.status_code
    assert await response.text() == "[Script Info]\nTitle: Demo\n"
    assert response.headers["Content-Type"] == "text/x-ssa; charset=UTF-8"


@pytest.mark.asyncio
async def test_subtitles_track_bad_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    config.download_path = str(tmp_path)

    subtitle = tmp_path / "video.ass"
    subtitle.write_text("[Script Info]\nTitle: Demo\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.features.streaming.router.get_file",
        lambda **_kwargs: (subtitle, web.HTTPOk.status_code),
    )

    client = await test_client(_subtitle_handlers(config))
    response = await client.get(url_for("subtitles_track_get", source_format="vtt", file="video.ass"))

    assert response.status == web.HTTPBadRequest.status_code
    assert "does not match requested source format" in (await response.text())
