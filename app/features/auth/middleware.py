from __future__ import annotations

import base64
import ipaddress
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from aiohttp import web

from app.features.auth.service import AuthService
from app.features.core.utils import api_error_response
from app.library.config import Config
from app.library.router import RouteType, get_route

if TYPE_CHECKING:
    from aiohttp.typedefs import Handler, Middleware
    from aiohttp.web import Request
    from aiohttp.web_response import StreamResponse

AUTH_USER_KEY: web.RequestKey[dict] = web.RequestKey("auth_user", dict)


def decode_basic_credentials(value: str) -> tuple[str, str] | None:
    try:
        value = value.replace("-", "+").replace("_", "/")
        value += "=" * (-len(value) % 4)
        decoded: str = base64.b64decode(value, validate=True).decode("utf-8")
        username, separator, password = decoded.partition(":")
        return (username, password) if separator else None
    except (ValueError, UnicodeError):
        return None


def cors_headers(request: Request, config: Config) -> dict[str, str]:
    origin: str | None = request.headers.get("Origin")
    if not origin or is_cross_origin(request) is False:
        return {}
    allowed: set[str] = {item.strip() for item in config.cors_origins.split(",") if item.strip()}
    headers: dict[str, str] = {}
    if origin and config.cors_origins.strip() == "*":
        headers["Access-Control-Allow-Origin"] = "*"
    elif origin and origin in allowed:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
    if request.method == "OPTIONS" and origin:
        headers.update(
            {
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Allow-Methods": "GET, HEAD, PATCH, PUT, POST, DELETE, OPTIONS",
                "Access-Control-Max-Age": "900",
            }
        )
    return headers


def is_cross_origin(request: Request) -> bool:
    fetch_site: str | None = request.headers.get("Sec-Fetch-Site")
    if fetch_site:
        return fetch_site.lower() not in {"none", "same-origin"}

    origin: str | None = request.headers.get("Origin")
    if not origin or origin == "null":
        return bool(origin)
    try:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            return True
        if parsed.username or parsed.password:
            return True
        return parsed.netloc.lower() != request.host.lower()
    except ValueError:
        return True


def resolve_client_ip(request: Request, config: Config) -> str | None:
    remote = request.remote
    if not remote:
        return remote
    try:
        remote_ip = ipaddress.ip_address(remote)
    except ValueError:
        return remote
    trusted = []
    for value in config.trusted_proxies.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            trusted.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue

    def is_trusted(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return any(address in network for network in trusted)

    if not is_trusted(remote_ip):
        return remote
    forwarded = [value.strip() for value in request.headers.get("X-Forwarded-For", "").split(",") if value.strip()]
    try:
        forwarded_ips = [ipaddress.ip_address(value) for value in forwarded]
    except ValueError:
        return remote
    if not forwarded_ips:
        return remote
    for address in reversed([*forwarded_ips, remote_ip]):
        if not is_trusted(address):
            return str(address)
    return str(forwarded_ips[0])


def auth_middleware(auth: AuthService, config: Config) -> Middleware:
    @web.middleware
    async def auth_handler(request: Request, handler: Handler) -> StreamResponse:
        origin: str | None = request.headers.get("Origin")
        cross_origin: bool = is_cross_origin(request)
        route_name = getattr(request.match_info.route, "name", "")
        registered_route = get_route(RouteType.HTTP, route_name) if isinstance(route_name, str) else None
        same_origin = registered_route.same_origin if registered_route is not None else False
        cookie_only = registered_route.cookie_only if registered_route is not None else False
        optional_auth = registered_route.optional_auth if registered_route is not None else False
        auth_only = registered_route.auth_only if registered_route is not None else False
        public = registered_route.public if registered_route is not None else False
        allowed_origins: set[str] = {item.strip() for item in config.cors_origins.split(",") if item.strip()}
        if cross_origin and origin not in allowed_origins and config.cors_origins.strip() != "*":
            return api_error_response("Origin is not allowed.", code="FORBIDDEN", status=web.HTTPForbidden.status_code)

        if request.method == "OPTIONS":
            return await handler(request)

        async def explicit_user() -> dict | None:
            credentials: str | None = request.headers.get("Authorization")
            query_key: str | None = request.query.get("apikey")
            if credentials:
                parts: list[str] = credentials.split(" ", 1)
                if len(parts) != 2:
                    return None
                if parts[0].lower() == "bearer":
                    return await auth.user_from_key(parts[1])
                if parts[0].lower() != "basic":
                    return None
                value: str = parts[1]
            elif query_key:
                if query_key.startswith("ytp_"):
                    return await auth.user_from_key(query_key)
                value = query_key
            else:
                return None
            decoded = decode_basic_credentials(value)
            if decoded is None:
                return None
            username, secret = decoded
            if secret.startswith("ytp_"):
                user = await auth.user_from_key(secret)
                if user is not None and user["username"] == username:
                    return user
            if not auth.attempt_allowed(request.remote):
                return None
            user = await auth.authenticate_password(username, secret)
            if user is not None:
                auth.clear_attempts(request.remote)
            return user

        ticket: str | None = request.query.get("ticket") if route_name == "ws" else None

        if config.disable_auth:
            if auth_only:
                return api_error_response(
                    "Authentication is disabled.", code="FEATURE_DISABLED", status=web.HTTPForbidden.status_code
                )
            return await handler(request)

        if same_origin and cross_origin:
            return api_error_response("Origin is not allowed.", code="FORBIDDEN", status=web.HTTPForbidden.status_code)

        if public and not cookie_only:
            if optional_auth:
                user = await explicit_user()
                if user is None and not cross_origin and request.cookies.get("ytp_session"):
                    user = await auth.session_user(request.cookies["ytp_session"])
                if user is not None:
                    request[AUTH_USER_KEY] = user
            return await handler(request)

        user = (
            None if cookie_only else (auth.consume_ws_ticket(ticket) if ticket is not None else await explicit_user())
        )
        cookie = request.cookies.get("ytp_session")
        if user is None and ticket is None and not cross_origin and cookie:
            user = await auth.session_user(cookie)

        if user is None:
            if cookie_only:
                return api_error_response(
                    "A valid session cookie is required.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code
                )
            return api_error_response(
                "Unauthorized.",
                code="UNAUTHORIZED",
                status=web.HTTPUnauthorized.status_code,
            )
        request[AUTH_USER_KEY] = user
        return await handler(request)

    return auth_handler
