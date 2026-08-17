from __future__ import annotations

import base64
import logging
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request
from aiohttp.web_log import AccessLogger
from pydantic import ValidationError

from app.features.auth.schemas import Credentials
from app.features.auth.service import password_hash, password_matches
from app.features.auth.service import AuthService
from app.library import migrate
from app.features.auth.middleware import (
    AUTH_USER_KEY,
    auth_middleware,
    cors_headers,
    decode_basic_credentials,
    is_cross_origin,
)
from app.features.auth.router import auth_account, auth_login, auth_logout
from app.library.cache import Cache
from app.library.config import Config
from app.library.HttpAPI import HttpAccessLogger, HttpAPI, redact_url
from app.library.sqlite_store import SqliteStore
from app.library.router import RouteType, get_route, get_routes
from app.tests.helpers import make_in_memory_db_path, url_for


AUTH_ROUTE_NAMES = (
    "auth_status",
    "auth_setup",
    "auth_login",
    "auth_logout",
    "auth_ws_ticket",
    "auth_me",
    "auth_account",
    "auth_api_keys",
    "auth_api_keys_create",
    "auth_api_keys_delete",
)


def production_auth_route(name: str) -> tuple[str, str]:
    route = get_route(RouteType.HTTP, name)
    assert route is not None
    return route.method, route.path if route.path.startswith("/") else f"/{route.path}"


def test_auth_route_names() -> None:
    registered = {name for name in get_routes(RouteType.HTTP) if name.startswith("auth")}
    assert registered == set(AUTH_ROUTE_NAMES)
    assert not any("." in name for name in registered)


@pytest.mark.asyncio
async def test_passwords_preserve_spaces() -> None:
    stored = await password_hash(" leading and trailing ")
    assert await password_matches(" leading and trailing ", stored)
    assert not await password_matches("leading and trailing", stored)


@pytest.mark.asyncio
async def test_password_limits() -> None:
    with pytest.raises(ValidationError):
        Credentials(username="user", password="é" * 37)
    with pytest.raises(ValidationError):
        Credentials(username="user", password="bad\x00password")


def test_basic_query_padding() -> None:
    assert decode_basic_credentials("dXNlcjpwYXNz") == ("user", "pass")
    assert decode_basic_credentials("not-basic") is None


@pytest.mark.asyncio
async def test_auth_migration(tmp_path) -> None:
    path = tmp_path / "auth.db"
    await migrate.upgrade(str(path), "app/migrations")
    with closing(sqlite3.connect(path)) as database:
        tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"users", "sessions", "api_keys"} <= tables


def test_ws_ticket_once() -> None:
    cache = Cache.get_instance()
    cache.clear()
    auth = AuthService.get_instance()
    ticket = auth.create_ws_ticket({"id": 1, "username": "user"})
    assert ticket.startswith("ytp_ws_")
    assert cache.get(ticket) is None
    assert auth.consume_ws_ticket(ticket) == {"id": 1, "username": "user"}
    assert auth.consume_ws_ticket(ticket) is None
    expired = auth.create_ws_ticket({"id": 1, "username": "user"})
    cache.set(cache.hash(expired), {"id": 1, "username": "user"}, ttl=-1)
    assert auth.consume_ws_ticket(expired) is None
    cache.clear()


