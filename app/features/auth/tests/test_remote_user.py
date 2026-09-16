from __future__ import annotations

import ipaddress
import json
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from app.features.auth.middleware import AUTH_METHOD_KEY, AUTH_USER_KEY, auth_middleware
from app.features.auth.service import AuthService
from app.library.config import Config, ExternalAuthConfig, RemoteUserConfig


def config(remote: str = "10.0.0.0/8") -> Config:
    value = Config.get_instance()
    value.disable_auth = False
    value.external_auth = ExternalAuthConfig(
        external_user="owner",
        oidc=None,
        remote_user=RemoteUserConfig(
            enabled=True, header="Remote-User", trusted_proxies=(ipaddress.ip_network(remote),)
        ),
    )
    return value


def make_request(headers: object, remote: str) -> web.Request:
    transport = Mock()
    transport.get_extra_info.return_value = (remote, 0)
    return make_mocked_request("GET", "/", headers=headers, transport=transport)


async def run(request: web.Request, auth: AuthService, cfg: Config) -> web.Response:
    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"user": request.get(AUTH_USER_KEY), "method": request.get(AUTH_METHOD_KEY)})

    response = await auth_middleware(auth, cfg)(request, handler)
    assert isinstance(response, web.Response)
    return response


@pytest.mark.asyncio
async def test_trusted_header_authenticates() -> None:
    request = make_request({"Remote-User": "asserted"}, "10.1.2.3")
    auth: AuthService = Mock(spec=AuthService)
    auth.find_user = AsyncMock(return_value={"id": 1, "username": "owner"})

    response = await run(request, auth, config())
    assert response.status == 200
    assert response.text == '{"user": {"id": 1, "username": "owner"}, "method": "remote_user"}'


@pytest.mark.asyncio
async def test_untrusted_header_rejected() -> None:
    request = make_request({"Remote-User": "asserted", "X-Forwarded-For": "10.1.2.3"}, "192.0.2.1")
    auth: AuthService = Mock(spec=AuthService)
    find_user = AsyncMock()
    auth.find_user = find_user

    response = await run(request, auth, config())
    assert response.status == 401
    find_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_ambiguous_header_rejected() -> None:
    request = make_request([("Remote-User", "a"), ("Remote-User", "b")], "10.1.2.3")
    auth: AuthService = Mock(spec=AuthService)
    auth.find_user = AsyncMock()

    response = await run(request, auth, config())
    assert response.status == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [None, {"Remote-User": " "}, {"Remote-User": "a,b"}])
async def test_invalid_header(headers: object) -> None:
    auth: AuthService = Mock(spec=AuthService)
    auth.find_user = AsyncMock()
    response = await run(make_request(headers or {}, "10.1.2.3"), auth, config())
    assert response.status == 401


@pytest.mark.asyncio
async def test_ipv6_header_authenticates() -> None:
    auth: AuthService = Mock(spec=AuthService)
    auth.find_user = AsyncMock(return_value={"id": 1})
    response = await run(make_request({"Remote-User": "asserted"}, "2001:db8::1"), auth, config("2001:db8::/32"))
    assert response.status == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{"Origin": "https://other"}, {"Sec-Fetch-Site": "cross-site"}])
async def test_cross_origin_rejected(headers: dict[str, str]) -> None:
    auth: AuthService = Mock(spec=AuthService)
    auth.find_user = AsyncMock()
    response = await run(make_request({**headers, "Remote-User": "asserted"}, "10.1.2.3"), auth, config())
    assert response.status in {401, 403}


@pytest.mark.asyncio
async def test_missing_account_rejected() -> None:
    auth: AuthService = Mock(spec=AuthService)
    auth.find_user = AsyncMock(return_value=None)
    response = await run(make_request({"Remote-User": "asserted"}, "10.1.2.3"), auth, config())
    assert response.status == 401


@pytest.mark.asyncio
async def test_disabled_rejected() -> None:
    auth: AuthService = Mock(spec=AuthService)
    find_user = AsyncMock()
    auth.find_user = find_user
    cfg = config()
    cfg.disable_auth = True
    response = await run(make_request({"Remote-User": "asserted"}, "10.1.2.3"), auth, cfg)
    assert response.status == 200
    find_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_cookie_sets_method() -> None:
    auth: AuthService = Mock(spec=AuthService)
    auth.find_user = AsyncMock()
    auth.session_user = AsyncMock(return_value={"id": 1})
    request = make_request({"Cookie": "ytp_session=token"}, "10.1.2.3")
    response = await run(request, auth, config())
    assert response.status == 200
    assert response.text is not None
    assert json.loads(response.text)["method"] == "session"
