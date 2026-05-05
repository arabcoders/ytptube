from pathlib import Path
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from app.features.streaming import router
from app.library.config import Config


class _DummyRoute:
    def __init__(self, pattern: str) -> None:
        self.pattern = pattern

    def url_for(self, **params: str) -> str:
        path = self.pattern
        for key, value in params.items():
            path = path.replace(f"{{{key}:.*}}", value)
            path = path.replace(f"{{{key}}}", value)
        return path


class _DummyRouter(dict[str, _DummyRoute]):
    def __init__(self) -> None:
        super().__init__(
            {
                "subtitles_manifest_get": _DummyRoute("/api/player/subtitles/manifest/{file:.*}"),
                "subtitles_track_get": _DummyRoute("/api/player/subtitles/{source_format}/{file:.*}"),
                "subtitles_get": _DummyRoute("/api/player/subtitle/{file:.*}.vtt"),
            }
        )


def _make_request(path: str, *, match_info: dict[str, str]) -> web.Request:
    return make_mocked_request("GET", path, app=SimpleNamespace(router=_DummyRouter()), match_info=match_info)


@pytest.mark.asyncio
async def test_subtitles_manifest_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    req = _make_request(
        "/api/player/subtitles/manifest/video.mp4",
        match_info={"file": "video.mp4"},
    )
    response = await router.subtitles_manifest_get(req, config, req.app)

    assert response.status == web.HTTPOk.status_code
    body = response.text
    assert '"source_format": "vtt"' in body
    assert '"renderer": "native"' in body
    assert '"source_format": "ass"' in body
    assert '"renderer": "assjs"' in body
    assert body.index('"source_format": "vtt"') < body.index('"source_format": "ass"')


@pytest.mark.asyncio
async def test_subtitles_track_get_ass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    config.download_path = str(tmp_path)

    subtitle = tmp_path / "video.ass"
    subtitle.write_text("[Script Info]\nTitle: Demo\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.features.streaming.router.get_file",
        lambda **_kwargs: (subtitle, web.HTTPOk.status_code),
    )

    req = _make_request(
        "/api/player/subtitles/ass/video.ass",
        match_info={"source_format": "ass", "file": "video.ass"},
    )
    response = await router.subtitles_track_get(req, config, req.app)

    assert response.status == web.HTTPOk.status_code
    assert response.text == "[Script Info]\nTitle: Demo\n"
    assert response.headers["Content-Type"] == "text/x-ssa; charset=UTF-8"


@pytest.mark.asyncio
async def test_subtitles_track_bad_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    config.download_path = str(tmp_path)

    subtitle = tmp_path / "video.ass"
    subtitle.write_text("[Script Info]\nTitle: Demo\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.features.streaming.router.get_file",
        lambda **_kwargs: (subtitle, web.HTTPOk.status_code),
    )

    req = _make_request(
        "/api/player/subtitles/vtt/video.ass",
        match_info={"source_format": "vtt", "file": "video.ass"},
    )
    response = await router.subtitles_track_get(req, config, req.app)

    assert response.status == web.HTTPBadRequest.status_code
    assert b"does not match requested source format" in response.body
