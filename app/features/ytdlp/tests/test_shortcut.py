from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.features.ytdlp import router
from app.features.ytdlp.shortcut import cookie_file_header, extracted_headers, media_type, selected_format
from app.library.router import ROUTES, RouteType
from app.tests.helpers import url_for


def item(**values: object) -> dict:
    return {
        "id": "id1",
        "title": "Example",
        "url": "https://cdn.test/file.mp4",
        "format": "best",
        "format_id": "18",
        "format_note": "360p",
        "ext": "mp4",
        "width": 640,
        "height": 360,
        "vcodec": "avc",
        "acodec": "aac",
        "filesize": 12,
        **values,
    }


class Cache:
    value: dict | None = None

    def get(self, _: str) -> dict | None:
        return self.value

    def set(self, key: str, value: dict, ttl: int, *, persist: bool) -> None:
        assert key.startswith("shortcut:")
        assert ttl == 21600 and persist is False
        self.value = value


class Options:
    last: dict | None = None

    def preset(self, _: str) -> Options:
        return self

    def get_all(self) -> dict:
        return {
            "format": "1080p",
            "format_sort": ["res:1080"],
            "format_sort_force": True,
            "proxy": "http://proxy.test",
            "socket_timeout": 12,
            "download_archive": "secret",
        }


class Presets:
    def __init__(self, value: object = True) -> None:
        self.value = value

    def get(self, _: str) -> object:
        return self.value


class Upstream:
    def __init__(self, status: int = 200) -> None:
        self.status_code = status
        self.headers = {"Content-Length": "4", "ETag": "tag", "X-Leak": "no"}
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    async def aiter_bytes(self, _: int):
        yield b"body"


class Client:
    def __init__(self, upstream: Upstream) -> None:
        self.upstream = upstream
        self.request: tuple | None = None

    def build_request(self, method: str, url: str, headers: dict, timeout: float):
        self.request = (method, url, headers, timeout)
        return self.request

    async def send(self, *_args, **_kwargs):
        return self.upstream


def test_selected_top_level() -> None:
    selected = item(formats=[item(format_id="other")])
    assert selected_format(selected) is selected
    with pytest.raises(ValueError, match="Multiple"):
        selected_format(item(requested_formats=[item(), item(format_id="second")]))


@pytest.mark.parametrize(
    ("values", "expected"),
    [({"vcodec": "none"}, "audio"), ({"acodec": "none"}, "video")],
)
def test_media_type(values: dict, expected: str) -> None:
    assert media_type(item(**values)) == expected


@pytest.mark.parametrize("url", ["https://cdn.test/master.m3u8", "https://cdn.test/file.mpd", "rtmp://cdn.test/file"])
def test_selected_rejects_url(url: str) -> None:
    with pytest.raises(ValueError):
        selected_format(item(url=url, protocol="m3u8" if "m3u8" in url else "rtmp", formats=[item(format_id="unused")]))


def test_header_cookie_scope(tmp_path) -> None:
    path = tmp_path / "cookies.txt"
    path.write_text("# Netscape HTTP Cookie File\n.example.test\tTRUE\t/stream\tFALSE\t2147483647\twide\t1\n")
    assert cookie_file_header(str(path), "https://example.test/stream/file") == "wide=1"
    assert cookie_file_header(str(path), "https://example.test/other/file") is None
    assert extracted_headers(
        item(http_headers={"Authorization": "extract", "Referer": "player"}),
        {},
        {"http_headers": {"User-Agent": "preset"}},
    ) == {"Authorization": "extract", "Referer": "player", "User-Agent": "preset"}


@pytest.mark.asyncio
async def test_info_is_singular(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    cache = Cache()
    options = Options()
    fetch = AsyncMock(
        return_value=(
            item(formats=[item(format_id="unused")], filesize=None, filesize_approx=14, resolution=None),
            [],
        )
    )
    monkeypatch.setattr(router, "validate_url", lambda _: None)
    monkeypatch.setattr(router.Presets, "get_instance", lambda: Presets())
    monkeypatch.setattr(router.YTDLPOpts, "get_instance", lambda: options)
    monkeypatch.setattr(router, "fetch_info", fetch)

    async def handler(request):
        return await router.shortcut_info(request, cache, SimpleNamespace(default_preset="default"))

    client = await test_client({"shortcut.info": handler})
    response = await client.get(url_for("shortcut.info", query={"url": "https://source.test/v"}))
    body = await response.json()
    assert response.status == 200
    assert body["media_type"] == "video+audio"
    assert body["filesize"] == 14
    assert body["resolution"] == "640x360"
    assert body["download_url"].startswith("/api/yt-dlp/shortcut/download/")
    assert not {"formats", "index", "url", "proxy", "headers", "cookies"} & body.keys()
    cached = cache.value
    assert cached is not None
    assert cached["format"]["url"] == "https://cdn.test/file.mp4"
    assert "formats" not in cached
    call = fetch.await_args
    assert call is not None
    assert call.kwargs["config"]["format"] == "best"
    assert "format_sort" not in call.kwargs["config"]
    assert "format_sort_force" not in call.kwargs["config"]
    assert call.kwargs["config"]["noplaylist"] is True
    assert call.kwargs["no_archive"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [{"_type": "playlist"}, {"is_live": True}, None])
async def test_info_rejects_media(monkeypatch: pytest.MonkeyPatch, data, test_client) -> None:
    monkeypatch.setattr(router, "validate_url", lambda _: None)
    monkeypatch.setattr(router.Presets, "get_instance", lambda: Presets())
    monkeypatch.setattr(router.YTDLPOpts, "get_instance", lambda: Options())
    monkeypatch.setattr(router, "fetch_info", AsyncMock(return_value=(data, [])))

    async def handler(request):
        return await router.shortcut_info(request, Cache(), SimpleNamespace(default_preset="default"))

    client = await test_client({"shortcut.info": handler})
    expected = 500 if data is None else 400
    assert (await client.get(url_for("shortcut.info", query={"url": "https://source.test/v"}))).status == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [{}, {"url": "bad"}])
