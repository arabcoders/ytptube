from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from aiohttp.test_utils import make_mocked_request
from joserfc import jwt
from joserfc.jwk import generate_key

from app.features.auth.router import _oidc_metadata, auth_status, oidc_callback, oidc_login
from app.library.cache import Cache


def config() -> SimpleNamespace:
    return SimpleNamespace(
        disable_auth=False,
        base_path="/app",
        auth_session_days=30,
        external_auth=SimpleNamespace(
            external_user="owner",
            oidc=SimpleNamespace(
                issuer="https://issuer.example",
                client_id="client",
                client_secret="secret",
                redirect_uri="https://app.example/api/auth/oidc/callback",
            ),
        ),
    )


KEY = generate_key("RSA", 2048, auto_kid=True)
OTHER_KEY = generate_key("RSA", 2048, auto_kid=True)


def token(key=KEY, **changes: object) -> str:
    now = 1_700_000_000
    claims: dict[str, Any] = {
        "iss": "https://issuer.example",
        "aud": "client",
        "exp": 2_000_000_000,
        "iat": now,
        "nonce": "nonce",
        "sub": "subject",
    }
    claims.update(changes)
    claims.pop("_missing", None)
    missing = changes.get("_missing")
    if isinstance(missing, str):
        claims.pop(missing)
    return jwt.encode({"alg": "RS256", "kid": key.as_dict()["kid"]}, claims, key)


def request(state: str = "state") -> object:
    return make_mocked_request(
        "GET", f"/api/auth/oidc/callback?state={state}&code=code", headers={"Cookie": f"oidc_state={state}"}
    )


def pending(state: str = "state") -> None:
    cache = Cache.get_instance()
    cache.clear()
    cache.set(cache.hash(f"oidc:{state}"), {"verifier": "verifier", "nonce": "nonce"})


def client(token_value: str) -> SimpleNamespace:
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id_token": token_value})
    jwks = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"keys": [KEY.as_dict()]})
    return SimpleNamespace(post=AsyncMock(return_value=response), get=AsyncMock(return_value=jwks))


def metadata(**changes: object) -> dict:
    result = {
        "token_endpoint": "https://issuer.example/token",
        "jwks_uri": "https://issuer.example/jwks",
        "id_token_signing_alg_values_supported": ["RS256"],
    }
    result.update(changes)
    return result


@pytest.mark.asyncio
async def test_login_params() -> None:
    cache = Cache.get_instance()
    cache.clear()
    auth = SimpleNamespace(find_user=AsyncMock(return_value={"id": 1, "username": "owner"}))
    with patch(
        "app.features.auth.router._oidc_metadata",
        AsyncMock(return_value={"authorization_endpoint": "https://issuer.example/authorize"}),
    ):
        response = await oidc_login(config(), auth)
    values = parse_qs(urlsplit(response.location).query)
    assert values["response_type"] == ["code"]
    assert values["code_challenge_method"] == ["S256"]
    state = values["state"][0]
    binding = cache.get(cache.hash(f"oidc:{state}"))
    assert isinstance(binding, dict)
    assert binding["nonce"] == values["nonce"][0]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(binding["verifier"].encode()).digest()).rstrip(b"=").decode()
    assert challenge == values["code_challenge"][0]
    cookie = response.cookies["oidc_state"]
    assert cookie.value == state
    assert cookie["httponly"] and cookie["secure"]
    assert cookie["samesite"] == "Lax" and cookie["path"] == "/app" and cookie["max-age"] == "300"


@pytest.mark.asyncio
async def test_state_binding() -> None:
    request = make_mocked_request(
        "GET", "/api/auth/oidc/callback?state=one&code=x", headers={"Cookie": "oidc_state=two"}
    )
    response = await oidc_callback(request, config(), SimpleNamespace())
    assert response.status == 400


@pytest.mark.asyncio
async def test_state_logging(caplog: pytest.LogCaptureFixture) -> None:
    secrets = ("state-secret-value", "cookie-secret-value", "code-secret-value")
    request = make_mocked_request(
        "GET",
        f"/api/auth/oidc/callback?state={secrets[0]}&code={secrets[2]}",
        headers={"Cookie": f"oidc_state={secrets[1]}"},
    )
    response = await oidc_callback(request, config(), SimpleNamespace())
    assert response.status == 400
    assert b"OIDC authentication failed." in response.body
    assert "state parameter does not match state cookie" in caplog.text
    assert all(secret not in caplog.text for secret in secrets)


@pytest.mark.asyncio
async def test_login_failure(caplog: pytest.LogCaptureFixture) -> None:
    settings = config()
    auth = SimpleNamespace(find_user=AsyncMock(return_value={"id": 1}))
    with patch("app.features.auth.router._oidc_metadata", AsyncMock(side_effect=RuntimeError("failure"))):
        response = await oidc_login(settings, auth)
    assert response.status == 502
    assert b"OIDC authentication failed." in response.body
    assert "provider discovery" in caplog.text


@pytest.mark.asyncio
async def test_discovery_issuer() -> None:
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"issuer": "wrong"})
    with patch("app.features.auth.router.httpx.AsyncClient.get", AsyncMock(return_value=response)):
        with pytest.raises(ValueError):
            await _oidc_metadata("https://issuer.example")


@pytest.mark.asyncio
async def test_status_disabled() -> None:
    settings = config()
    settings.disable_auth = True
    request = make_mocked_request("GET", "/api/auth/status")
    response = await auth_status(request, settings, SimpleNamespace(find_user=AsyncMock(return_value={"id": 1})))
    assert response.status == 200
    assert response.body is not None and b'"oidc_available": false' in response.body


