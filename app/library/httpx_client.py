from __future__ import annotations

import logging
from typing import Any

import httpx

from .cf_solver_shared import is_cf_challenge, solver

__all__: list[str] = ["async_client", "sync_client"]

LOG: logging.Logger = logging.getLogger("httpx_cf")


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


def _get_transport(
    enable_cf: bool,
    is_async: bool,
    transport: httpx.AsyncBaseTransport | None,
) -> httpx.AsyncBaseTransport:
    if enable_cf:
        return CFAsyncTransport(base=transport) if is_async else CFTransport(base=transport)

    return transport or (httpx.AsyncHTTPTransport() if is_async else httpx.HTTPTransport())


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
        self.base.close()


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
    transport = kwargs.pop("transport", None)
    return httpx.AsyncClient(transport=_get_transport(enable_cf, is_async=True, transport=transport), **kwargs)


def sync_client(enable_cf: bool = True, **kwargs: Any) -> httpx.Client:
    """
    Create an httpx.Client with optional Cloudflare challenge solving.

    Args:
        enable_cf (bool): Whether to enable Cloudflare challenge solving.
        **kwargs: Additional keyword arguments to pass to httpx.Client.

    Returns:
        httpx.Client: The configured httpx.Client instance.

    """
    transport = kwargs.pop("transport", None)
    return httpx.Client(transport=_get_transport(enable_cf, is_async=False, transport=transport), **kwargs)
