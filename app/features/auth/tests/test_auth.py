from __future__ import annotations

import base64
import hashlib
import logging
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request
from aiohttp.web_log import AccessLogger
from pydantic import ValidationError

from app.features.auth.schemas import Credentials
from app.features.auth.service import password_hash, password_matches
from app.features.auth.service import AuthService
from app.scripts import reset_password
from app.library import migrate
from app.features.auth.middleware import (
    AUTH_USER_KEY,
    auth_middleware,
    cors_headers,
    decode_basic_credentials,
    is_cross_origin,
    resolve_client_ip,
)
from app.features.auth.router import (
    auth_account,
    auth_login,
    auth_logout,
    auth_session_delete,
    auth_sessions_delete,
)
from app.library.cache import Cache
from app.library.config import Config
from app.library.HttpAPI import HttpAccessLogger, HttpAPI, redact_url
from app.library.sqlite_store import SqliteStore
from app.library.router import ROUTES, RouteType, add_route, get_route, get_routes
from app.tests.helpers import make_in_memory_db_path, url_for


AUTH_ROUTE_NAMES = (
    "auth_status",
    "auth_setup",
    "auth_login",
    "auth_logout",
    "auth_sessions",
    "auth_session_delete",
    "auth_sessions_delete",
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
    with pytest.raises(ValueError):
        await password_hash("")


def test_reset_command_input(monkeypatch, capsys) -> None:
    values = iter(("secret", "different"))
    monkeypatch.setattr(reset_password, "getpass", lambda _: next(values))

    async def reset(username: str) -> None:
        assert username == "owner"
        reset_password._confirmed_password()

    monkeypatch.setattr(reset_password, "reset", reset)

    assert reset_password.main(["--username", "owner"]) == 1
    output = capsys.readouterr()
    assert "do not match" in output.err
    assert "secret" not in output.err
    assert "different" not in output.err


def test_native_reset_forwarding(monkeypatch) -> None:
    import app.local as local_module

    reset = Mock(return_value=0)
    monkeypatch.setattr(local_module, "set_env", lambda: None)
    monkeypatch.setattr(reset_password, "main", reset)
    monkeypatch.setattr("sys.argv", ["local.py", "--reset-password", "--username", "owner"])

    with pytest.raises(SystemExit) as exc_info:
        local_module.main()
    assert exc_info.value.code == 0
    reset.assert_called_once_with(["--username", "owner"])


def test_native_reset_username(monkeypatch, capsys) -> None:
    import app.local as local_module

    monkeypatch.setattr(local_module, "set_env", lambda: None)
    monkeypatch.setattr("sys.argv", ["local.py", "--reset-password"])

    with pytest.raises(SystemExit) as exc_info:
        local_module.main()
    assert exc_info.value.code == 2
    assert "--username is required" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_reset_missing_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("YTP_CONFIG_PATH", str(tmp_path))
    db_file = Path(tmp_path) / "ytptube.db"
    monkeypatch.setattr(reset_password, "getpass", lambda _: pytest.fail("password was requested"))

    with pytest.raises(ValueError):
        await reset_password.reset("owner")
    assert not db_file.exists()


@pytest.mark.asyncio
async def test_reset_checks_username(monkeypatch, tmp_path, capsys) -> None:
    db_file = Path(tmp_path) / "ytptube.db"
    await migrate.upgrade(str(db_file), "app/migrations")
    config = Config.get_instance()
    previous_db = config.db_file
    config.db_file = str(db_file)
    monkeypatch.setattr(reset_password, "getpass", lambda _: pytest.fail("password was requested"))
    capsys.readouterr()

    try:
        with pytest.raises(ValueError, match="not found"):
            await reset_password.reset("missing")
        output = capsys.readouterr()
        assert output.out == f"Database: {db_file.resolve()}\n"
        assert not output.err
    finally:
        config.db_file = previous_db
        SqliteStore._reset_singleton()


def test_basic_query_padding() -> None:
    assert decode_basic_credentials("dXNlcjpwYXNz") == ("user", "pass")
    assert decode_basic_credentials("not-basic") is None


@pytest.mark.asyncio
async def test_auth_migration(tmp_path) -> None:
    path = tmp_path / "auth.db"
    await migrate.upgrade(str(path), "app/migrations")
    with closing(sqlite3.connect(path)) as database:
        tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        columns = {row[1] for row in database.execute('PRAGMA table_info("sessions")')}
    assert {"users", "sessions", "api_keys"} <= tables
    assert {"user_agent", "ip"} <= columns


@pytest.mark.asyncio
async def test_session_metadata_migration(tmp_path) -> None:
    path = tmp_path / "session-metadata.db"
    await migrate.upgrade(str(path), "app/migrations", "20260817160639")
    with closing(sqlite3.connect(path)) as database:
        database.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("owner", "hash"))
        database.execute(
            "INSERT INTO sessions (token_digest, user_id, expires_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            ("digest", 1),
        )
        database.commit()
    await migrate.upgrade(str(path), "app/migrations", "20260820144657")
    with closing(sqlite3.connect(path)) as database:
        columns = {row[1] for row in database.execute('PRAGMA table_info("sessions")')}
        count = database.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert {"user_agent", "ip"} <= columns
    assert count == 0