@pytest.mark.asyncio
async def test_callback_success() -> None:
    pending()
    auth = SimpleNamespace(
        find_user=AsyncMock(return_value={"id": 1}), create_session=AsyncMock(return_value="session")
    )
    http = client(token())
    with (
        patch("app.features.auth.router._oidc_metadata", AsyncMock(return_value=metadata())),
        patch(
            "app.features.auth.router.httpx.AsyncClient",
            return_value=MagicMock(__aenter__=AsyncMock(return_value=http), __aexit__=AsyncMock()),
        ),
    ):
        response = await oidc_callback(request(), config(), auth)
    assert response.status == 302 and response.location == "/app"
    assert http.post.call_args.kwargs["auth"] == ("client", "secret")
    assert http.post.call_args.kwargs["data"]["code_verifier"] == "verifier"
    assert "client_secret" not in http.post.call_args.kwargs["data"]
    assert auth.create_session.await_count == 1
    assert response.cookies["ytp_session"]["secure"] and response.cookies["ytp_session"]["httponly"]
    assert response.cookies["ytp_session"]["samesite"] == "Strict"
    assert response.cookies["oidc_state"].value == ""
    assert not Cache.get_instance().has(Cache.get_instance().hash("oidc:state"))


@pytest.mark.asyncio
async def test_callback_replay() -> None:
    pending()
    auth = SimpleNamespace(find_user=AsyncMock(), create_session=AsyncMock())
    http = client(token())
    with (
        patch("app.features.auth.router._oidc_metadata", AsyncMock(return_value=metadata())),
        patch(
            "app.features.auth.router.httpx.AsyncClient",
            return_value=MagicMock(__aenter__=AsyncMock(return_value=http), __aexit__=AsyncMock()),
        ),
    ):
        await oidc_callback(request(), config(), auth)
        response = await oidc_callback(request(), config(), auth)
    assert response.status == 400 and http.post.await_count == 1 and auth.create_session.await_count == 1


@pytest.mark.asyncio
async def test_provider_error() -> None:
    pending()
    http = client(token())
    auth = SimpleNamespace(find_user=AsyncMock(), create_session=AsyncMock())
    with patch(
        "app.features.auth.router.httpx.AsyncClient",
        return_value=MagicMock(__aenter__=AsyncMock(return_value=http), __aexit__=AsyncMock()),
    ):
        response = await oidc_callback(
            make_mocked_request("GET", "/?state=state&error=denied", headers={"Cookie": "oidc_state=state"}),
            config(),
            auth,
        )
    assert (
        response.status == 400
        and http.post.await_count == 0
        and not Cache.get_instance().has(Cache.get_instance().hash("oidc:state"))
    )


@pytest.mark.asyncio
async def test_provider_logging(caplog: pytest.LogCaptureFixture) -> None:
    pending()
    secret = "provider-description-secret"
    response = await oidc_callback(
        make_mocked_request(
            "GET",
            f"/?state=state&error=access_denied&error_description={secret}",
            headers={"Cookie": "oidc_state=state"},
        ),
        config(),
        SimpleNamespace(),
    )
    assert response.status == 400
    assert b"OIDC authentication failed." in response.body
    assert "provider rejected authentication" in caplog.text
    assert secret not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "wrong"},
        {"aud": "wrong"},
        {"nonce": "wrong"},
        {"exp": 1},
        {"_missing": "exp"},
        {"_missing": "iat"},
        {"iat": 2_000_000_100},
        {"sub": None},
        {"sub": ""},
        {"azp": "wrong"},
        {"aud": ["client", "other"]},
        {"_key": OTHER_KEY},
    ],
)
async def test_rejected_claims(changes: dict[str, object]) -> None:
    pending()
    auth = SimpleNamespace(find_user=AsyncMock(return_value={"id": 1}), create_session=AsyncMock())
    key = changes.pop("_key", KEY)
    http = client(token(key=key, **changes))
    with (
        patch("app.features.auth.router._oidc_metadata", AsyncMock(return_value=metadata())),
        patch(
            "app.features.auth.router.httpx.AsyncClient",
            return_value=MagicMock(__aenter__=AsyncMock(return_value=http), __aexit__=AsyncMock()),
        ),
    ):
        response = await oidc_callback(request(), config(), auth)
    assert response.status == 400 and auth.create_session.await_count == 0


@pytest.mark.asyncio
async def test_missing_user() -> None:
    pending()
    auth = SimpleNamespace(find_user=AsyncMock(return_value=None), create_session=AsyncMock())
    http = client(token())
    with (
        patch("app.features.auth.router._oidc_metadata", AsyncMock(return_value=metadata())),
        patch(
            "app.features.auth.router.httpx.AsyncClient",
            return_value=MagicMock(__aenter__=AsyncMock(return_value=http), __aexit__=AsyncMock()),
        ),
    ):
        response = await oidc_callback(request(), config(), auth)
    assert response.status == 400 and auth.create_session.await_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["HS256", "none"])
async def test_unsupported_algorithm(algorithm: str) -> None:
    pending()
    auth = SimpleNamespace(find_user=AsyncMock(return_value={"id": 1}), create_session=AsyncMock())
    http = client(token())
    with (
        patch(
            "app.features.auth.router._oidc_metadata",
            AsyncMock(return_value=metadata(id_token_signing_alg_values_supported=[algorithm])),
        ),
        patch(
            "app.features.auth.router.httpx.AsyncClient",
            return_value=MagicMock(__aenter__=AsyncMock(return_value=http), __aexit__=AsyncMock()),
        ),
    ):
        response = await oidc_callback(request(), config(), auth)
    assert response.status == 400 and auth.create_session.await_count == 0