async def test_info_rejects_input(monkeypatch: pytest.MonkeyPatch, query, test_client) -> None:
    def reject(_: str) -> None:
        raise ValueError("invalid")

    monkeypatch.setattr(router, "validate_url", reject)

    async def handler(request):
        return await router.shortcut_info(request, Cache(), SimpleNamespace(default_preset="default"))

    client = await test_client({"shortcut.info": handler})
    assert (await client.get(url_for("shortcut.info", query=query))).status == 400


@pytest.mark.asyncio
async def test_info_rejects_preset(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    monkeypatch.setattr(router, "validate_url", lambda _: None)
    monkeypatch.setattr(router.Presets, "get_instance", lambda: Presets(None))

    async def handler(request):
        return await router.shortcut_info(request, Cache(), SimpleNamespace(default_preset="default"))

    client = await test_client({"shortcut.info": handler})
    response = await client.get(url_for("shortcut.info", query={"url": "https://source.test/v"}))
    assert response.status == 404


@pytest.mark.asyncio
async def test_download_streams_and_filters(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    upstream = Upstream(206)
    client = Client(upstream)
    cache = Cache()
    cache.value = {
        "format": item(),
        "headers": {"Authorization": "extract", "Cookie": "preset=1"},
        "filename": "Example.mp4",
        "ext": "mp4",
        "timeout": 12,
    }
    monkeypatch.setattr(router, "get_async_client", lambda **_: client)

    async def handler(request):
        return await router.shortcut_download(request, cache)

    app_client = await test_client({"shortcut.download": handler})
    response = await app_client.get(
        url_for("shortcut.download", token="x"),
        headers={"Authorization": "caller", "Cookie": "caller=1", "Range": "bytes=1-"},
    )
    assert response.status == 206
    assert await response.read() == b"body"
    assert response.headers["Content-Disposition"] == 'attachment; filename="Example.mp4"'
    assert response.headers["Content-Type"] == "video/mp4"
    request = client.request
    assert request is not None
    assert request[2] == {"Authorization": "extract", "Cookie": "preset=1", "Range": "bytes=1-"}
    assert upstream.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["bytes=1-2,4-5", "bytes=4-2", "bytes=-0"])
async def test_download_rejects_range(value: str, test_client) -> None:
    cache = Cache()
    cache.value = {"format": item(), "headers": {}, "filename": "x.mp4", "ext": "mp4"}

    async def handler(request):
        return await router.shortcut_download(request, cache)

    client = await test_client({"shortcut.download": handler})
    assert (await client.get(url_for("shortcut.download", token="x"), headers={"Range": value})).status == 400


@pytest.mark.asyncio
async def test_download_closes_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = Upstream()

    async def cancelled(_: int):
        raise asyncio.CancelledError
        yield b""

    monkeypatch.setattr(upstream, "aiter_bytes", cancelled)
    monkeypatch.setattr(router, "get_async_client", lambda **_: Client(upstream))
    request = SimpleNamespace(
        match_info={"token": "x"}, headers={}, transport=SimpleNamespace(is_closing=lambda: False)
    )
    monkeypatch.setattr(router.web.StreamResponse, "prepare", AsyncMock())
    with pytest.raises(asyncio.CancelledError):
        await router.shortcut_download(
            request, CacheWith({"format": item(), "headers": {}, "filename": "x.mp4", "ext": "mp4"})
        )
    assert upstream.closed


@pytest.mark.asyncio
async def test_download_closes_error(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    upstream = Upstream(403)
    monkeypatch.setattr(router, "get_async_client", lambda **_: Client(upstream))
    cache = CacheWith({"format": item(), "headers": {}, "filename": "x.mp4", "ext": "mp4"})

    async def handler(request):
        return await router.shortcut_download(request, cache)

    client = await test_client({"shortcut.download": handler})
    response = await client.get(url_for("shortcut.download", token="x"))
    assert response.status == 502
    assert "cdn.test" not in await response.text()
    assert upstream.closed


class CacheWith(Cache):
    def __init__(self, value: dict) -> None:
        self.value = value


def test_route_defaults() -> None:
    assert ROUTES[RouteType.HTTP]["shortcut.info"].public is False
    assert ROUTES[RouteType.HTTP]["shortcut.download"].public is False