@pytest.mark.asyncio
async def test_sessions_and_keys(monkeypatch) -> None:
    store = SqliteStore.get_instance(db_path=make_in_memory_db_path("auth-service"))
    await store.get_connection()

    @asynccontextmanager
    async def session():
        async with store.sessionmaker()() as value:
            yield value

    import app.features.auth.service as service_module

    monkeypatch.setattr(service_module, "get_session", session)
    config = Config.get_instance()
    config.auth_username = None
    config.auth_password = None
    auth = AuthService.get_instance()
    user = await auth.create_user("owner", "secret")
    assert user is not None
    assert await auth.create_user("second", "secret") is None
    token = await auth.create_session(user["id"])
    session_user = await auth.session_user(token)
    assert session_user is not None
    assert session_user["id"] == user["id"]
    metadata, key = await auth.create_key(user["id"], "browser")
    assert metadata["name"] == "browser"
    key_user = await auth.user_from_key(key)
    assert key_user is not None
    assert key_user["id"] == user["id"]
    await store.execute_raw(
        "INSERT INTO users (username, password_hash) VALUES (:username, :password_hash)",
        {"username": "other", "password_hash": await password_hash("other-secret")},
    )
    other = await auth.authenticate_password("other", "other-secret")
    assert other is not None
    assert not await auth.delete_key(other["id"], metadata["id"])
    assert await auth.delete_key(user["id"], metadata["id"])
    assert await auth.user_from_key(key) is None
    await store.execute_raw(
        "UPDATE sessions SET expires_at = :expires",
        {"expires": (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S.%f")},
    )
    assert await auth.session_user(token) is None
    await store.close()
    SqliteStore._reset_singleton()


@pytest.mark.asyncio
async def test_bootstrap_when_empty(monkeypatch) -> None:
    store = SqliteStore.get_instance(db_path=make_in_memory_db_path("auth-bootstrap"))
    await store.get_connection()

    @asynccontextmanager
    async def session():
        async with store.sessionmaker()() as value:
            yield value

    import app.features.auth.service as service_module

    monkeypatch.setattr(service_module, "get_session", session)
    config = Config.get_instance()
    config.auth_username = "env-user"
    config.auth_password = "env-password"
    auth = AuthService.get_instance()
    await auth.bootstrap()
    assert await auth.user_count() == 1
    config.auth_username = "other-user"
    config.auth_password = "other-password"
    await auth.bootstrap()
    assert await auth.user_count() == 1
    await store.close()
    SqliteStore._reset_singleton()


@pytest.mark.asyncio
async def test_auth_startup_ready(monkeypatch) -> None:
    store = SqliteStore.get_instance(db_path=make_in_memory_db_path("auth-startup"))

    @asynccontextmanager
    async def session():
        async with store.sessionmaker()() as value:
            yield value

    import app.features.auth.service as service_module

    monkeypatch.setattr(service_module, "get_session", session)
    config = Config.get_instance()
    config.auth_username = "startup-user"
    config.auth_password = "startup-password"
    app = web.Application()
    auth = AuthService.get_instance()
    auth.attach(app)
    await auth.startup(app)
    assert store.sessionmaker() is not None
    assert await auth.authenticate_password("startup-user", "startup-password") is not None
    assert await store.fetch_raw("SELECT name FROM sqlite_master WHERE name = 'users'")
    await store.close()
    SqliteStore._reset_singleton()
    config.auth_username = None
    config.auth_password = None


class FakeAuth(AuthService):
    async def authenticate_password(self, username: str, password: str) -> dict | None:
        return {"id": 1, "username": username} if username == "user" and password in {"pass", "ytp_password"} else None

    async def user_from_key(self, key: str) -> dict | None:
        return {"id": 1, "username": "user"} if key == "ytp_key" else None

    async def session_user(self, token: str) -> dict | None:
        return {"id": 1, "username": "user"} if token == "session" else None

    async def create_session(self, user_id: int) -> str:
        return "session"

    async def revoke_session(self, token: str) -> None:
        self.revoked = token

    async def update_user(self, user_id: int, username: str | None, password: str | None) -> dict:
        raise ValueError("Username already exists.")


class TicketAuth(FakeAuth):
    def __init__(self) -> None:
        self.consumed = False

    def consume_ws_ticket(self, ticket: str) -> dict | None:
        if ticket == "ytp_ws_valid" and not self.consumed:
            self.consumed = True
            return {"id": 1, "username": "user"}
        return None


class JsonRequest(dict):
    secure = False
    remote = "test-client"

    def __init__(self, payload: dict, cookies: dict[str, str] | None = None):
        super().__init__()
        self._payload = payload
        self.cookies = cookies or {}

    async def json(self) -> dict:
        return self._payload


@pytest.mark.asyncio
async def test_credentials_cors() -> None:
    called = False
    setup_called = False

    async def handler(_: web.Request) -> web.Response:
        nonlocal called
        called = True
        return web.json_response({"ok": True})

    async def setup_handler(_: web.Request) -> web.Response:
        nonlocal setup_called
        setup_called = True
        return web.json_response({"ok": True})

    async def status_handler(request: web.Request) -> web.Response:
        return web.json_response({"authenticated": AUTH_USER_KEY in request})

    config = Config.get_instance()
    config.disable_auth = False
    config.cors_origins = "*"
    config.base_path = "/"
    app = web.Application(middlewares=[auth_middleware(FakeAuth(), config)])
    app.router.add_get("/api/value", handler, name="api_value")
    app.router.add_options("/api/value", handler, name="api_value_options")
    app.router.add_get("/ws", handler, name="ws")
    for name in ("auth_setup", "auth_login"):
        method, path = production_auth_route(name)
        app.router.add_route(method, path, setup_handler, name=name)
    method, path = production_auth_route("auth_status")
    app.router.add_route(method, path, status_handler, name="auth_status")
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        response = await client.get(
            url_for("api_value", app=app), cookies={"ytp_session": "session"}, headers={"Origin": "https://site"}
        )
        assert response.status == 401
        assert not called
        same_origin = str(client.make_url("/")).rstrip("/")
        config.cors_origins = "https://unrelated.example"
        response = await client.get(
            url_for("api_value", app=app), cookies={"ytp_session": "session"}, headers={"Origin": same_origin}
        )
        assert response.status == 200
        assert (
            is_cross_origin(
                make_mocked_request(
                    "GET", "/", headers={"Origin": "https://different", "Sec-Fetch-Site": "same-origin"}
                )
            )
            is False
        )
        config.cors_origins = "*"
        response = await client.post(url_for("auth_setup", app=app), headers={"Origin": "https://site"})
        assert response.status == 403
        response = await client.post(url_for("auth_login", app=app), headers={"Origin": "https://site"})
        assert response.status == 403
        assert not setup_called
        response = await client.get(
            url_for("auth_status", app=app), cookies={"ytp_session": "session"}, headers={"Origin": "https://site"}
        )
        assert (await response.json())["authenticated"] is False
        response = await client.get(
            url_for("auth_status", app=app), headers={"Origin": "https://site", "Authorization": "Bearer ytp_key"}
        )
        assert (await response.json())["authenticated"] is True
        response = await client.get(url_for("ws", app=app))
        assert response.status == 401
        response = await client.get(
            url_for("api_value", app=app), headers={"Authorization": "Bearer ytp_key", "Origin": "https://site"}
        )
        assert response.status == 200
        headers = cors_headers(make_mocked_request("GET", "/", headers={"Origin": "https://site"}), config)
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Credentials" not in headers
        response = await client.get(
            url_for("api_value", app=app, query={"apikey": "dXNlcjpwYXNz"}), headers={"Origin": "https://site"}
        )
        assert response.status == 200
        response = await client.options(url_for("api_value_options", app=app), headers={"Origin": "https://site"})
        assert response.status == 200
        preflight = cors_headers(make_mocked_request("OPTIONS", "/", headers={"Origin": "https://site"}), config)
        assert "Authorization" in preflight["Access-Control-Allow-Headers"]
        assert preflight["Access-Control-Max-Age"] == "900"
    finally:
        await client.close()
        config.disable_auth = False


@pytest.mark.asyncio
async def test_basic_api_key() -> None:
    async def handler(_: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    def header(username: str, secret: str) -> dict[str, str]:
        encoded = base64.b64encode(f"{username}:{secret}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    config = Config.get_instance()
    config.disable_auth = False
    config.base_path = "/"
    app = web.Application(middlewares=[auth_middleware(FakeAuth(), config)])
    app.router.add_get("/api/value", handler, name="api_value")
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        assert (await client.get(url_for("api_value", app=app), headers=header("user", "ytp_key"))).status == 200
        assert (await client.get(url_for("api_value", app=app), headers=header("other", "ytp_key"))).status == 401
        assert (await client.get(url_for("api_value", app=app), headers=header("user", "ytp_missing"))).status == 401
        assert (await client.get(url_for("api_value", app=app), headers=header("user", "ytp_password"))).status == 200
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_login_logout_cookie() -> None:
    Cache.get_instance().clear()
    config = Config.get_instance()
    config.disable_auth = False
    config.base_path = "/"
    auth = FakeAuth()
    login = await auth_login(JsonRequest({"username": "user", "password": "pass"}), config, auth)
    assert login.status == 200
    assert "ytp_session" in login.cookies
    logout = await auth_logout(JsonRequest({}, {"ytp_session": "session"}), config, auth)
    assert logout.status == 204
    assert auth.revoked == "session"
    Cache.get_instance().clear()


@pytest.mark.asyncio
async def test_login_rate_limit() -> None:
    cache = Cache.get_instance()
    cache.clear()
    config = Config.get_instance()
    config.disable_auth = False
    auth = FakeAuth()
    try:
        for _ in range(5):
            response = await auth_login(JsonRequest({"username": "user", "password": "wrong"}), config, auth)
            assert response.status == web.HTTPUnauthorized.status_code
        response = await auth_login(JsonRequest({"username": "user", "password": "wrong"}), config, auth)
        assert response.status == web.HTTPTooManyRequests.status_code
        assert response.headers["Retry-After"] == "60"
    finally:
        cache.clear()


def test_access_log_redaction() -> None:
    logger = Mock(spec=logging.Logger)
    access = HttpAccessLogger(logger, AccessLogger.LOG_FORMAT)
    request = make_mocked_request(
        "GET",
        "/api/value?api%6bey=api-secret&keep=yes&ticket=ticket-secret",
        headers={"Referer": "https://example.test/?apikey=referer-secret"},
    )

    access.log(request, web.Response(status=200), 0.1)

    call = logger.info.call_args
    assert call is not None
    assert "api-secret" not in repr(call)
    assert "ticket-secret" not in repr(call)
    assert "referer-secret" not in repr(call)
    assert "apikey=[REDACTED]" in call.args[0]
    assert "ticket=[REDACTED]" in call.args[0]
    assert redact_url("/api?APIKEY=secret&value=kept") == "/api?APIKEY=[REDACTED]&value=kept"


@pytest.mark.asyncio
async def test_download_redirect_requires_auth(monkeypatch, tmp_path) -> None:
    redirected = False

    def get_file(**_kwargs):
        nonlocal redirected
        redirected = True
        return tmp_path / "Title [abcdefghijk].mp4", web.HTTPFound.status_code

    async def handler(_: web.Request) -> web.Response:
        return web.Response(text="file")

    config = Config.get_instance()
    config.disable_auth = False
    config.base_path = "/"
    config.download_path = str(tmp_path)
    api = object.__new__(HttpAPI)
    api.config = config

    def add_routes(app: web.Application) -> None:
        app.router.add_get("/api/download/{filename:.+}", handler, name="download_static")

    monkeypatch.setattr(api, "add_routes", add_routes)
    monkeypatch.setattr("app.library.HttpAPI.get_file", get_file)
    app = web.Application()
    api.attach(app)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.get("/api/download/[abcdefghijk].mp4", allow_redirects=False)
        assert response.status == web.HTTPUnauthorized.status_code
        assert not redirected
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_account_duplicate() -> None:
    config = Config.get_instance()
    config.disable_auth = False
    auth = FakeAuth()
    request = JsonRequest({"current_password": "pass", "username": "taken"})
    request[AUTH_USER_KEY] = {"id": 1, "username": "user"}
    response = await auth_account(request, config, auth)
    assert response.status == 409


@pytest.mark.asyncio
async def test_auth_middleware_allowlist() -> None:
    async def handler(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    config = Config.get_instance()
    config.disable_auth = False
    config.cors_origins = "https://allowed"
    config.base_path = "/"
    app = web.Application(middlewares=[auth_middleware(FakeAuth(), config)])
    app.router.add_get("/api/value", handler, name="api_value")
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        response = await client.get(url_for("api_value", app=app), headers={"Origin": "https://denied"})
        assert response.status == 403
        response = await client.get(
            url_for("api_value", app=app), headers={"Origin": "https://allowed", "Authorization": "Bearer ytp_key"}
        )
        assert response.status == 200
        headers = cors_headers(make_mocked_request("GET", "/", headers={"Origin": "https://allowed"}), config)
        assert headers["Access-Control-Allow-Origin"] == "https://allowed"
        assert headers["Vary"] == "Origin"
    finally:
        await client.close()
        config.disable_auth = False


@pytest.mark.asyncio
async def test_disable_auth_public() -> None:
    async def handler(_: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    config = Config.get_instance()
    config.disable_auth = True
    config.cors_origins = "*"
    config.base_path = "/"
    app = web.Application(middlewares=[auth_middleware(FakeAuth(), config)])
    for name in AUTH_ROUTE_NAMES:
        method, path = production_auth_route(name)
        app.router.add_route(method, path, handler, name=name)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        assert (await client.get(url_for("auth_status", app=app))).status == 200
        for name in AUTH_ROUTE_NAMES[1:]:
            method, _ = production_auth_route(name)
            response = await client.request(
                method, url_for(name, app=app, key_id="1") if name.endswith("delete") else url_for(name, app=app)
            )
            assert response.status == 403
            assert (await response.json())["code"] == "FEATURE_DISABLED"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_ws_ticket_authentication() -> None:
    async def handler(_: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    config = Config.get_instance()
    config.disable_auth = False
    config.cors_origins = "*"
    config.base_path = "/"
    app = web.Application(middlewares=[auth_middleware(TicketAuth(), config)])
    app.router.add_get("/ws", handler, name="ws")
    app.router.add_get("/api/value", handler, name="api_value")
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        response = await client.get(
            url_for("ws", app=app, query={"ticket": "ytp_ws_valid"}), headers={"Origin": "https://frontend.example"}
        )
        assert response.status == 200
        response = await client.get(
            url_for("ws", app=app, query={"ticket": "ytp_ws_valid"}), headers={"Origin": "https://frontend.example"}
        )
        assert response.status == 401
        response = await client.get(url_for("api_value", app=app, query={"ticket": "ytp_ws_valid"}))
        assert response.status == 401
    finally:
        await client.close()
        config.disable_auth = False


@pytest.mark.asyncio
async def test_ws_disabled_auth() -> None:
    async def handler(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    config = Config.get_instance()
    config.disable_auth = True
    config.base_path = "/"
    app = web.Application(middlewares=[auth_middleware(FakeAuth(), config)])
    app.router.add_get("/ws", handler, name="ws")
    method, path = production_auth_route("auth_ws_ticket")
    app.router.add_route(method, path, handler, name="auth_ws_ticket")
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        assert (await client.get(url_for("ws", app=app))).status == 200
        response = await client.post(url_for("auth_ws_ticket", app=app))
        assert response.status == 403
        assert (await response.json())["code"] == "FEATURE_DISABLED"
    finally:
        await client.close()
        config.disable_auth = False