def test_proxy_resolution() -> None:
    def request(remote: str, forwarded: str):
        transport = Mock()
        transport.get_extra_info.return_value = (remote, 123)
        return make_mocked_request("GET", "/", transport=transport, headers={"X-Forwarded-For": forwarded})

    config = Config.get_instance()
    previous = config.trusted_proxies
    try:
        config.trusted_proxies = ""
        assert resolve_client_ip(request("198.51.100.10", "203.0.113.5"), config) == "198.51.100.10"
        config.trusted_proxies = "198.51.100.10"
        assert resolve_client_ip(request("198.51.100.10", "203.0.113.5"), config) == "203.0.113.5"
        config.trusted_proxies = "10.0.0.0/24"
        assert resolve_client_ip(request("10.0.0.2", "203.0.113.5, 10.0.0.1"), config) == "203.0.113.5"
        assert resolve_client_ip(request("10.0.0.2", "invalid"), config) == "10.0.0.2"
    finally:
        config.trusted_proxies = previous


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
    previous_days = config.auth_session_days
    auth = AuthService.get_instance()
    user = await auth.create_user("owner", "secret", require_empty=True)
    assert user is not None
    assert await auth.create_user("blocked", "blocked-secret", require_empty=True) is None
    other = await auth.create_user("second", "second-secret")
    assert other is not None
    assert await auth.create_user("second", "different-secret") is None
    try:
        config.auth_session_days = 3
        token = await auth.create_session(user["id"], "Browser/1", "192.0.2.1")
        owner_session = await auth.create_session(user["id"], "Browser/2", "192.0.2.2")
        expired = await auth.create_session(user["id"])
        other_token = await auth.create_session(other["id"])
        expires = (
            await store.fetch_raw(
                "SELECT expires_at FROM sessions WHERE token_digest = :digest",
                {"digest": hashlib.sha256(token.encode()).hexdigest()},
            )
        )[0]["expires_at"]
        expiry = datetime.strptime(expires, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=UTC)
        assert timedelta(days=2, hours=23) < expiry - datetime.now(UTC) < timedelta(days=3, minutes=1)
        await store.execute_raw(
            "UPDATE sessions SET expires_at = :expires WHERE token_digest = :digest",
            {
                "expires": (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S.%f"),
                "digest": hashlib.sha256(expired.encode()).hexdigest(),
            },
        )
        listed = await auth.sessions(user["id"], owner_session)
        expired_id = (
            await store.fetch_raw(
                "SELECT id FROM sessions WHERE token_digest = :digest",
                {"digest": hashlib.sha256(expired.encode()).hexdigest()},
            )
        )[0]["id"]
        assert len(listed) == 2
        assert expired_id not in {item["id"] for item in listed}
        assert [item["id"] for item in listed] == sorted((item["id"] for item in listed), reverse=True)
        assert all(set(item) == {"id", "created_at", "expires_at", "user_agent", "ip", "current"} for item in listed)
        current_item = next(item for item in listed if item["current"])
        assert current_item["user_agent"] == "Browser/2"
        assert current_item["ip"] == "192.0.2.2"
        assert sum(item["current"] for item in listed) == 1
        owner_current = next(item["id"] for item in listed if item["current"])
        token_current = next(item["id"] for item in await auth.sessions(user["id"], token) if item["current"])
        assert owner_current != token_current
        assert not any(item["id"] == owner_current for item in await auth.sessions(other["id"], owner_session))
        assert await auth.delete_session(other["id"], owner_current) is False
        assert await auth.delete_session(user["id"], owner_current)
        assert await auth.session_user(owner_session) is None
        session_user = await auth.session_user(token)
        assert session_user is not None
        assert session_user["id"] == user["id"]
        metadata, key = await auth.create_key(user["id"], "browser")
        assert metadata["name"] == "browser"
        await auth.reset_password("owner", "new secret")
        assert await auth.authenticate_password("owner", "secret") is None
        assert await auth.authenticate_password("owner", "new secret") is not None
        assert await auth.session_user(token) is None
        assert await auth.authenticate_password("second", "second-secret") is not None
        assert await auth.session_user(other_token) is not None
        key_user = await auth.user_from_key(key)
        assert key_user is not None
        assert key_user["id"] == user["id"]
        with pytest.raises(ValueError, match="not found"):
            await auth.reset_password("unknown", "another secret")
        assert await auth.authenticate_password("owner", "new secret") is not None
        assert await auth.authenticate_password("second", "second-secret") is not None
        assert await auth.session_user(other_token) is not None
        assert not await auth.delete_key(other["id"], metadata["id"])
        assert await auth.delete_key(user["id"], metadata["id"])
        assert await auth.user_from_key(key) is None
        await store.execute_raw(
            "UPDATE sessions SET expires_at = :expires",
            {"expires": (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S.%f")},
        )
        assert await auth.session_user(token) is None
        assert await auth.session_user(other_token) is None
    finally:
        config.auth_session_days = previous_days
    await store.close()
    SqliteStore._reset_singleton()


@pytest.mark.asyncio
async def test_reset_no_account(monkeypatch) -> None:
    store = SqliteStore.get_instance(db_path=make_in_memory_db_path("auth-reset-guards"))
    await store.get_connection()

    @asynccontextmanager
    async def session():
        async with store.sessionmaker()() as value:
            yield value

    import app.features.auth.service as service_module

    monkeypatch.setattr(service_module, "get_session", session)
    auth = AuthService.get_instance()
    with pytest.raises(ValueError, match="not found"):
        await auth.reset_password("missing", "secret")
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
    session_metadata: tuple[str | None, str | None]

    async def authenticate_password(self, username: str, password: str) -> dict | None:
        return {"id": 1, "username": username} if username == "user" and password in {"pass", "ytp_password"} else None

    async def user_from_key(self, key: str) -> dict | None:
        return {"id": 1, "username": "user"} if key == "ytp_key" else None

    async def session_user(self, token: str) -> dict | None:
        return {"id": 1, "username": "user"} if token == "session" else None

    async def create_session(self, user_id: int, user_agent: str | None = None, ip: str | None = None) -> str:
        self.session_metadata = (user_agent, ip)
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

    def __init__(
        self,
        payload: dict,
        cookies: dict[str, str] | None = None,
        match_info: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        remote: str = "test-client",
    ):
        super().__init__()
        self._payload = payload
        self.cookies = cookies or {}
        self.match_info = match_info or {}
        self.headers = headers or {}
        self.remote = remote

    async def json(self) -> dict:
        return self._payload


@pytest.mark.asyncio
async def test_session_routes(monkeypatch) -> None:
    store = SqliteStore.get_instance(db_path=make_in_memory_db_path("auth-routes"))
    await store.get_connection()

    @asynccontextmanager
    async def session():
        async with store.sessionmaker()() as value:
            yield value

    import app.features.auth.service as service_module

    monkeypatch.setattr(service_module, "get_session", session)
    config = Config.get_instance()
    config.disable_auth = False
    config.base_path = "/"
    auth = AuthService.get_instance()
    owner = await auth.create_user("route-owner", "secret", require_empty=True)
    other = await auth.create_user("route-other", "secret")
    assert owner is not None and other is not None
    current = await auth.create_session(owner["id"])
    extra = await auth.create_session(owner["id"])
    foreign = await auth.create_session(other["id"])
    current_id = next(item["id"] for item in await auth.sessions(owner["id"], current) if item["current"])
    foreign_id = (await auth.sessions(other["id"], foreign))[0]["id"]

    malformed = JsonRequest({}, {"ytp_session": current}, {"session_id": "invalid"})
    malformed[AUTH_USER_KEY] = owner
    assert (await auth_session_delete(malformed, auth)).status == 404
    missing = JsonRequest({}, {"ytp_session": current}, {"session_id": "99999"})
    missing[AUTH_USER_KEY] = owner
    assert (await auth_session_delete(missing, auth)).status == 404
    cross_user = JsonRequest({}, {"ytp_session": current}, {"session_id": str(foreign_id)})
    cross_user[AUTH_USER_KEY] = owner
    assert (await auth_session_delete(cross_user, auth)).status == 404

    current_request = JsonRequest({}, {"ytp_session": current}, {"session_id": str(current_id)})
    current_request[AUTH_USER_KEY] = owner
    deleted = await auth_session_delete(current_request, auth)
    assert deleted.status == 204
    assert deleted.cookies["ytp_session"]["max-age"] == "0"
    assert await auth.session_user(current) is None

    current = await auth.create_session(owner["id"])
    extra = await auth.create_session(owner["id"])
    bulk_request = JsonRequest({}, {"ytp_session": current})
    bulk_request[AUTH_USER_KEY] = owner
    assert (await auth_sessions_delete(bulk_request, auth)).status == 204
    assert await auth.session_user(current) is not None
    assert await auth.session_user(extra) is None
    assert await auth.session_user(foreign) is not None

    await store.close()
    SqliteStore._reset_singleton()


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
async def test_route_metadata_behavior(request) -> None:
    snapshot = {route_type: routes.copy() for route_type, routes in ROUTES.items()}

    def restore_routes() -> None:
        ROUTES.clear()
        ROUTES.update(snapshot)

    request.addfinalizer(restore_routes)

    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"authenticated": AUTH_USER_KEY in request})

    add_route("GET", "/metadata/same-origin", handler, name="arbitrary_same_origin", public=True, same_origin=True)
    add_route("OPTIONS", "/metadata/same-origin", handler, name="arbitrary_same_origin_options", same_origin=True)
    add_route("GET", "/metadata/optional", handler, name="arbitrary_optional", public=True, optional_auth=True)
    add_route("GET", "/metadata/cookie", handler, name="arbitrary_cookie", cookie_only=True)
    add_route("GET", "/metadata/disabled", handler, name="arbitrary_disabled", same_origin=True, auth_only=True)

    config = Config.get_instance()
    config.disable_auth = False
    config.cors_origins = "*"
    config.base_path = "/"
    app = web.Application(middlewares=[auth_middleware(FakeAuth(), config)])
    app.router.add_get("/metadata/same-origin", handler, name="arbitrary_same_origin")
    app.router.add_options("/metadata/same-origin", handler, name="arbitrary_same_origin_options")
    app.router.add_get("/metadata/optional", handler, name="arbitrary_optional")
    app.router.add_get("/metadata/cookie", handler, name="arbitrary_cookie")
    app.router.add_get("/metadata/disabled", handler, name="arbitrary_disabled")
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.get(
            url_for("arbitrary_same_origin", app=app), headers={"Origin": "https://external.example"}
        )
        assert response.status == 403
        response = await client.options(
            url_for("arbitrary_same_origin_options", app=app), headers={"Origin": "https://external.example"}
        )
        assert response.status == 200
        response = await client.get(url_for("arbitrary_optional", app=app), headers={"Authorization": "Bearer ytp_key"})
        assert (await response.json())["authenticated"] is True
        response = await client.get(url_for("arbitrary_optional", app=app))
        assert (await response.json())["authenticated"] is False
        response = await client.get(url_for("arbitrary_cookie", app=app), headers={"Authorization": "Bearer ytp_key"})
        assert response.status == 400
        response = await client.get(url_for("arbitrary_cookie", app=app), cookies={"ytp_session": "session"})
        assert response.status == 200
        config.disable_auth = True
        response = await client.get(
            url_for("arbitrary_disabled", app=app), headers={"Origin": "https://external.example"}
        )
        assert response.status == 403
        assert (await response.json())["code"] == "FEATURE_DISABLED"
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
    previous_days = config.auth_session_days
    config.auth_session_days = 11
    try:
        login = await auth_login(
            JsonRequest(
                {"username": "user", "password": "pass"},
                headers={"User-Agent": "Test Browser"},
                remote="192.0.2.44",
            ),
            config,
            auth,
        )
        assert login.status == 200
        assert "ytp_session" in login.cookies
        assert login.cookies["ytp_session"]["max-age"] == str(11 * 86400)
        assert auth.session_metadata == ("Test Browser", "192.0.2.44")
        logout = await auth_logout(JsonRequest({}, {"ytp_session": "session"}), config, auth)
        assert logout.status == 204
        assert auth.revoked == "session"
    finally:
        config.auth_session_days = previous_days
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
                method,
                url_for(name, app=app, session_id="1")
                if name == "auth_session_delete"
                else url_for(name, app=app, key_id="1")
                if name == "auth_api_keys_delete"
                else url_for(name, app=app),
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
