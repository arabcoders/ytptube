from __future__ import annotations

import asyncio
import functools
import logging
import threading
from dataclasses import dataclass
from typing import Any, Literal, cast, overload

import httpx

from .cf_solver_shared import is_cf_challenge, solver

__all__: list[str] = [
    "async_client",
    "build_request_headers",
    "close_shared_clients",
    "get_async_client",
    "get_sync_client",
    "resolve_curl_transport",
    "sync_client",
]

LOG: logging.Logger = logging.getLogger("httpx_cf")


class Globals:
    random_agent: str | None = None

    SHARED_ASYNC_CLIENTS: dict[_AsyncClientKey, httpx.AsyncClient] = {}
    SHARED_SYNC_CLIENTS: dict[_SyncClientKey, httpx.Client] = {}
    SHARED_CLIENT_LOCK = threading.Lock()

    def get_random_agent() -> str:
        if Globals.random_agent:
            return Globals.random_agent

        from yt_dlp.utils.networking import random_user_agent

        Globals.random_agent = random_user_agent()
        return Globals.random_agent


@dataclass(frozen=True)
class _AsyncClientKey:
    enable_cf: bool
    proxy: str | None
    use_curl: bool
    curl_impersonate: str
    curl_default_headers: bool


@dataclass(frozen=True)
class _SyncClientKey:
    enable_cf: bool
    proxy: str | None


def _parse_cookie_header(cookie_header: str | None) -> dict[str, str]:
    cookies: dict[str, str] = {}

    if not cookie_header:
        return cookies

    for item in cookie_header.split(";"):
        item: str = item.strip()
        if "=" in item:
            name, value = item.split("=", 1)
            cookies[name] = value

    return cookies


def _merge_cookies(existing_header: str | None, new_cookies: list[dict[str, str]]) -> dict[str, str]:
    merged: dict[str, str] = _parse_cookie_header(existing_header)

    for cookie in new_cookies:
        if cookie.get("name") and cookie.get("value"):
            merged[cookie["name"]] = cookie["value"]

    return merged


def _normalize_proxy(proxy: str | dict[str, str] | None) -> str | None:
    if proxy is None:
        return None

    if isinstance(proxy, str):
        cleaned: str = proxy.strip()
        return cleaned or None

    if isinstance(proxy, dict):
        return "|".join(f"{key}={value}" for key, value in sorted(proxy.items()))

    return str(proxy)


@functools.lru_cache(maxsize=1)
def _curl_available() -> bool:
    try:
        import httpx_curl_cffi  # noqa: F401

        return True
    except Exception:
        return False


def resolve_curl_transport(use_curl: bool = True) -> bool:
    return use_curl and _curl_available()


def _build_async_curl_transport(
    use_curl: bool,
    curl_impersonate: str,
    curl_default_headers: bool,
) -> httpx.AsyncBaseTransport | None:
    if not resolve_curl_transport(use_curl):
        return None

    from httpx_curl_cffi import AsyncCurlTransport

    return AsyncCurlTransport(
        impersonate=curl_impersonate,
        default_headers=curl_default_headers,
    )


@overload
def _get_transport(
    enable_cf: bool,
    is_async: Literal[True],
    transport: httpx.AsyncBaseTransport | None,
) -> httpx.AsyncBaseTransport: ...


@overload
def _get_transport(
    enable_cf: bool,
    is_async: Literal[False],
    transport: httpx.BaseTransport | None,
) -> httpx.BaseTransport: ...


def _get_transport(
    enable_cf: bool,
    is_async: bool,
    transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None,
) -> httpx.AsyncBaseTransport | httpx.BaseTransport:
    if enable_cf:
        if is_async:
            async_transport = cast("httpx.AsyncBaseTransport | None", transport)
            return CFAsyncTransport(base=async_transport)

        sync_transport = cast("httpx.BaseTransport | None", transport)
        return CFTransport(base=sync_transport)

    return transport or (httpx.AsyncHTTPTransport() if is_async else httpx.HTTPTransport())


def build_request_headers(
    base_headers: dict[str, str] | None = None,
    user_agent: str | None = None,
    use_curl: bool = True,
) -> dict[str, str]:
    headers: dict[str, str] = base_headers.copy() if isinstance(base_headers, dict) else {}

    if user_agent and not use_curl:
        headers.setdefault("User-Agent", user_agent)

    return headers


class CFAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, base: httpx.AsyncBaseTransport | None = None):
        self.base: httpx.AsyncBaseTransport | httpx.AsyncHTTPTransport = base or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response: httpx.Response = await self.base.handle_async_request(request)
        if not is_cf_challenge(response.status_code, dict(response.headers)):
            return response

        url = str(request.url)

        solution: dict[str, Any] | None = solver(url, [], request.headers.get("User-Agent"))
        if not solution:
            return response

        if cookies := solution.get("cookies", []):
            merged_cookies: dict[str, str] = _merge_cookies(request.headers.get("Cookie"), cookies)
            headers: httpx.Headers = request.headers.copy()
            headers.pop("Cookie", None)
            request = httpx.Request(
                method=request.method,
                url=request.url,
                headers=headers,
                content=request.content,
                cookies=merged_cookies,
            )

        if ua := solution.get("userAgent"):
            request.headers["User-Agent"] = ua

        await response.aclose()
        return await self.base.handle_async_request(request)

    def close(self) -> None:
        close_fn = getattr(self.base, "close", None)
        if callable(close_fn):
            close_fn()


