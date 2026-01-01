# flake8: noqa: S310
from __future__ import annotations

import http.cookiejar
import json
import logging
import urllib.request
from collections.abc import Callable
from typing import Any, ClassVar
from urllib.parse import urlparse

from yt_dlp.networking.common import (
    _REQUEST_HANDLERS,
    _RH_PREFERENCES,
    Request,
    RequestDirector,
    RequestHandler,
    Response,
    register_preference,
    register_rh,
)
from yt_dlp.networking.exceptions import HTTPError
from yt_dlp.utils.networking import clean_headers

LOG: logging.Logger = logging.getLogger(__name__)

SolverFn = Callable[[Request, Response, RequestHandler], Request | None]


def cf_solver(request: Request, _response: Response, handler: RequestHandler) -> Request | None:
    """
    A Cloudflare solver that uses FlareSolverr/FlareSolverr to solve challenges.

    Args:
        request (Request): The original request that triggered the challenge.
        _response (Response): The response that contained the challenge.
        handler (RequestHandler): The request handler invoking the solver.

    Returns:
        Request | None: The modified request with solved credentials, or None if solving failed.

    """
    from app.library.config import Config

    config = Config.get_instance()

    if not config.flaresolverr_url:
        return None

    parsed_endpoint = urlparse(config.flaresolverr_url)
    if parsed_endpoint.scheme not in ("http", "https"):
        return None

    if request.data is not None and request.method not in ("GET", None):
        return None

    method: str = request.method.lower() if isinstance(request.method, str) else "get"
    if method not in ("get", "head"):
        method = "get"

    payload: dict[str, Any] = {
        "cmd": f"request.{method}",
        "url": request.url,
        "maxTimeout": int(getattr(config, "flaresolverr_max_timeout", 60) * 1000),
    }

    cookiejar = handler._get_cookiejar(request)
    cookies = (
        [
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain or urlparse(request.url).hostname or "",
                "path": cookie.path or "/",
            }
            for cookie in cookiejar
        ]
        if cookiejar
        else []
    )

    if cookies:
        payload["cookies"] = cookies

    req = urllib.request.Request(
        config.flaresolverr_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        LOG.info(f"Trying to solve Cloudflare challenge for '{request.url}' this may take a while...")
        with urllib.request.urlopen(req, timeout=float(config.flaresolverr_client_timeout)) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        LOG.error(f"FlareSolverr failed to solve challenge for '{request.url}': {e!s}")
        return None

    if "ok" != result.get("status"):
        LOG.error(f"FlareSolverr failed to solve challenge for '{request.url}': {result}")
        return None

    LOG.info(f"Successfully solved Cloudflare challenge for '{request.url}'.")

    solution = result.get("solution") or {}
    _cookiejar_from_solution(solution.get("cookies"), request, handler)

    ua = solution.get("userAgent")
    if ua:
        request.headers["User-Agent"] = ua

    return request


def set_cf_handler(solver: SolverFn | None = None) -> type[CFSolverRH]:
    """
    Set the Cloudflare handler.

    Args:
        solver (SolverFn | None): The solver function to use for Cloudflare challenges.
            If None, the existing solver will be used.

    Returns:
        type[CloudflareRH]: The Cloudflare request handler class.

    """
    CFSolverRH.solver = solver or CFSolverRH.solver

    return CFSolverRH


def _cookiejar_from_solution(cookies, request: Request, handler: RequestHandler) -> None:
    cookiejar = handler._get_cookiejar(request)
    host = urlparse(request.url).hostname or ""
    for cookie in cookies or []:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        domain = cookie.get("domain") or host
        path = cookie.get("path") or "/"
        cookiejar.set_cookie(
            http.cookiejar.Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=domain,
                domain_specified=True,
                domain_initial_dot=domain.startswith("."),
                path=path,
                path_specified=True,
                secure=bool(cookie.get("secure")),
                expires=cookie.get("expires"),
                discard=False,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
        )


@register_preference()
def _prefer_cf_handler(handler: RequestHandler, _request: Request) -> int:
    """Prefer Cloudflare handler when configured with endpoint."""
    from app.library.config import Config

    if not Config.get_instance().flaresolverr_url:
        return 0

    hand = getattr(handler, "RH_KEY", "")
    return 1000 if hand == "CFSolver" else 0


@register_rh
class CFSolverRH(RequestHandler):
    """Request handler that intercepts Cloudflare challenges"""

    _SUPPORTED_URL_SCHEMES = ("http", "https")
    _SUPPORTED_PROXY_SCHEMES = ("http", "https", "socks4", "socks4a", "socks5", "socks5h")
    solver: ClassVar[SolverFn | None] = None

    def __init__(self, *, solver: SolverFn | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._solver: SolverFn | None = solver or cf_solver
        self._fallback_director: RequestDirector | None = None

    def close(self) -> None:
        if self._fallback_director:
            self._fallback_director.close()
            self._fallback_director = None

    def _check_extensions(self, extensions) -> None:
        super()._check_extensions(extensions)
        for key in ("cookiejar", "timeout", "legacy_ssl", "keep_header_casing", "impersonate", "cf_retry"):
            extensions.pop(key, None)

    def _build_fallback(self) -> RequestDirector:
        if self._fallback_director:
            return self._fallback_director

        director = RequestDirector(logger=self._logger, verbose=self.verbose)
        for handler_cls in _REQUEST_HANDLERS.values():
            if handler_cls.RH_KEY == self.RH_KEY:
                continue
            director.add_handler(
                handler_cls(
                    logger=self._logger,
                    headers=self.headers,
                    cookiejar=self.cookiejar,
                    proxies=self.proxies,
                    timeout=self.timeout,
                    source_address=self.source_address,
                    verbose=self.verbose,
                    prefer_system_certs=self.prefer_system_certs,
                    client_cert=self._client_cert,
                    verify=self.verify,
                    legacy_ssl_support=self.legacy_ssl_support,
                )
            )
        director.preferences.update(_RH_PREFERENCES)
        self._fallback_director = director
        return director

    @staticmethod
    def _is_cf_response(response: Response) -> bool:
        """
        Check if the response is a Cloudflare challenge response.

        Args:
            response (Response): The HTTP response to check.

        Returns:
            bool: True if the response is a Cloudflare challenge, False otherwise.

        """
        status: int | None = getattr(response, "status", None)
        if status not in (403, 429, 503):
            return False

        headers = response.headers or {}
        server_header: str = (headers.get("Server") or "").lower()
        if "cloudflare" in server_header:
            return True

        cf_header_keys: tuple[str, ...] = ("cf-ray", "cf-chl-bypass", "cf-cache-status", "cf-visitor")
        return any(key in headers for key in cf_header_keys)

    def _solve(self, request: Request, response: Response) -> Request | None:
        return self._solver(request, response, self) if self._solver else None

    @staticmethod
    def _mark_retry(request: Request) -> Request:
        new_request: Request = request.copy()
        new_request.extensions["cf_retry"] = True
        return new_request

    def _retry_with_clearance(self, request: Request, response: Response, director: RequestDirector) -> Response:
        if request.extensions.get("cf_retry"):
            return response

        solved_request: Request | None = self._solve(self._mark_retry(request), response)
        if solved_request is None:
            return response

        solved_request.extensions.pop("cf_retry", None)
        clean_headers(solved_request.headers)
        response.close()
        return director.send(solved_request)

    def _send(self, request: Request) -> Response:
        director: RequestDirector = self._build_fallback()

        try:
            response: Response = director.send(request)
        except HTTPError as error:
            if error.response and self._is_cf_response(error.response):
                return self._retry_with_clearance(request, error.response, director)
            raise

        if self._is_cf_response(response):
            return self._retry_with_clearance(request, response, director)

        return response
