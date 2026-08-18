from __future__ import annotations

from aiohttp import web
from pydantic import ValidationError

from app.features.auth.middleware import AUTH_USER_KEY
from app.features.auth.schemas import AccountPatch, ApiKeyCreate, Credentials
from app.features.auth.service import AuthService
from app.features.core.utils import api_error_response, format_validation_errors
from app.library.config import Config
from app.library.router import route


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
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        samesite="Strict",
        secure=request.secure,
        path=Config.get_instance().base_path,
    )
    return response


@route("GET", "api/auth/status", "auth_status")
async def auth_status(request: web.Request, config: Config, auth: AuthService) -> web.Response:
    user = _user(request)
    return web.json_response(
        data={
            "disabled": config.disable_auth,
            "setup_required": False if config.disable_auth else await auth.user_count() == 0,
            "authenticated": user is not None,
            "user": user,
        }
    )


@route("POST", "api/auth/setup", "auth_setup")
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
    return _session_response(request, user, await auth.create_session(user["id"]), web.HTTPCreated.status_code)


@route("POST", "api/auth/login", "auth_login")
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
    return _session_response(request, user, await auth.create_session(user["id"]))


@route("POST", "api/auth/logout", "auth_logout")
async def auth_logout(request: web.Request, config: Config, auth: AuthService) -> web.Response:
    if config.disable_auth:
        return _disabled()
    if token := request.cookies.get("ytp_session"):
        await auth.revoke_session(token)
    response = web.Response(status=web.HTTPNoContent.status_code)
    response.del_cookie("ytp_session", path=config.base_path)
    return response


@route("POST", "api/auth/ws-ticket", "auth_ws_ticket")
async def auth_ws_ticket(request: web.Request, auth: AuthService) -> web.Response:
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    response = web.json_response(
        data={"ticket": auth.create_ws_ticket(user), "expires_in": 30}, status=web.HTTPCreated.status_code
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@route("GET", "api/auth/me", "auth_me")
async def auth_me(request: web.Request) -> web.Response:
    return web.json_response(data={"user": _user(request)})


@route("PATCH", "api/auth/account", "auth_account")
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
        return _session_response(request, updated, await auth.create_session(updated["id"]))
    return web.json_response(data={"user": updated})


@route("GET", "api/auth/api-keys", "auth_api_keys")
async def auth_keys(request: web.Request, auth: AuthService) -> web.Response:
    user = _user(request)
    if user is None:
        return api_error_response("Unauthorized.", code="UNAUTHORIZED", status=web.HTTPUnauthorized.status_code)
    return web.json_response(data={"items": await auth.keys(user["id"])})


@route("POST", "api/auth/api-keys", "auth_api_keys_create")
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


@route("DELETE", "api/auth/api-keys/{key_id}", "auth_api_keys_delete")
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
