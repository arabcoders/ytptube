"""Comprehensive tests for httpx_client Cloudflare challenge solving."""

from __future__ import annotations

import http.cookiejar
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from app.library.httpx_client import (
    CFAsyncTransport,
    CFTransport,
    _get_transport,
    async_client,
    sync_client,
)


class TestGetTransport:
    """Test transport factory function."""

    def test_get_transport_cf_enabled_async(self):
        """Test getting async transport with CF enabled."""
        transport = _get_transport(enable_cf=True, is_async=True, transport=None)
        assert isinstance(transport, CFAsyncTransport)

    def test_get_transport_cf_enabled_sync(self):
        """Test getting sync transport with CF enabled."""
        transport = _get_transport(enable_cf=False, is_async=False, transport=None)
        assert isinstance(transport, httpx.HTTPTransport)

    def test_get_transport_cf_disabled_async(self):
        """Test getting async transport with CF disabled."""
        transport = _get_transport(enable_cf=False, is_async=True, transport=None)
        assert isinstance(transport, httpx.AsyncHTTPTransport)

    def test_get_transport_cf_disabled_sync(self):
        """Test getting sync transport with CF disabled."""
        transport = _get_transport(enable_cf=False, is_async=False, transport=None)
        assert isinstance(transport, httpx.HTTPTransport)

    def test_get_transport_custom_base_async(self):
        """Test getting transport with custom base transport."""
        custom_transport = httpx.AsyncHTTPTransport()
        transport = _get_transport(enable_cf=True, is_async=True, transport=custom_transport)
        assert isinstance(transport, CFAsyncTransport)
        assert transport.base is custom_transport

    def test_get_transport_custom_base_sync(self):
        """Test getting transport with custom base transport."""
        custom_transport = httpx.HTTPTransport()
        transport = _get_transport(enable_cf=True, is_async=False, transport=custom_transport)
        assert isinstance(transport, CFTransport)
        assert transport.base is custom_transport