class CFTransport(httpx.BaseTransport):
    def __init__(self, base: httpx.BaseTransport | None = None):
        self.base: httpx.BaseTransport | httpx.HTTPTransport = base or httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response: httpx.Response = self.base.handle_request(request)
        if not is_cf_challenge(response.status_code, dict(response.headers)):
            return response

        url = str(request.url)

        solution: dict[str, Any] | None = solver(url, [], request.headers.get("User-Agent"))
        if not solution:
            return response

        if cookies := solution.get("cookies", []):
            merged_cookies: dict[str, str] = _merge_cookies(request.headers.get("Cookie"), cookies)
            headers: httpx.Headers = request.headers.copy()
            headers.pop("Cookie", None)
            request = httpx.Request(
                method=request.method,
                url=request.url,
                headers=headers,
                content=request.content,
                cookies=merged_cookies,
            )

        if ua := solution.get("userAgent"):
            request.headers["User-Agent"] = ua

        response.close()
        return self.base.handle_request(request)

    def close(self) -> None:
        self.base.close()


def async_client(enable_cf: bool = True, **kwargs: Any) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient with optional Cloudflare challenge solving.

    Args:
        enable_cf (bool): Whether to enable Cloudflare challenge solving.
        **kwargs: Additional keyword arguments to pass to httpx.AsyncClient.

    Returns:
        httpx.AsyncClient: The configured httpx.AsyncClient instance.

    """
    transport = cast("httpx.AsyncBaseTransport | None", kwargs.pop("transport", None))
    async_transport = _get_transport(enable_cf, is_async=True, transport=transport)
    return httpx.AsyncClient(transport=async_transport, **kwargs)


def sync_client(enable_cf: bool = True, **kwargs: Any) -> httpx.Client:
    """
    Create an httpx.Client with optional Cloudflare challenge solving.

    Args:
        enable_cf (bool): Whether to enable Cloudflare challenge solving.
        **kwargs: Additional keyword arguments to pass to httpx.Client.

    Returns:
        httpx.Client: The configured httpx.Client instance.

    """
    transport = cast("httpx.BaseTransport | None", kwargs.pop("transport", None))
    sync_transport = _get_transport(enable_cf, is_async=False, transport=transport)
    return httpx.Client(transport=sync_transport, **kwargs)


def get_async_client(
    enable_cf: bool = True,
    proxy: str | dict[str, str] | None = None,
    use_curl: bool = True,
    curl_impersonate: str = "chrome",
    curl_default_headers: bool = True,
) -> httpx.AsyncClient:
    proxy_key = _normalize_proxy(proxy)
    use_curl = resolve_curl_transport(use_curl)
    key = _AsyncClientKey(
        enable_cf=enable_cf,
        proxy=proxy_key,
        use_curl=use_curl,
        curl_impersonate=curl_impersonate,
        curl_default_headers=curl_default_headers,
    )

    with Globals.SHARED_CLIENT_LOCK:
        if key in Globals.SHARED_ASYNC_CLIENTS:
            return Globals.SHARED_ASYNC_CLIENTS[key]

        transport = _build_async_curl_transport(
            use_curl=use_curl,
            curl_impersonate=curl_impersonate,
            curl_default_headers=curl_default_headers,
        )
        client = httpx.AsyncClient(
            transport=cast(
                "httpx.AsyncBaseTransport",
                _get_transport(enable_cf, is_async=True, transport=transport),
            ),
            proxy=cast("Any", proxy),
        )
        Globals.SHARED_ASYNC_CLIENTS[key] = client
        return client


def get_sync_client(
    enable_cf: bool = True,
    proxy: str | dict[str, str] | None = None,
) -> httpx.Client:
    proxy_key = _normalize_proxy(proxy)
    key = _SyncClientKey(enable_cf=enable_cf, proxy=proxy_key)

    with Globals.SHARED_CLIENT_LOCK:
        if key in Globals.SHARED_SYNC_CLIENTS:
            return Globals.SHARED_SYNC_CLIENTS[key]

        client = httpx.Client(
            transport=cast(
                "httpx.BaseTransport",
                _get_transport(enable_cf, is_async=False, transport=None),
            ),
            proxy=cast("Any", proxy),
        )
        Globals.SHARED_SYNC_CLIENTS[key] = client
        return client


async def close_shared_clients(_: Any | None = None) -> None:
    async_clients = list(Globals.SHARED_ASYNC_CLIENTS.values())
    sync_clients = list(Globals.SHARED_SYNC_CLIENTS.values())
    Globals.SHARED_ASYNC_CLIENTS.clear()
    Globals.SHARED_SYNC_CLIENTS.clear()

    for client in sync_clients:
        try:
            client.close()
        except Exception:
            pass

    if async_clients:
        await asyncio.gather(*(client.aclose() for client in async_clients), return_exceptions=True)
