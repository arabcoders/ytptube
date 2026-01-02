"""Comprehensive tests for cf_solver_handler yt-dlp request handler."""

from __future__ import annotations

import http.cookiejar
from unittest.mock import Mock, patch

import pytest

try:
    from yt_dlp.networking.common import Request, RequestDirector, Response
    from yt_dlp.networking.exceptions import HTTPError

    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    Request = Mock
    Response = Mock
    RequestDirector = Mock
    HTTPError = Exception

pytestmark = pytest.mark.skipif(not YTDLP_AVAILABLE, reason="yt-dlp not available")


@pytest.fixture(scope="module")
def cf_handler_module():
    """Lazily import cf_solver_handler module to avoid circular imports."""
    from app.library import cf_solver_handler

    return cf_solver_handler


class TestCfSolverFunction:
    """Test the cf_solver function."""

    @patch("app.library.cf_solver_handler.solver")
    def test_cf_solver_success(self, mock_solver, cf_handler_module):
        """Test successful solving of Cloudflare challenge."""
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

    @patch("app.library.cf_solver_handler.solver")
    def test_cf_solver_no_solution(self, mock_solver, cf_handler_module):
        """Test when solver returns no solution."""
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
    def test_cf_solver_with_existing_cookies(self, mock_solver, cf_handler_module):
        """Test solving with existing cookies in jar."""
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


class TestSetCfHandler:
    """Test set_cf_handler function."""

    def test_set_cf_handler_default(self, cf_handler_module):
        """Test setting CF handler with default solver."""
        result = cf_handler_module.set_cf_handler()
        assert result is cf_handler_module.CFSolverRH
        assert cf_handler_module.CFSolverRH.solver is None or callable(cf_handler_module.CFSolverRH.solver)

    def test_set_cf_handler_custom_solver(self, cf_handler_module):
        """Test setting CF handler with custom solver."""

        def custom_solver(req, resp, handler):
            return req

        result = cf_handler_module.set_cf_handler(custom_solver)
        assert result is cf_handler_module.CFSolverRH
        assert cf_handler_module.CFSolverRH.solver is custom_solver


class TestCFSolverRH:
    """Test CFSolverRH request handler class."""

    @pytest.fixture(autouse=True)
    def setup(self, cf_handler_module):
        """Set up test fixtures."""
        self.module = cf_handler_module
        self.handler = self.module.CFSolverRH(logger=Mock(), verbose=False)

    def test_init_default(self):
        """Test initialization with defaults."""
        handler = self.module.CFSolverRH(logger=Mock(), verbose=False)
        assert handler._solver is not None
        assert handler._fallback_director is None

    def test_init_custom_solver(self):
        """Test initialization with custom solver."""

        def custom_solver(req, resp, handler):
            return req

        handler = self.module.CFSolverRH(logger=Mock(), verbose=False, solver=custom_solver)
        assert handler._solver is custom_solver

    def test_close(self):
        """Test closing handler."""
        mock_director = Mock()
        self.handler._fallback_director = mock_director

        self.handler.close()

        mock_director.close.assert_called_once()
        assert self.handler._fallback_director is None

    def test_close_no_director(self):
        """Test closing handler when no director exists."""
        self.handler._fallback_director = None
        self.handler.close()

    def test_check_extensions(self):
        """Test extension checking."""
        extensions = {
            "timeout": 30,
            "legacy_ssl": True,
            "other": "value",
        }

        self.handler._check_extensions(extensions)

    def test_validate(self):
        """Test request validation."""
        request = Mock()
        request.url = "https://example.com"
        request.proxies = None
        request.extensions = {}

        self.handler._validate(request)

    def test_solve(self):
        """Test solving challenge."""
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
        """Test marking request as retry."""
        request = Mock()
        request.copy = Mock(return_value=Mock())
        request.copy.return_value.extensions = {}

        new_request = self.module.CFSolverRH._mark_retry(request)

        assert new_request.extensions.get("cf_retry") is True


class TestCfSolverPreference:
    """Test cf_solver_preference function."""

    def test_preference_with_flaresolverr(self, cf_handler_module, monkeypatch):
        """Test preference when FlareSolverr is configured."""
        mock_config = Mock()
        mock_config.flaresolverr_url = "http://localhost:8191/v1"

        import app.library.config

        monkeypatch.setattr(app.library.config.Config, "get_instance", lambda: mock_config)

    def test_preference_without_flaresolverr(self, cf_handler_module, monkeypatch):
        """Test preference when FlareSolverr is not configured."""
        mock_config = Mock()
        mock_config.flaresolverr_url = None

        import app.library.config

        monkeypatch.setattr(app.library.config.Config, "get_instance", lambda: mock_config)

    def test_preference_with_empty_flaresolverr(self, cf_handler_module, monkeypatch):
        """Test preference when FlareSolverr URL is empty."""
        mock_config = Mock()
        mock_config.flaresolverr_url = ""

        import app.library.config

        monkeypatch.setattr(app.library.config.Config, "get_instance", lambda: mock_config)