class TestCFAsyncTransport:
    """Test async Cloudflare transport wrapper."""

    def setup_method(self):
        """Set up test fixtures."""
        self.base_transport = AsyncMock(spec=httpx.AsyncHTTPTransport)
        self.transport = CFAsyncTransport(base=self.base_transport)

    @pytest.mark.asyncio
    async def test_init_default(self):
        """Test initialization with defaults."""
        transport = CFAsyncTransport()
        assert isinstance(transport.base, httpx.AsyncHTTPTransport)

    @pytest.mark.asyncio
    async def test_init_custom(self):
        """Test initialization with custom base."""
        assert self.transport.base is self.base_transport

    @pytest.mark.asyncio
    @patch("app.library.httpx_client.is_cf_challenge")
    async def test_handle_request_no_challenge(self, mock_is_cf):
        """Test handling request without Cloudflare challenge."""
        mock_is_cf.return_value = False

        request = httpx.Request("GET", "https://example.com")
        response = Mock(status_code=200, headers={})
        self.base_transport.handle_async_request.return_value = response

        result = await self.transport.handle_async_request(request)

        assert result is response
        self.base_transport.handle_async_request.assert_called_once()
        mock_is_cf.assert_called_once_with(200, {})

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @patch("app.library.httpx_client.solver")
    @patch("app.library.httpx_client.is_cf_challenge")
    async def test_handle_request_cached_solution(self, mock_is_cf, mock_solver):
        """Test handling request with Cloudflare solution from cache."""
        mock_is_cf.return_value = True
        mock_solver.return_value = {
            "cookies": [{"name": "cf_clearance", "value": "token123"}],
            "userAgent": "Mozilla/5.0",
        }

        request = httpx.Request("GET", "https://example.com")
        response1 = Mock(status_code=403, headers={"Server": "cloudflare"})
        response1.aclose = AsyncMock()
        response2 = Mock(status_code=200, headers={})

        self.base_transport.handle_async_request.side_effect = [response1, response2]

        result = await self.transport.handle_async_request(request)

        assert result is response2
        assert 2 == self.base_transport.handle_async_request.call_count
        mock_solver.assert_called_once()
        response1.aclose.assert_called_once()

        second_call_request = self.base_transport.handle_async_request.call_args_list[1][0][0]
        assert "cf_clearance=token123" == second_call_request.headers["Cookie"]
        assert "Mozilla/5.0" == second_call_request.headers["User-Agent"]

    @pytest.mark.asyncio
    @patch("app.library.httpx_client.solver")
    @patch("app.library.httpx_client.is_cf_challenge")
    async def test_handle_request_solve_challenge(self, mock_is_cf, mock_solver):
        """Test handling request by solving Cloudflare challenge."""
        mock_is_cf.return_value = True
        mock_solver.return_value = {
            "cookies": [{"name": "cf_clearance", "value": "token123"}, {"name": "__cf_bm", "value": "bm456"}],
            "userAgent": "Mozilla/5.0",
        }

        request = httpx.Request("GET", "https://example.com")
        response1 = Mock(status_code=403, headers={"cf-ray": "123"})
        response1.aclose = AsyncMock()
        response2 = Mock(status_code=200, headers={})

        self.base_transport.handle_async_request.side_effect = [response1, response2]

        result = await self.transport.handle_async_request(request)

        assert result is response2
        assert 2 == self.base_transport.handle_async_request.call_count
        mock_solver.assert_called_once()
        response1.aclose.assert_called_once()

        second_call_request = self.base_transport.handle_async_request.call_args_list[1][0][0]
        assert "cf_clearance=token123; __cf_bm=bm456" == second_call_request.headers["Cookie"]
        assert "Mozilla/5.0" == second_call_request.headers["User-Agent"]

    @pytest.mark.asyncio
    @patch("app.library.httpx_client.solver")
    @patch("app.library.httpx_client.is_cf_challenge")
    async def test_handle_request_merge_existing_cookies(self, mock_is_cf, mock_solver):
        """Test that existing cookies are preserved when adding CF cookies."""
        mock_is_cf.return_value = True
        mock_solver.return_value = {
            "cookies": [{"name": "cf_clearance", "value": "token123"}],
            "userAgent": "Mozilla/5.0",
        }

        request = httpx.Request("GET", "https://example.com", cookies={"session_id": "abc123", "user_pref": "dark"})
        response1 = Mock(status_code=403, headers={"cf-ray": "123"})
        response1.aclose = AsyncMock()
        response2 = Mock(status_code=200, headers={})

        self.base_transport.handle_async_request.side_effect = [response1, response2]

        result = await self.transport.handle_async_request(request)

        assert result is response2

        second_call_request = self.base_transport.handle_async_request.call_args_list[1][0][0]
        cookie_header = second_call_request.headers["Cookie"]
        assert "session_id=abc123" in cookie_header
        assert "user_pref=dark" in cookie_header
        assert "cf_clearance=token123" in cookie_header

    @pytest.mark.asyncio
    @patch("app.library.httpx_client.solver")
    @patch("app.library.httpx_client.is_cf_challenge")
    async def test_handle_request_solve_failed(self, mock_is_cf, mock_solver):
        """Test handling request when solving fails."""
        mock_is_cf.return_value = True
        mock_solver.return_value = None

        request = httpx.Request("GET", "https://example.com")
        response = Mock(status_code=403, headers={"cf-ray": "123"})
        response.close = Mock()

        self.base_transport.handle_async_request.return_value = response

        result = await self.transport.handle_async_request(request)

        assert result is response
        assert 1 == self.base_transport.handle_async_request.call_count
        mock_solver.assert_called_once()
        response.close.assert_not_called()

    def test_close(self):
        """Test closing transport."""
        self.base_transport.close = Mock()
        self.transport.close()
        self.base_transport.close.assert_called_once()


