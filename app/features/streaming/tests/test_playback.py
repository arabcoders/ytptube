from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import ClientTimeout, web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

from app.features.auth.middleware import AUTH_USER_KEY, auth_middleware
from app.features.auth.service import AuthService
from app.features.streaming.playback import playback_get, playback_put
from app.library.cache import Cache, JsonPersistence
from app.library.config import Config, ExternalAuthConfig, RemoteUserConfig
from app.library.router import RouteType, get_routes
from app.library.Services import Services


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Cache]:
    Cache._reset_singleton()
    monkeypatch.setattr("app.library.cache.time.time", lambda: 1000.0)
    value = Cache(JsonPersistence(tmp_path / "cache.json"))
    try:
        yield value
    finally:
        Cache._reset_singleton()


def request(method: str, body: object = None, user: dict | None = None) -> web.Request:
    value = make_mocked_request(method, "/api/playback/x", match_info={"media_id": "x"})
    if user is not None:
        value[AUTH_USER_KEY] = user
    value.json = AsyncMock(return_value=body)
    return value


@pytest.mark.asyncio
async def test_playback_isolates_users(cache: Cache) -> None:
    await playback_put(request("PUT", {"position": 4, "user_id": 2}, {"id": 1}), cache)
    response = await playback_get(request("GET", user={"id": 2}), cache)
    assert json.loads(response.text) == {"position": None}
    own = await playback_get(request("GET", user={"id": 1}), cache)
    assert json.loads(own.text) == {"position": 4.0}
    assert own.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
async def test_playback_persists(cache: Cache) -> None:
    await playback_put(request("PUT", {"position": 4}), cache)
    key = cache.hash("playback:shared:x")
    assert cache.ttl(key) == 24 * 60 * 60
    async with asyncio.timeout(5):
        await cache.flush()
    assert cache._persistence is not None
    entries = cache._persistence.load()
    assert entries[key].value == 4.0
    assert entries[key].expires_at == 1000 + 24 * 60 * 60


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        None,
        {"position": float("nan")},
        {"position": float("inf")},
        {"position": 10**400},
        {"position": -1},
        {"position": True},
        {"position": "4"},
    ],
)
async def test_playback_rejects_payloads(cache: Cache, body: object) -> None:
    await playback_put(request("PUT", {"position": 7}), cache)
    response = await playback_put(request("PUT", body), cache)
    assert response.status == web.HTTPBadRequest.status_code
    assert json.loads(response.text)["code"] == "BAD_REQUEST"
    saved = await playback_get(request("GET"), cache)
    assert json.loads(saved.text) == {"position": 7.0}


@pytest.mark.asyncio
async def test_playback_clears_state(cache: Cache) -> None:
    await playback_put(request("PUT", {"position": 4}), cache)
    await playback_put(request("PUT", {"position": None}), cache)
    response = await playback_get(request("GET"), cache)
    assert json.loads(response.text) == {"position": None}
    async with asyncio.timeout(5):
        await cache.flush()
    assert cache._persistence is not None
    assert cache._persistence.load() == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", [False, True])
async def test_playback_authenticates(cache: Cache, monkeypatch: pytest.MonkeyPatch, disabled: bool) -> None:
    config = Config.get_instance()
    monkeypatch.setattr(config, "disable_auth", disabled)
    monkeypatch.setattr(config, "cors_origins", "")
    monkeypatch.setattr(
        config,
        "external_auth",
        ExternalAuthConfig(
            external_user=None,
            oidc=None,
            remote_user=RemoteUserConfig(enabled=False, header="Remote-User", trusted_proxies=()),
        ),
    )
    auth = Mock(spec=AuthService)
    auth.session_user = AsyncMock(return_value={"id": 1, "username": "owner"})
    app = web.Application(middlewares=[auth_middleware(auth, config)])

    async def handler(request: web.Request) -> web.Response:
        name = request.match_info.route.name
        assert name is not None
        route = get_routes(RouteType.HTTP)[name]
        return await Services.get_instance().handle_async(route.handler, request=request, cache=cache)

    routes = [route for route in get_routes(RouteType.HTTP).values() if route.handler in (playback_get, playback_put)]
    assert len(routes) == 2
    for route in routes:
        app.router.add_route(route.method, f"/{route.path}", handler, name=route.name)
    client = TestClient(TestServer(app), timeout=ClientTimeout(total=5))
    try:
        async with asyncio.timeout(5):
            await client.start_server()
            for method in ("GET", "PUT"):
                response = await client.request(method, "/api/playback/x", json={"position": 3})
                assert response.status == (200 if disabled else 401)
            response = await client.put("/api/playback/x", json={"position": 6}, cookies={"ytp_session": "valid"})
            assert response.status == 200
            key = cache.hash(f"playback:{'shared' if disabled else '1'}:x")
            assert cache.get(key) == 6
    finally:
        async with asyncio.timeout(5):
            await client.close()
