from __future__ import annotations

import http.cookiejar
import logging
from abc import ABC
from collections.abc import Callable
from typing import Any, ClassVar

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

from app.library.cf_solver_shared import CACHE, is_cf_challenge, solver

LOG: logging.Logger = logging.getLogger(__name__)

SolverFn = Callable[[Request, Response, RequestHandler], Request | None]


def cf_solver(request: Request, _response: Response, handler: RequestHandler) -> Request | None:
    """
    A Cloudflare solver that uses FlareSolverr to solve challenges.

    Args:
        request (Request): The original request that triggered the challenge.
        _response (Response): The response that contained the challenge.
        handler (RequestHandler): The request handler invoking the solver.

    Returns:
        Request | None: The modified request with solved credentials, or None if solving failed.

    """
    if not isinstance(handler, CFSolverRH):
        return None

    cookiejar = handler._get_cookiejar(request)
    host: str = handler._get_host(request.url)
    cookies = [
        {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain or host,
            "path": cookie.path or "/",
        }
        for cookie in cookiejar
    ]

    solution: dict[str, Any] | None = solver(request.url, cookies, request.headers.get("User-Agent"))
    if not handler._apply_solution(solution, request.url, request.headers, cookiejar):
        return None

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


@register_rh
class CFSolverRH(RequestHandler, ABC):
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

    @staticmethod
    def _get_host(url: str) -> str:
        """Extract hostname from URL."""
        from urllib.parse import urlparse

        return urlparse(url).hostname or ""

    def _apply_solution(
        self,
        solution: dict[str, Any] | None,
        url: str,
        headers: dict[str, Any],
        cookiejar: http.cookiejar.CookieJar,
    ) -> bool:
        """Apply Cloudflare solution (cookies and User-Agent) to request."""
        if not solution:
            return False

        host = self._get_host(url)

        for cookie in solution.get("cookies", []):
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

        if ua := solution.get("userAgent"):
            headers["User-Agent"] = ua

        return True

    def _check_extensions(self, extensions) -> None:
        super()._check_extensions(extensions)
        for key in ("cookiejar", "timeout", "legacy_ssl", "keep_header_casing", "cf_retry"):
            extensions.pop(key, None)

    def _validate(self, request: Request):
        self._check_url_scheme(request)
        self._check_proxies(request.proxies or self.proxies)
        extensions = request.extensions.copy()
        self._check_extensions(extensions)

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
        host: str = self._get_host(request.url)
        if host and (cached := CACHE.get(host)):
            LOG.info(f"Injecting cached Cloudflare cookies for '{host}'.")
            self._apply_solution(cached, request.url, request.headers, self._get_cookiejar(request))

        director: RequestDirector = self._build_fallback()

        try:
            response: Response = director.send(request)
        except HTTPError as error:
            if error.response and is_cf_challenge(getattr(error.response, "status", None), error.response.headers):
                return self._retry_with_clearance(request, error.response, director)
            raise

        if is_cf_challenge(getattr(response, "status", None), response.headers):
            return self._retry_with_clearance(request, response, director)

        return response


@register_preference(CFSolverRH)
def cf_solver_preference(_handler, _request) -> int:
    from app.library.config import Config

    if not Config.get_instance().flaresolverr_url:
        return 0

    return 500
