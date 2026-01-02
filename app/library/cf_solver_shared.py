# flake8: noqa: S310
from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import Any
from urllib.parse import urlparse

from .cache import Cache

CACHE: Cache = Cache()
LOG: logging.Logger = logging.getLogger("cf_solver")


def solver(url: str, cookies: list[dict[str, Any]], user_agent: str | None) -> dict[str, Any] | None:
    """
    Run FlareSolverr solve. Returns solution dict or None.

    Args:
        url (str): The URL to solve the challenge for.
        cookies (list[dict]): List of existing cookies to send to FlareSolverr.
        user_agent (str | None): The User-Agent string to send to FlareSolverr.

    Returns:
        dict[str, Any] | None: The solution dict from FlareSolverr, or None if solving fails.

    """
    from app.library.config import Config

    config = Config.get_instance()
    if not (endpoint := config.flaresolverr_url):
        return None

    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https"):
        return None

    host = urlparse(url).hostname or ""
    if not host:
        return None

    if cached := CACHE.get(host):
        return cached

    payload: dict[str, Any] = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": int(config.flaresolverr_max_timeout * 1000),
    }

    if cookies:
        payload["cookies"] = cookies

    if user_agent:
        payload.setdefault("headers", {})["User-Agent"] = user_agent

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    LOG.info(f"Solving Cloudflare challenge for '{host}' via FlareSolverr.")
    start_time = time.time()
    with urllib.request.urlopen(req, timeout=float(config.flaresolverr_client_timeout)) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    if "ok" != result.get("status"):
        LOG.error(f"FlareSolverr failed to solve challenge for '{host}': {result.get('message')}")
        return None

    LOG.info(f"FlareSolverr successfully solved challenge for '{host}'. (Took {time.time() - start_time:.2f} seconds)")

    solution = result.get("solution") or {}
    CACHE.set(
        host,
        {"cookies": solution.get("cookies") or [], "userAgent": solution.get("userAgent")},
        ttl=config.flaresolverr_cache_ttl,
    )

    return CACHE.get(host)


def is_cf_challenge(status: int | None, headers: dict[str, Any] | None) -> bool:
    """
    Determine whether a response indicates a Cloudflare challenge.
    """
    if status not in (403, 429, 503):
        return False

    headers = headers or {}
    server_header: str = str(headers.get("Server", "")).lower()
    if "cloudflare" in server_header:
        return True

    cf_header_keys: tuple[str, ...] = ("cf-ray", "cf-chl-bypass", "cf-cache-status", "cf-visitor")
    return any(key in headers for key in cf_header_keys)