class TestCFTransport:
    """Test sync Cloudflare transport wrapper."""

    def setup_method(self):
        """Set up test fixtures."""
        self.base_transport = Mock(spec=httpx.HTTPTransport)
        self.transport = CFTransport(base=self.base_transport)

    def test_init_default(self):
        """Test initialization with defaults."""
        transport = CFTransport()
        assert isinstance(transport.base, httpx.HTTPTransport)

    def test_init_custom(self):
        """Test initialization with custom base."""
        assert self.transport.base is self.base_transport

    @patch("app.library.httpx_client.is_cf_challenge")
    def test_handle_request_no_challenge(self, mock_is_cf):
        """Test handling request without Cloudflare challenge."""
        mock_is_cf.return_value = False

        request = httpx.Request("GET", "https://example.com")
        response = Mock(status_code=200, headers={})
        self.base_transport.handle_request.return_value = response

        result = self.transport.handle_request(request)

        assert result is response
        self.base_transport.handle_request.assert_called_once()
        mock_is_cf.assert_called_once_with(200, {})

    @patch("app.library.httpx_client.solver")
    @patch("app.library.httpx_client.is_cf_challenge")
    def test_handle_request_cached_solution(self, mock_is_cf, mock_solver):
        """Test handling request with Cloudflare solution from cache."""
        mock_is_cf.return_value = True
        mock_solver.return_value = {
            "cookies": [{"name": "cf_clearance", "value": "token123"}],
            "userAgent": "Mozilla/5.0",
        }

        request = httpx.Request("GET", "https://example.com")
        response1 = Mock(status_code=403, headers={"Server": "cloudflare"})
        response1.close = Mock()
        response2 = Mock(status_code=200, headers={})

        self.base_transport.handle_request.side_effect = [response1, response2]

        result = self.transport.handle_request(request)

        assert result is response2
        assert 2 == self.base_transport.handle_request.call_count
        mock_solver.assert_called_once()
        response1.close.assert_called_once()

        second_call_request = self.base_transport.handle_request.call_args_list[1][0][0]
        assert "cf_clearance=token123" == second_call_request.headers["Cookie"]
        assert "Mozilla/5.0" == second_call_request.headers["User-Agent"]

    @patch("app.library.httpx_client.solver")
    @patch("app.library.httpx_client.is_cf_challenge")
    def test_handle_request_solve_challenge(self, mock_is_cf, mock_solver):
        """Test handling request by solving Cloudflare challenge."""
        mock_is_cf.return_value = True
        mock_solver.return_value = {
            "cookies": [{"name": "cf_clearance", "value": "token123"}, {"name": "__cf_bm", "value": "bm456"}],
            "userAgent": "Mozilla/5.0",
        }

        request = httpx.Request("GET", "https://example.com")
        response1 = Mock(status_code=503, headers={"cf-cache-status": "DYNAMIC"})
        response1.close = Mock()
        response2 = Mock(status_code=200, headers={})

        self.base_transport.handle_request.side_effect = [response1, response2]

        result = self.transport.handle_request(request)

        assert result is response2
        assert 2 == self.base_transport.handle_request.call_count
        mock_solver.assert_called_once()
        response1.close.assert_called_once()

        second_call_request = self.base_transport.handle_request.call_args_list[1][0][0]
        assert "cf_clearance=token123; __cf_bm=bm456" == second_call_request.headers["Cookie"]
        assert "Mozilla/5.0" == second_call_request.headers["User-Agent"]

    @patch("app.library.httpx_client.solver")
    @patch("app.library.httpx_client.is_cf_challenge")
    def test_handle_request_merge_existing_cookies(self, mock_is_cf, mock_solver):
        """Test that existing cookies are preserved when adding CF cookies."""
        mock_is_cf.return_value = True
        mock_solver.return_value = {
            "cookies": [{"name": "cf_clearance", "value": "token123"}],
            "userAgent": "Mozilla/5.0",
        }

        request = httpx.Request("GET", "https://example.com", cookies={"session_id": "abc123", "user_pref": "dark"})
        response1 = Mock(status_code=403, headers={"cf-ray": "123"})
        response1.close = Mock()
        response2 = Mock(status_code=200, headers={})

        self.base_transport.handle_request.side_effect = [response1, response2]

        result = self.transport.handle_request(request)

        assert result is response2

        second_call_request = self.base_transport.handle_request.call_args_list[1][0][0]
        cookie_header = second_call_request.headers["Cookie"]
        assert "session_id=abc123" in cookie_header
        assert "user_pref=dark" in cookie_header
        assert "cf_clearance=token123" in cookie_header

    @patch("app.library.httpx_client.solver")
    @patch("app.library.httpx_client.is_cf_challenge")
    def test_handle_request_solve_failed(self, mock_is_cf, mock_solver):
        """Test handling request when solving fails."""
        mock_is_cf.return_value = True
        mock_solver.return_value = None

        request = httpx.Request("GET", "https://example.com")
        response = Mock(status_code=429, headers={"cf-ray": "abc123"})
        response.close = Mock()

        self.base_transport.handle_request.return_value = response

        result = self.transport.handle_request(request)

        assert result is response
        assert 1 == self.base_transport.handle_request.call_count
        mock_solver.assert_called_once()
        response.close.assert_not_called()

    def test_close(self):
        """Test closing transport."""
        self.base_transport.close = Mock()
        self.transport.close()
        self.base_transport.close.assert_called_once()


