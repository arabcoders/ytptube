from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from app.library.logging import get_logger

from .cache import Cache

if TYPE_CHECKING:
    from collections.abc import Mapping

CACHE: Cache = Cache()
LOG = get_logger()

_solve_locks: dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()


def _get_solve_lock(host: str) -> threading.Lock:
    with _locks_mutex:
        if host not in _solve_locks:
            _solve_locks[host] = threading.Lock()
        return _solve_locks[host]


def _host_matches_cookie_domain(host: str, cookie_domain: str | None) -> bool:
    """
    Determine whether a cookie belongs to the given request host.

    FlareSolverr hands every cookie we send to a real Chrome instance navigating to the target
    URL. Chrome rejects cookies whose domain does not match the page being loaded with an
    ``invalid cookie domain`` error, which aborts the whole solve with an HTTP 500. So we only
    forward cookies whose domain matches the target host.

    Args:
        host (str): The hostname of the target URL.
        cookie_domain (str | None): The cookie's domain attribute.

    Returns:
        bool: True if the cookie applies to the host, False otherwise.

    """
    host = (host or "").lower().strip(".")
    domain = (cookie_domain or "").lower().strip(".")
    if not host:
        return False

    # Host-only cookie (no domain) applies to the target by default.
    if not domain:
        return True

    return host == domain or host.endswith(f".{domain}")


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

    lock = _get_solve_lock(host)
    try:
        with lock:
            if cached := CACHE.get(host):
                return cached

            payload: dict[str, Any] = {
                "cmd": "request.get",
                "url": url,
                "maxTimeout": int(config.flaresolverr_max_timeout * 1000),
            }

        if cookies:
            # Only forward cookies that belong to the target host. Sending a cookie for an unrelated
            # domain makes FlareSolverr's Chrome reject it and fail the whole solve with an HTTP 500.
            scoped_cookies = [c for c in cookies if _host_matches_cookie_domain(host, c.get("domain"))]
            dropped: int = len(cookies) - len(scoped_cookies)
            if dropped:
                LOG.debug(
                    "Dropped %d cookie(s) not matching host '%s' before calling FlareSolverr.",
                    dropped,
                    host,
                    extra={"host": host, "dropped": dropped},
                )
            if scoped_cookies:
                payload["cookies"] = scoped_cookies

        if user_agent:
            payload.setdefault("headers", {})["User-Agent"] = user_agent

        req = urllib.request.Request(  # noqa: S310
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        LOG.info(
            "Solving Cloudflare challenge for '%s' via FlareSolverr.", host, extra={"host": host, "endpoint": endpoint}
        )
        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=float(config.flaresolverr_client_timeout)) as resp:  # noqa: S310
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # FlareSolverr signals solve failures with an HTTP 500 and a JSON body describing why.
            # urlopen raises before we can read that body, so pull the message out of the error here
            # and degrade gracefully instead of letting the exception abort the whole extraction.
            message: str | None = None
            try:
                message = json.loads(e.read().decode("utf-8")).get("message")
            except Exception:
                message = None

            LOG.error(
                "FlareSolverr returned HTTP %s while solving challenge for '%s': %s",
                e.code,
                host,
                message or e.reason,
                extra={"host": host, "endpoint": endpoint, "status_code": e.code, "solver_message": message},
            )
            return None
        except (urllib.error.URLError, OSError) as e:
            LOG.error(
                "Failed to reach FlareSolverr for '%s': %s",
                host,
                e,
                extra={"host": host, "endpoint": endpoint, "error": str(e)},
            )
            return None

        if "ok" != result.get("status"):
            LOG.error(
                "FlareSolverr failed to solve challenge for '%s': %s",
                host,
                result.get("message"),
                extra={"host": host, "endpoint": endpoint, "solver_message": result.get("message")},
            )
            return None

        elapsed_s: float = time.time() - start_time
        LOG.info(
            "FlareSolverr solved challenge for '%s' in %.2f seconds.",
            host,
            elapsed_s,
            extra={"host": host, "endpoint": endpoint, "elapsed_s": round(elapsed_s, 2)},
        )

        solution = result.get("solution") or {}
        CACHE.set(
            host,
            {"cookies": solution.get("cookies") or [], "userAgent": solution.get("userAgent")},
            ttl=config.flaresolverr_cache_ttl,
        )

        return CACHE.get(host)
    finally:
        with _locks_mutex:
            _solve_locks.pop(host, None)


def is_cf_challenge(status: int | None, headers: Mapping[str, Any] | None) -> bool:
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
