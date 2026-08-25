from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import Mock, patch

import pytest

from app.library.cf_solver_shared import _host_matches_cookie_domain, solver


class TestHostMatchesCookieDomain:
    @pytest.mark.parametrize(
        ("host", "domain", "expected"),
        [
            ("www.pexels.com", ".pexels.com", True),
            ("www.pexels.com", "pexels.com", True),
            ("pexels.com", ".pexels.com", True),
            ("www.pexels.com", ".vimeo.com", False),
            ("www.pexels.com", "vimeo.com", False),
            ("www.pexels.com", "", True),
            ("www.pexels.com", None, True),
            ("www.pexels.com", "notpexels.com", False),
            ("", ".pexels.com", False),
            ("www.youtube.com", ".youtube.com", True),
            ("youtube.com", ".youtube.com", True),
            ("consent.youtube.com", ".youtube.com", True),
            ("m.youtube.com", "youtube.com", True),
            ("www.youtube.com", ".google.com", False),
        ],
    )
    def test_matches(self, host, domain, expected):
        assert _host_matches_cookie_domain(host, domain) is expected


def _make_config():
    config = Mock()
    config.flaresolverr_url = "http://flaresolverr:8191/v1"
    config.flaresolverr_max_timeout = 120
    config.flaresolverr_client_timeout = 120
    config.flaresolverr_cache_ttl = 600
    return config


class TestSolver:
    @patch("app.library.cf_solver_shared.CACHE")
    @patch("app.library.cf_solver_shared.urllib.request.urlopen")
    @patch("app.library.config.Config")
    def test_filters_cross_domain_cookies(self, mock_config_cls, mock_urlopen, mock_cache):
        """Cookies for unrelated domains must not be forwarded to FlareSolverr."""
        mock_config_cls.get_instance.return_value = _make_config()
        mock_cache.get.return_value = None

        resp_data = json.dumps({"status": "ok", "solution": {"cookies": [], "userAgent": "UA"}}).encode()
        mock_urlopen.return_value.__enter__.return_value.read.return_value = resp_data

        cookies = [
            {"name": "cf_bm_pexels", "value": "a", "domain": ".pexels.com", "path": "/"},
            {"name": "vuid", "value": "b", "domain": ".vimeo.com", "path": "/"},
            {"name": "g_state", "value": "c", "domain": "vimeo.com", "path": "/"},
        ]

        solver("https://www.pexels.com/video/x-123/", cookies, "UA")

        sent = json.loads(mock_urlopen.call_args[0][0].data.decode())
        forwarded_names = {c["name"] for c in sent.get("cookies", [])}
        assert forwarded_names == {"cf_bm_pexels"}

    @patch("app.library.cf_solver_shared.CACHE")
    @patch("app.library.cf_solver_shared.urllib.request.urlopen")
    @patch("app.library.config.Config")
    def test_http_500_returns_none(self, mock_config_cls, mock_urlopen, mock_cache):
        """A FlareSolverr HTTP 500 must degrade to None, not raise."""
        mock_config_cls.get_instance.return_value = _make_config()
        mock_cache.get.return_value = None

        body = json.dumps({"status": "error", "message": "Error solving the challenge."}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://flaresolverr:8191/v1",
            code=500,
            msg="Internal Server Error",
            hdrs=Mock(),
            fp=io.BytesIO(body),
        )

        result = solver("https://www.pexels.com/video/x-123/", [], "UA")
        assert result is None
        mock_cache.set.assert_not_called()

    @patch("app.library.cf_solver_shared.CACHE")
    @patch("app.library.cf_solver_shared.urllib.request.urlopen")
    @patch("app.library.config.Config")
    def test_connection_error_returns_none(self, mock_config_cls, mock_urlopen, mock_cache):
        """A transport error reaching FlareSolverr must degrade to None, not raise."""
        mock_config_cls.get_instance.return_value = _make_config()
        mock_cache.get.return_value = None
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        result = solver("https://www.pexels.com/video/x-123/", [], "UA")
        assert result is None

    @patch("app.library.cf_solver_shared.CACHE")
    @patch("app.library.cf_solver_shared.urllib.request.urlopen")
    @patch("app.library.config.Config")
    def test_all_cookies_filtered_out(self, mock_config_cls, mock_urlopen, mock_cache):
        mock_config_cls.get_instance.return_value = _make_config()
        mock_cache.get.return_value = None

        resp_data = json.dumps({"status": "ok", "solution": {"cookies": [], "userAgent": "UA"}}).encode()
        mock_urlopen.return_value.__enter__.return_value.read.return_value = resp_data

        cookies = [
            {"name": "vuid", "value": "b", "domain": ".vimeo.com", "path": "/"},
            {"name": "g_state", "value": "c", "domain": "vimeo.com", "path": "/"},
        ]

        solver("https://www.pexels.com/video/x-123/", cookies, "UA")

        sent = json.loads(mock_urlopen.call_args[0][0].data.decode())
        assert "cookies" not in sent

    @patch("app.library.cf_solver_shared.CACHE")
    @patch("app.library.cf_solver_shared.urllib.request.urlopen")
    @patch("app.library.config.Config")
    def test_os_error_returns_none(self, mock_config_cls, mock_urlopen, mock_cache):
        mock_config_cls.get_instance.return_value = _make_config()
        mock_cache.get.return_value = None
        mock_urlopen.side_effect = OSError("connection reset")

        result = solver("https://www.pexels.com/video/x-123/", [], "UA")
        assert result is None