class TestAsyncClient:
    """Test async client factory function."""

    @pytest.mark.asyncio
    async def test_async_client_cf_enabled(self):
        """Test creating async client with CF enabled."""
        async with async_client(enable_cf=True) as client:
            assert isinstance(client, httpx.AsyncClient)
            assert isinstance(client._transport, CFAsyncTransport)

    @pytest.mark.asyncio
    async def test_async_client_cf_disabled(self):
        """Test creating async client with CF disabled."""
        async with async_client(enable_cf=False) as client:
            assert isinstance(client, httpx.AsyncClient)
            assert isinstance(client._transport, httpx.AsyncHTTPTransport)

    @pytest.mark.asyncio
    async def test_async_client_kwargs(self):
        """Test creating async client with additional kwargs."""
        async with async_client(enable_cf=True, timeout=30.0, follow_redirects=True) as client:
            assert isinstance(client, httpx.AsyncClient)
            assert isinstance(client._transport, CFAsyncTransport)
            assert 30.0 == client.timeout.read
            assert client.follow_redirects is True

    @pytest.mark.asyncio
    async def test_async_client_custom_transport(self):
        """Test creating async client with custom transport."""
        custom = httpx.AsyncHTTPTransport()
        async with async_client(enable_cf=True, transport=custom) as client:
            assert isinstance(client, httpx.AsyncClient)
            assert isinstance(client._transport, CFAsyncTransport)
            assert client._transport.base is custom

    @pytest.mark.asyncio
    async def test_async_client_custom_transport_cf_disabled(self):
        """Test creating async client with custom transport and CF disabled."""
        custom = httpx.AsyncHTTPTransport()
        async with async_client(enable_cf=False, transport=custom) as client:
            assert isinstance(client, httpx.AsyncClient)

            assert client._transport is custom


class TestSyncClient:
    """Test sync client factory function."""

    def test_sync_client_cf_enabled(self):
        """Test creating sync client with CF enabled."""
        client = sync_client(enable_cf=True)
        assert isinstance(client, httpx.Client)
        assert isinstance(client._transport, CFTransport)
        client.close()

    def test_sync_client_cf_disabled(self):
        """Test creating sync client with CF disabled."""
        client = sync_client(enable_cf=False)
        assert isinstance(client, httpx.Client)
        assert isinstance(client._transport, httpx.HTTPTransport)
        client.close()

    def test_sync_client_kwargs(self):
        """Test creating sync client with additional kwargs."""
        client = sync_client(enable_cf=True, timeout=30.0, follow_redirects=True)
        assert isinstance(client, httpx.Client)
        assert isinstance(client._transport, CFTransport)
        assert 30.0 == client.timeout.read
        assert client.follow_redirects is True
        client.close()

    def test_sync_client_custom_transport(self):
        """Test creating sync client with custom transport."""
        custom = httpx.HTTPTransport()
        client = sync_client(enable_cf=True, transport=custom)
        assert isinstance(client, httpx.Client)
        assert isinstance(client._transport, CFTransport)
        assert client._transport.base is custom
        client.close()

    def test_sync_client_custom_transport_cf_disabled(self):
        """Test creating sync client with custom transport and CF disabled."""
        custom = httpx.HTTPTransport()
        client = sync_client(enable_cf=False, transport=custom)
        assert isinstance(client, httpx.Client)
        assert client._transport is custom, "When CF is disabled, custom transport should be used directly"
        client.close()
