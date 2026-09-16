from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
from aiohttp import web
from joserfc import jwt
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry
from pydantic import ValidationError

from app.features.auth.middleware import AUTH_METHOD_KEY, AUTH_USER_KEY, resolve_client_ip
from app.features.auth.schemas import AccountPatch, ApiKeyCreate, Credentials
from app.features.auth.service import AuthService
from app.features.core.utils import api_error_response, format_validation_errors
from app.library.cache import Cache
from app.library.config import Config
from app.library.logging import get_logger
from app.library.router import route

LOG = get_logger()


def _user(request: web.Request) -> dict | None:
    value = request.get(AUTH_USER_KEY)
    return value if isinstance(value, dict) else None


def _disabled() -> web.Response:
    return api_error_response(
        "Authentication is disabled.", code="FEATURE_DISABLED", status=web.HTTPForbidden.status_code
    )


def _rate_limited() -> web.Response:
    return api_error_response(
        "Too many login attempts.",
        code="TOO_MANY_REQUESTS",
        status=web.HTTPTooManyRequests.status_code,
        headers={"Retry-After": "60"},
    )


def _payload_error(exc: ValidationError) -> web.Response:
    return api_error_response(
        "Invalid request payload.",
        code="BAD_REQUEST",
        status=web.HTTPBadRequest.status_code,
        detail=format_validation_errors(exc),
    )


