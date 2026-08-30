from __future__ import annotations

import http.cookiejar
from typing import Any
from unittest.mock import Mock, patch

import pytest

try:
    from yt_dlp.networking.common import Request, RequestDirector, Response
    from yt_dlp.networking.exceptions import HTTPError

    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    Request: Any = Mock
    Response: Any = Mock
    RequestDirector: Any = Mock
    HTTPError: Any = Exception

pytestmark = pytest.mark.skipif(not YTDLP_AVAILABLE, reason="yt-dlp not available")


@pytest.fixture(scope="module")
def cf_handler_module():
    """Lazily import cf_solver_handler module to avoid circular imports."""
    from app.library import cf_solver_handler

    return cf_solver_handler


class TestCfSolverFunction:
    @patch("app.library.cf_solver_handler.solver")
    def test_cf_solver_success(self, mock_solver, cf_handler_module):
        mock_solver.return_value = {"cookies": [], "userAgent": "Mozilla/5.0"}

        handler = cf_handler_module.CFSolverRH(logger=Mock())
        cookiejar = http.cookiejar.CookieJar()
        handler._get_cookiejar = Mock(return_value=cookiejar)

        request = Mock()
        request.url = "https://example.com/path"
        request.headers = {"User-Agent": "test"}

        response = Mock()

        result = cf_handler_module.cf_solver(request, response, handler)

        assert result is request
        mock_solver.assert_called_once()
        assert request.headers["User-Agent"] == "Mozilla/5.0"

    @patch("app.library.cf_solver_handler.solver")
    def test_cf_solver_no_solution(self, mock_solver, cf_handler_module):
        mock_solver.return_value = None

        handler = cf_handler_module.CFSolverRH(logger=Mock())
        cookiejar = http.cookiejar.CookieJar()
        handler._get_cookiejar = Mock(return_value=cookiejar)

        request = Mock()
        request.url = "https://example.com/path"
        request.headers = {"User-Agent": "test"}

        response = Mock()

        result = cf_handler_module.cf_solver(request, response, handler)

        assert result is None
        mock_solver.assert_called_once()

    @patch("app.library.cf_solver_handler.solver")
    def test_cf_solver_existing_cookies(self, mock_solver, cf_handler_module):
        mock_solver.return_value = {"cookies": [], "userAgent": "Mozilla/5.0"}

        handler = cf_handler_module.CFSolverRH(logger=Mock())
        cookiejar = http.cookiejar.CookieJar()

        cookie = http.cookiejar.Cookie(
            version=0,
            name="existing",
            value="value",
            port=None,
            port_specified=False,
            domain="example.com",
            domain_specified=True,
            domain_initial_dot=False,
            path="/",
            path_specified=True,
            secure=False,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False,
        )
        cookiejar.set_cookie(cookie)
        handler._get_cookiejar = Mock(return_value=cookiejar)

        request = Mock()
        request.url = "https://example.com/path"
        request.headers = {"User-Agent": "test"}

        response = Mock()

        result = cf_handler_module.cf_solver(request, response, handler)

        assert result is request
        call_args = mock_solver.call_args
        assert call_args is not None
        cookies_arg = call_args[0][1]
        assert len(cookies_arg) > 0
        assert "existing" == cookies_arg[0]["name"]

    @patch("app.library.cf_solver_handler.solver")
    def test_solver_passes_cookies_jar(self, mock_solver, cf_handler_module):
        mock_solver.return_value = {"cookies": [], "userAgent": "Mozilla/5.0"}

        handler = cf_handler_module.CFSolverRH(logger=Mock())
        cookiejar = http.cookiejar.CookieJar()
        for name, domain in (("a", "example.com"), ("b", "other.com"), ("c", ".example.com")):
            cookiejar.set_cookie(
                http.cookiejar.Cookie(
                    version=0,
                    name=name,
                    value="v",
                    port=None,
                    port_specified=False,
                    domain=domain,
                    domain_specified=True,
                    domain_initial_dot=domain.startswith("."),
                    path="/",
                    path_specified=True,
                    secure=False,
                    expires=None,
                    discard=True,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False,
                )
            )
        handler._get_cookiejar = Mock(return_value=cookiejar)

        request = Mock()
        request.url = "https://example.com/path"
        request.headers = {"User-Agent": "test"}
        response = Mock()

        cf_handler_module.cf_solver(request, response, handler)

        cookies_arg = mock_solver.call_args[0][1]
        cookie_names = {c["name"] for c in cookies_arg}
        assert {"a", "b", "c"} == cookie_names


class TestSetCfHandler:
    def test_set_cf_handler_default(self, cf_handler_module):
        result = cf_handler_module.set_cf_handler()
        assert result is cf_handler_module.CFSolverRH
        assert cf_handler_module.CFSolverRH.solver is None or callable(cf_handler_module.CFSolverRH.solver)

    def test_cf_handler_custom_solver(self, cf_handler_module):

        def custom_solver(req, resp, handler):
            return req

        result = cf_handler_module.set_cf_handler(custom_solver)
        assert result is cf_handler_module.CFSolverRH
        assert cf_handler_module.CFSolverRH.solver is custom_solver


class TestCFSolverRH:
    @pytest.fixture(autouse=True)
    def setup(self, cf_handler_module):
        self.module = cf_handler_module
        self.handler = self.module.CFSolverRH(logger=Mock(), verbose=False)

    def test_init_default(self):
        handler = self.module.CFSolverRH(logger=Mock(), verbose=False)
        assert handler._solver is not None
        assert handler._fallback_director is None

    def test_init_custom_solver(self):

        def custom_solver(req, resp, handler):
            return req

        handler = self.module.CFSolverRH(logger=Mock(), verbose=False, solver=custom_solver)
        assert handler._solver is custom_solver

    def test_close(self):
        mock_director = Mock()
        self.handler._fallback_director = mock_director

        self.handler.close()

        mock_director.close.assert_called_once()
        assert self.handler._fallback_director is None

    def test_solve(self):
        request = Mock()
        request.url = "https://example.com"
        request.headers = {}
        request.extensions = {}

        response = Mock()

        self.handler._solver = Mock(return_value=request)
        result = self.handler._solve(request, response)
        assert result is request
        self.handler._solver.assert_called_once()

        self.handler._solver = None
        result = self.handler._solve(request, response)
        assert result is None

    def test_mark_retry(self):
        request = Mock()
        request.copy = Mock(return_value=Mock())
        request.copy.return_value.extensions = {}

        new_request = self.module.CFSolverRH._mark_retry(request)

        assert new_request.extensions.get("cf_retry") is True

    def test_cached_user_agent(self, cf_handler_module):
        request = Mock(
            url="https://example.com/path",
            headers={"User-Agent": "original"},
            extensions={},
            proxies=None,
        )
        response = Mock(status=200, headers={})
        director = Mock()
        director.send.return_value = response
        self.handler._build_fallback = Mock(return_value=director)
        self.handler._get_cookiejar = Mock(return_value=http.cookiejar.CookieJar())

        with patch.object(
            cf_handler_module.CACHE,
            "get",
            return_value={"cookies": [], "userAgent": "FlareSolverr/Browser"},
        ):
            result = self.handler._send(request)

        assert result is response
        assert request.headers["User-Agent"] == "FlareSolverr/Browser"