async def _credentials(request: web.Request) -> Credentials | web.Response:
    try:
        return Credentials.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        return api_error_response("Invalid request payload.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)


def _session_response(request: web.Request, user: dict, token: str, status: int = 200) -> web.Response:
    response = web.json_response(data={"user": user}, status=status)
    response.set_cookie(
        "ytp_session",
        token,
        max_age=Config.get_instance().auth_session_days * 24 * 60 * 60,
        httponly=True,
        samesite="Strict",
        secure=request.secure,
        path=Config.get_instance().base_path,
    )
    return response


@route("GET", "api/auth/status", "auth_status", public=True, optional_auth=True)
async def auth_status(request: web.Request, config: Config, auth: AuthService) -> web.Response:
    user = _user(request)
    return web.json_response(
        data={
            "disabled": config.disable_auth,
            "setup_required": False if config.disable_auth else await auth.user_count() == 0,
            "authenticated": user is not None,
            "user": user,
            "auth_method": request.get(AUTH_METHOD_KEY),
            "oidc_available": bool(
                config.external_auth.oidc
                and not config.disable_auth
                and config.external_auth.external_user
                and await auth.find_user(config.external_auth.external_user) is not None
            ),
        }
    )


async def _oidc_metadata(issuer: str) -> dict:
    async with httpx.AsyncClient(follow_redirects=False) as client:
        response = await client.get(issuer.rstrip("/") + "/.well-known/openid-configuration")
        response.raise_for_status()
        metadata = response.json()

    required = ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")
    if metadata.get("issuer") != issuer or any(
        not isinstance(metadata.get(key), str) or not metadata[key] for key in required
    ):
        raise ValueError from None

    return metadata


@route("GET", "api/auth/oidc/login", "auth_oidc_login", public=True, auth_only=True)
async def oidc_login(config: Config, auth: AuthService) -> web.Response:
    oidc = config.external_auth.oidc

    if config.disable_auth:
        LOG.warning("OIDC login unavailable: authentication is disabled.")
        return api_error_response("OIDC authentication failed.", code="NOT_FOUND", status=web.HTTPNotFound.status_code)

    if oidc is None:
        LOG.warning("OIDC login unavailable: OIDC is not configured.")
        return api_error_response("OIDC authentication failed.", code="NOT_FOUND", status=web.HTTPNotFound.status_code)

    if not config.external_auth.external_user:
        LOG.warning("OIDC login unavailable: external user mapping is missing.")
        return api_error_response("OIDC authentication failed.", code="NOT_FOUND", status=web.HTTPNotFound.status_code)

    stage = "mapped user lookup"

    try:
        if await auth.find_user(config.external_auth.external_user) is None:
            LOG.warning("OIDC login unavailable: mapped user does not exist.")
            return api_error_response(
                "OIDC authentication failed.", code="NOT_FOUND", status=web.HTTPNotFound.status_code
            )

        stage = "provider discovery"
        metadata = await _oidc_metadata(oidc.issuer)

        stage = "authorization request setup"
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        nonce = secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        Cache.get_instance().set(
            Cache.get_instance().hash(f"oidc:{state}"), {"verifier": verifier, "nonce": nonce}, ttl=300
        )
        params = {
            "client_id": oidc.client_id,
            "redirect_uri": oidc.redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }

        response = web.HTTPFound(f"{metadata['authorization_endpoint']}?{urlencode(params)}")
        response.set_cookie(
            "oidc_state",
            state,
            max_age=300,
            httponly=True,
            samesite="Lax",
            secure=oidc.redirect_uri.startswith("https://"),
            path=config.base_path,
        )

        return response
    except Exception:
        LOG.exception("OIDC login failed during %s.", stage)
        return api_error_response(
            "OIDC authentication failed.", code="OPERATION_FAILED", status=web.HTTPBadGateway.status_code
        )


@route("GET", "api/auth/oidc/callback", "auth_oidc_callback", public=True, auth_only=True)
async def oidc_callback(request: web.Request, config: Config, auth: AuthService) -> web.Response:
    oidc = config.external_auth.oidc
    state = request.query.get("state", "")
    binding = request.cookies.get("oidc_state", "")

    response: web.Response
    if config.disable_auth:
        LOG.warning("OIDC callback rejected: authentication is disabled.")
        response = api_error_response(
            "OIDC authentication failed.", code="OPERATION_FAILED", status=web.HTTPBadRequest.status_code
        )
    elif oidc is None:
        LOG.warning("OIDC callback rejected: OIDC is not configured.")
        response = api_error_response(
            "OIDC authentication failed.", code="OPERATION_FAILED", status=web.HTTPBadRequest.status_code
        )
    elif not state:
        LOG.warning("OIDC callback rejected: state parameter is missing.")
        response = api_error_response(
            "OIDC authentication failed.", code="OPERATION_FAILED", status=web.HTTPBadRequest.status_code
        )
    elif not binding:
        LOG.warning("OIDC callback rejected: state cookie is missing.")
        response = api_error_response(
            "OIDC authentication failed.", code="OPERATION_FAILED", status=web.HTTPBadRequest.status_code
        )
    elif not secrets.compare_digest(state, binding):
        LOG.warning("OIDC callback rejected: state parameter does not match state cookie.")
        response = api_error_response(
            "OIDC authentication failed.", code="OPERATION_FAILED", status=web.HTTPBadRequest.status_code
        )
    else:
        cache = Cache.get_instance()
        key = cache.hash(f"oidc:{state}")
        pending = cache.get(key)
        cache.delete(key)

        try:
            if pending is None:
                LOG.warning("OIDC callback rejected: pending state is expired or already consumed.")
                raise web.HTTPBadRequest  # noqa: TRY301

            if request.query.get("error"):
                LOG.warning("OIDC callback rejected: provider rejected authentication.")
                raise web.HTTPBadRequest  # noqa: TRY301

            if not request.query.get("code"):
                LOG.warning("OIDC callback rejected: authorization code is missing.")
                raise web.HTTPBadRequest  # noqa: TRY301

            stage = "provider discovery"
            metadata = await _oidc_metadata(oidc.issuer)

            stage = "token exchange and response parsing"
            async with httpx.AsyncClient(follow_redirects=False) as client:
                token_response = await client.post(
                    metadata["token_endpoint"],
                    data={
                        "grant_type": "authorization_code",
                        "code": request.query["code"],
                        "redirect_uri": oidc.redirect_uri,
                        "code_verifier": pending["verifier"],
                    },
                    auth=(oidc.client_id, oidc.client_secret),
                )
                token_response.raise_for_status()
                token = token_response.json()

                stage = "JWKS retrieval and import"
                jwks_response = await client.get(metadata["jwks_uri"])
                jwks_response.raise_for_status()
                jwks = KeySet.import_key_set(jwks_response.json())

            stage = "ID-token processing"
            algorithms = [
                item
                for item in metadata.get("id_token_signing_alg_values_supported", [])
                if item in {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512"}
            ]
            if not algorithms:
                LOG.warning("OIDC callback rejected: provider supports no permitted signing algorithms.")
                raise web.HTTPBadRequest  # noqa: TRY301

            try:
                decoded = jwt.decode(token["id_token"], jwks, algorithms=algorithms)
                claims = decoded.claims
                registry = JWTClaimsRegistry(
                    iss={"value": oidc.issuer, "essential": True},
                    aud={"value": oidc.client_id, "essential": True},
                    exp={"essential": True},
                    iat={"essential": True},
                    nonce={"value": pending["nonce"], "essential": True},
                    sub={"essential": True},
                )
                registry.validate(claims)
            except Exception as exc:
                LOG.warning(
                    "OIDC callback rejected: ID token signature or claims are invalid.",
                    extra={"exception_type": type(exc).__name__},
                )
                raise web.HTTPBadRequest from exc

            audiences = claims.get("aud")
            if ("azp" in claims and claims["azp"] != oidc.client_id) or (
                isinstance(audiences, list) and len(audiences) > 1 and claims.get("azp") != oidc.client_id
            ):
                LOG.warning("OIDC callback rejected: ID token authorized party is invalid.")
                raise web.HTTPBadRequest  # noqa: TRY301

            if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
                LOG.warning("OIDC callback rejected: ID token subject is missing or invalid.")
                raise web.HTTPBadRequest  # noqa: TRY301

            stage = "mapped user lookup"
            user = await auth.find_user(config.external_auth.external_user or "")
            if user is None:
                LOG.warning("OIDC callback rejected: mapped user no longer exists.")
                raise web.HTTPBadRequest  # noqa: TRY301

            stage = "session creation"
            session = await auth.create_session(
                user["id"], request.headers.get("User-Agent"), resolve_client_ip(request, config)
            )

            response = web.HTTPFound(config.base_path or "/")
            response.set_cookie(
                "ytp_session",
                session,
                max_age=config.auth_session_days * 86400,
                httponly=True,
                samesite="Strict",
                secure=oidc.redirect_uri.startswith("https://"),
                path=config.base_path,
            )

        except web.HTTPException:
            response = api_error_response(
                "OIDC authentication failed.", code="OPERATION_FAILED", status=web.HTTPBadRequest.status_code
            )
        except Exception:
            LOG.exception("OIDC callback failed during %s.", stage)
            response = api_error_response(
                "OIDC authentication failed.", code="OPERATION_FAILED", status=web.HTTPBadRequest.status_code
            )

    response.del_cookie("oidc_state", path=config.base_path)
    return response


@route("POST", "api/auth/setup", "auth_setup", public=True, same_origin=True, auth_only=True)
async def auth_setup(request: web.Request, config: Config, auth: AuthService) -> web.Response:
    if config.disable_auth:
        return _disabled()
    if await auth.user_count() > 0:
        return api_error_response(
            "Setup is no longer available.", code="ALREADY_EXISTS", status=web.HTTPConflict.status_code
        )
    payload = await _credentials(request)
    if isinstance(payload, web.Response):
        return payload
    if not auth.attempt_allowed(request.remote):
        return _rate_limited()
    user = await auth.create_user(payload.username, payload.password, require_empty=True)
    if user is None:
        return api_error_response(
            "Setup is no longer available.", code="ALREADY_EXISTS", status=web.HTTPConflict.status_code
        )
    return _session_response(
        request,
        user,
        await auth.create_session(user["id"], request.headers.get("User-Agent"), resolve_client_ip(request, config)),
        web.HTTPCreated.status_code,
    )


@route("POST", "api/auth/login", "auth_login", public=True, same_origin=True, auth_only=True)
async def auth_login(request: web.Request, config: Config, auth: AuthService) -> web.Response:
    if config.disable_auth:
        return _disabled()
    payload = await _credentials(request)
    if isinstance(payload, web.Response):
        return payload
    if not auth.attempt_allowed(request.remote):
        return _rate_limited()
    user = await auth.authenticate_password(payload.username, payload.password)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    auth.clear_attempts(request.remote)
    return _session_response(
        request,
        user,
        await auth.create_session(user["id"], request.headers.get("User-Agent"), resolve_client_ip(request, config)),
    )


@route("POST", "api/auth/logout", "auth_logout", auth_only=True)
async def auth_logout(request: web.Request, config: Config, auth: AuthService) -> web.Response:
    if config.disable_auth:
        return _disabled()
    if token := request.cookies.get("ytp_session"):
        await auth.revoke_session(token)
    response = web.Response(status=web.HTTPNoContent.status_code)
    response.del_cookie("ytp_session", path=config.base_path)
    return response


@route("GET", "api/auth/sessions", "auth_sessions", auth_only=True)
async def auth_sessions(request: web.Request, auth: AuthService) -> web.Response:
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    return web.json_response(data={"items": await auth.sessions(user["id"], request.cookies.get("ytp_session"))})


@route("DELETE", "api/auth/sessions/{session_id}", "auth_session_delete", auth_only=True)
async def auth_session_delete(request: web.Request, auth: AuthService) -> web.Response:
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    try:
        session_id = int(request.match_info["session_id"])
    except ValueError:
        session_id = 0
    current = request.cookies.get("ytp_session")
    current_user = await auth.session_user(current) if current else None
    current_session = (
        current_user is not None
        and current_user["id"] == user["id"]
        and any(item["id"] == session_id and item["current"] for item in await auth.sessions(user["id"], current))
    )
    if not await auth.delete_session(user["id"], session_id):
        return api_error_response("Session not found.", code="NOT_FOUND", status=web.HTTPNotFound.status_code)
    response = web.Response(status=web.HTTPNoContent.status_code)
    if current_session:
        response.del_cookie("ytp_session", path=Config.get_instance().base_path)
    return response


@route("DELETE", "api/auth/sessions", "auth_sessions_delete", auth_only=True, cookie_only=True)
async def auth_sessions_delete(request: web.Request, auth: AuthService) -> web.Response:
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    token = request.cookies["ytp_session"]
    await auth.revoke_other_sessions(user["id"], token)
    return web.Response(status=web.HTTPNoContent.status_code)


@route("POST", "api/auth/ws-ticket", "auth_ws_ticket", auth_only=True)
async def auth_ws_ticket(request: web.Request, auth: AuthService) -> web.Response:
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    response = web.json_response(
        data={"ticket": auth.create_ws_ticket(user), "expires_in": 30}, status=web.HTTPCreated.status_code
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@route("GET", "api/auth/me", "auth_me", auth_only=True)
async def auth_me(request: web.Request) -> web.Response:
    return web.json_response(data={"user": _user(request)})


@route("PATCH", "api/auth/account", "auth_account", auth_only=True)
async def auth_account(request: web.Request, config: Config, auth: AuthService) -> web.Response:
    if config.disable_auth:
        return _disabled()
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    try:
        payload = AccountPatch.model_validate(await request.json())
    except ValidationError as exc:
        return _payload_error(exc)
    except (ValueError, TypeError):
        return api_error_response("Invalid request payload.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)
    if payload.username is None and payload.password is None:
        return api_error_response(
            "Username or password is required.", code="REQUIRED", status=web.HTTPBadRequest.status_code
        )
    current = await auth.authenticate_password(user["username"], payload.current_password)
    if current is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    try:
        updated = await auth.update_user(user["id"], payload.username, payload.password)
    except ValueError as exc:
        return api_error_response(str(exc), code="ALREADY_EXISTS", status=web.HTTPConflict.status_code)
    if payload.password is not None:
        return _session_response(
            request,
            updated,
            await auth.create_session(
                updated["id"], request.headers.get("User-Agent"), resolve_client_ip(request, config)
            ),
        )
    return web.json_response(data={"user": updated})


@route("GET", "api/auth/api-keys", "auth_api_keys", auth_only=True)
async def auth_keys(request: web.Request, auth: AuthService) -> web.Response:
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    return web.json_response(data={"items": await auth.keys(user["id"])})


@route("POST", "api/auth/api-keys", "auth_api_keys_create", auth_only=True)
async def auth_key_create(request: web.Request, auth: AuthService) -> web.Response:
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    try:
        payload = ApiKeyCreate.model_validate(await request.json())
    except ValidationError as exc:
        return _payload_error(exc)
    except (ValueError, TypeError):
        return api_error_response("Invalid request payload.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)
    metadata, key = await auth.create_key(user["id"], payload.name)
    return web.json_response(data={**metadata, "key": key}, status=web.HTTPCreated.status_code)


@route("DELETE", "api/auth/api-keys/{key_id}", "auth_api_keys_delete", auth_only=True)
async def auth_key_delete(request: web.Request, auth: AuthService) -> web.Response:
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    try:
        key_id = int(request.match_info["key_id"])
    except ValueError:
        key_id = 0
    if not await auth.delete_key(user["id"], key_id):
        return api_error_response("API key not found.", code="NOT_FOUND", status=web.HTTPNotFound.status_code)
    return web.Response(status=web.HTTPNoContent.status_code)
