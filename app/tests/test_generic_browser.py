from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from app.yt_dlp_plugins.extractor import generic_browser


def _make_ie(config: dict[str, str | None] | None = None) -> Any:
    ie: Any = object.__new__(generic_browser.GenericBrowserIE)
    values = config or {}
    ie._configuration_arg = lambda name, default: [values.get(name)]
    ie._generic_id = lambda url: "vid"
    ie._generic_title = lambda url, webpage=None: "title"
    ie._get_timeout_ms = lambda: None
    ie.report_warning = Mock()
    ie.report_extraction = Mock()
    ie.playlist_result = Mock(side_effect=lambda entries, **kwargs: {"_type": "playlist", "entries": entries, **kwargs})
    ie._looks_like_html = lambda webpage: False
    ie._merge_requests = lambda network, media: list(network) + list(media)
    ie._extract_network_formats = Mock(
        return_value={"formats": [{"url": "https://cdn.example/video.mp4", "ext": "mp4"}]}
    )
    ie.to_screen = Mock()
    ie.write_debug = Mock()
    ie._downloader = Mock()
    ie._downloader.params = {}
    ie._failed = False
    return ie


def test_cfg_env(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setenv("YTP_BROWSER_URL", "  http://browser:9222  ")

    assert ie._get_config("url", "YTP_BROWSER_URL") == "http://browser:9222"


def test_cfg_arg_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie({"url": "http://arg:9222"})
    monkeypatch.setenv("YTP_BROWSER_URL", "http://env:9222")

    assert ie._get_config("url", "YTP_BROWSER_URL") == "http://arg:9222"


def test_wait_config() -> None:
    assert _make_ie()._get_wait() == generic_browser.BROWSER_WAIT_SECONDS
    assert _make_ie({"wait": "3.5"})._get_wait() == 3.5


@pytest.mark.parametrize("value", ["invalid", "-1", "301", "nan"])
def test_wait_invalid(value: str) -> None:
    with pytest.raises(generic_browser.ExtractorError, match="Invalid browser wait value"):
        _make_ie({"wait": value})._get_wait()


def test_wait_existing_media() -> None:
    wait = Mock()
    wait_for_media = Mock()

    generic_browser._wait_for_network_idle(
        [{"url": "https://cdn.example/video.mp4"}], wait, wait_for_media, max_total_timeout=60
    )

    wait.assert_not_called()
    wait_for_media.assert_not_called()


def test_wait_media_during_idle() -> None:
    requests: list[dict[str, str]] = []

    def wait(_timeout: int) -> bool:
        requests.append({"url": "https://cdn.example/video.mp4"})
        return False

    wait_for_media = Mock()
    generic_browser._wait_for_network_idle(requests, wait, wait_for_media, max_total_timeout=1)

    wait_for_media.assert_not_called()


def test_wait_zero() -> None:
    wait = Mock()
    wait_for_media = Mock()

    generic_browser._wait_for_network_idle([], wait, wait_for_media, max_total_timeout=0)

    wait.assert_not_called()
    wait_for_media.assert_not_called()


def test_safe_url() -> None:
    ie = _make_ie()

    assert (
        ie._safe_url("http://user:pass@10.0.0.6:9222/cdp?token=abc#frag") == "http://***:***@10.0.0.6:9222/cdp?***#***"
    )


def test_real_extract_env(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()

    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser:9222")
    monkeypatch.setattr(generic_browser.CdpDriver, "is_available", staticmethod(lambda: False))

    with pytest.raises(generic_browser.ExtractorError, match="No matching browser driver available"):
        ie._real_extract("https://example.com/watch")


def test_real_extract_invalid_url(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser:4444/wd/hub")

    with pytest.raises(generic_browser.ExtractorError, match="Invalid browser URL"):
        ie._real_extract("https://example.com/watch")


def test_log_connect_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    ie.__wrapped__ = Mock()
    ie.__wrapped__._real_extract = Mock(return_value={"id": "fallback"})
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser:9222")

    class BrokenDriver:
        __name__ = "BrokenDriver"

        @staticmethod
        def connect(ws_url: str, timeout: int | None = None):
            raise RuntimeError("remote browser down")

    monkeypatch.setattr(generic_browser.GenericBrowserIE, "_select_driver", lambda self, ws_url: BrokenDriver)

    result = ie._real_extract("https://example.com/watch")

    assert result == {"id": "fallback"}
    ie.report_warning.assert_called_once_with(
        "Remote browser unavailable: remote browser down, marking as failed.", "vid"
    )
    ie.to_screen.assert_called_once_with("Using remote browser for https://example.com/watch")


def test_log_session_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser/path?token=secret")

    session = Mock()
    session.goto.side_effect = RuntimeError("page crashed")

    class FakeDriver:
        __name__ = "FakeDriver"

        @staticmethod
        def connect(ws_url: str, timeout: int | None = None):
            return session

    monkeypatch.setattr(generic_browser.GenericBrowserIE, "_select_driver", lambda self, ws_url: FakeDriver)

    with pytest.raises(RuntimeError, match="page crashed"):
        ie._real_extract("https://example.com/watch")

    assert session.close.call_count == 1
    ie.report_warning.assert_called_once_with(
        "Browser extractor session failed for url='https://example.com/watch' "
        "browser_url='http://browser/path?***' driver=FakeDriver error=page crashed",
        "vid",
    )
    ie.write_debug.assert_any_call("Selected driver FakeDriver for http://browser/path?***")
    ie.write_debug.assert_any_call("Loading page https://example.com/watch")


def test_log_close_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser/path?token=secret")

    session = Mock()
    session.content.return_value = ""
    session.get_requests.return_value = []
    session.get_media_requests.return_value = []
    session.close.side_effect = RuntimeError("close failed")

    class FakeDriver:
        __name__ = "FakeDriver"

        @staticmethod
        def connect(ws_url: str, timeout: int | None = None):
            return session

    monkeypatch.setattr(generic_browser.GenericBrowserIE, "_select_driver", lambda self, ws_url: FakeDriver)

    ie._real_extract("https://example.com/watch")

    ie.report_warning.assert_called_once_with(
        "Browser session close failed for url='https://example.com/watch' "
        "browser_url='http://browser/path?***' driver=FakeDriver error=close failed",
        "vid",
    )


def test_log_non_html(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser")

    session = Mock()
    session.content.return_value = "plain text body"
    session.get_requests.return_value = [
        {"url": "https://cdn.example/video.mp4", "method": "GET", "resourceType": "video"}
    ]
    session.get_media_requests.return_value = []

    class FakeDriver:
        __name__ = "FakeDriver"

        @staticmethod
        def connect(ws_url: str, timeout: int | None = None):
            return session

    monkeypatch.setattr(generic_browser.GenericBrowserIE, "_select_driver", lambda self, ws_url: FakeDriver)

    result = ie._real_extract("https://example.com/watch")

    assert result["formats"][0]["url"] == "https://cdn.example/video.mp4"
    ie.write_debug.assert_any_call("Page content did not look like HTML for https://example.com/watch")
    ie.write_debug.assert_any_call("plain text body")


def test_html_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser")
    ie._looks_like_html = lambda webpage: True
    ie._generic_title = generic_browser.GenericIE._generic_title.__get__(ie, generic_browser.GenericBrowserIE)

    session = Mock()
    session.content.return_value = (
        '<html><head><meta property="og:title" content="OG Title">'
        '<meta name="description" content="Meta Desc">'
        '<meta property="og:image" content="https://img.example/thumb.jpg">'
        "</head><body><title>Page Title</title></body></html>"
    )
    session.get_requests.return_value = []
    session.get_media_requests.return_value = []

    class FakeDriver:
        __name__ = "FakeDriver"

        @staticmethod
        def connect(ws_url: str, timeout: int | None = None):
            return session

    monkeypatch.setattr(generic_browser.GenericBrowserIE, "_select_driver", lambda self, ws_url: FakeDriver)

    result = ie._real_extract("https://example.com/watch")

    assert result["title"] == "OG Title"
    assert result["description"] == "Meta Desc"
    assert result["thumbnail"] == "https://img.example/thumb.jpg"


def test_no_media() -> None:
    ie = _make_ie()
    ie.__wrapped__ = Mock()
    ie.__wrapped__._real_extract = Mock(return_value={"id": "fallback"})
    ie._url = "https://example.com/watch"
    ie._extract_network_formats = generic_browser.GenericBrowserIE._extract_network_formats.__get__(
        ie, generic_browser.GenericBrowserIE
    )

    result = ie._extract_network_formats([], "vid", {"title": "title"})

    assert result is None
    ie.__wrapped__._real_extract.assert_not_called()
    ie.write_debug.assert_called_with("No media formats found in 0 browser request(s)")
    ie.report_warning.assert_not_called()


def test_media_fallback_outside_session(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    ie.__wrapped__ = Mock()
    ie.__wrapped__._real_extract.side_effect = RuntimeError("fallback failed")
    ie._extract_network_formats = generic_browser.GenericBrowserIE._extract_network_formats.__get__(
        ie, generic_browser.GenericBrowserIE
    )
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser")

    session = Mock()
    session.content.return_value = ""
    session.get_requests.return_value = []
    session.get_media_requests.return_value = []

    class FakeDriver:
        __name__ = "FakeDriver"

        @staticmethod
        def connect(ws_url: str, timeout: int | None = None):
            return session

    monkeypatch.setattr(generic_browser.GenericBrowserIE, "_select_driver", lambda self, ws_url: FakeDriver)

    with pytest.raises(RuntimeError, match="fallback failed"):
        ie._real_extract("https://example.com/watch")

    session.close.assert_called_once_with()
    ie.report_warning.assert_called_once_with(
        "Generic browser extractor found no media formats; falling back to generic extractor.", "vid"
    )


@pytest.mark.parametrize("status", [200, 301, 400, 401])
def test_status_fallback(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    ie = _make_ie()
    ie.__wrapped__ = Mock()
    ie.__wrapped__._real_extract.return_value = {"id": "fallback"}
    ie._extract_network_formats = generic_browser.GenericBrowserIE._extract_network_formats.__get__(
        ie, generic_browser.GenericBrowserIE
    )
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser")

    session = Mock()
    session.goto.return_value = status
    session.content.return_value = ""
    session.get_requests.return_value = [
        {"url": "https://example.com/watch", "resourceType": "document", "response": {"status": status}}
    ]
    session.get_media_requests.return_value = []

    class FakeDriver:
        __name__ = "FakeDriver"

        @staticmethod
        def connect(ws_url: str, timeout: int | None = None):
            return session

    monkeypatch.setattr(generic_browser.GenericBrowserIE, "_select_driver", lambda self, ws_url: FakeDriver)

    assert ie._real_extract("https://example.com/watch") == {"id": "fallback"}
    ie.__wrapped__._real_extract.assert_called_once_with(ie, "https://example.com/watch")
    session.wait_for_network_idle.assert_called_once_with(
        api_poll_attempts=10,
        api_poll_interval=500,
        max_total_timeout=generic_browser.BROWSER_WAIT_SECONDS,
    )
    session.close.assert_called_once_with()


@pytest.mark.parametrize("status", sorted(generic_browser.HARD_HTTP_STATUSES))
def test_status_terminal(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    ie = _make_ie()
    ie.__wrapped__ = Mock()
    ie._extract_network_formats = generic_browser.GenericBrowserIE._extract_network_formats.__get__(
        ie, generic_browser.GenericBrowserIE
    )
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser")

    session = Mock()
    session.goto.return_value = status
    session.content.return_value = ""
    session.get_requests.return_value = [
        {"url": "https://example.com/missing", "resourceType": "document", "response": {"status": status}}
    ]
    session.get_media_requests.return_value = []

    class FakeDriver:
        __name__ = "FakeDriver"

        @staticmethod
        def connect(ws_url: str, timeout: int | None = None):
            return session

    monkeypatch.setattr(generic_browser.GenericBrowserIE, "_select_driver", lambda self, ws_url: FakeDriver)

    with pytest.raises(generic_browser.ExtractorError, match=f"Remote browser returned HTTP Error {status}") as exc:
        ie._real_extract("https://example.com/missing")

    assert exc.value.expected
    ie.__wrapped__._real_extract.assert_not_called()
    session.wait_for_network_idle.assert_not_called()
    session.close.assert_called_once_with()


def test_wait_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie({"wait": "2.5"})
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser")

    session = Mock()
    session.content.return_value = ""
    session.get_requests.return_value = []
    session.get_media_requests.return_value = []

    class FakeDriver:
        __name__ = "FakeDriver"

        @staticmethod
        def connect(ws_url: str, timeout: int | None = None):
            return session

    monkeypatch.setattr(generic_browser.GenericBrowserIE, "_select_driver", lambda self, ws_url: FakeDriver)
    ie.__wrapped__ = Mock()
    ie.__wrapped__._real_extract.return_value = {"id": "fallback"}

    ie._real_extract("https://example.com/watch")

    session.wait_for_network_idle.assert_called_once_with(
        api_poll_attempts=10,
        api_poll_interval=500,
        max_total_timeout=2.5,
    )


def test_entries_keep_own_urls() -> None:
    ie = _make_ie()
    ie._extract_network_formats = generic_browser.GenericBrowserIE._extract_network_formats.__get__(
        ie, generic_browser.GenericBrowserIE
    )

    result = ie._extract_network_formats(
        [
            {"url": "https://cdn.example/1.mp3", "method": "GET", "resourceType": "audio"},
            {"url": "https://cdn.example/2.mp3", "method": "GET", "resourceType": "audio"},
        ],
        "vid",
        {"title": "Title", "webpage_url": "https://example.com/page", "original_url": "https://example.com/page"},
    )

    assert result is not None
    assert result["_type"] == "playlist"
    assert result["entries"][0]["url"] == "https://cdn.example/1.mp3"
    assert result["entries"][0]["webpage_url"] == "https://cdn.example/1.mp3"
    assert result["entries"][0]["original_url"] == "https://cdn.example/1.mp3"
    assert result["entries"][0]["_old_archive_ids"] == [generic_browser.make_archive_id("generic", "vid-1")]
    assert result["entries"][0]["direct"] is True
    assert result["entries"][1]["url"] == "https://cdn.example/2.mp3"
    assert result["entries"][1]["webpage_url"] == "https://cdn.example/2.mp3"
    assert result["entries"][1]["original_url"] == "https://cdn.example/2.mp3"
    assert result["entries"][1]["_old_archive_ids"] == [generic_browser.make_archive_id("generic", "vid-2")]
    assert result["entries"][1]["direct"] is True


@pytest.mark.parametrize("url", ["http://playwright:9222/", "https://chrome:9222/"])
def test_select_driver_cdp(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    ie = _make_ie()
    monkeypatch.setattr(generic_browser.CdpDriver, "is_available", staticmethod(lambda: True))

    assert ie._select_driver(url) is generic_browser.CdpDriver


@pytest.mark.parametrize("url", ["ws://browser:9222", "http://browser:9222/wd/hub/"])
def test_select_driver_rejects(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    with pytest.raises(generic_browser.ExtractorError, match="Invalid browser URL"):
        _make_ie()._select_driver(url)


def _cdp_mocks(monkeypatch: pytest.MonkeyPatch, contexts: list[Mock]) -> tuple[Mock, Mock]:
    from playwright import sync_api

    playwright = Mock()
    starter = Mock()
    starter.start.return_value = playwright
    browser = Mock()
    browser.contexts = contexts
    playwright.chromium.connect_over_cdp.return_value = browser

    monkeypatch.setattr(sync_api, "sync_playwright", lambda: starter)
    monkeypatch.setattr(generic_browser.CdpDriver, "is_available", staticmethod(lambda: True))
    return playwright, browser


def test_cdp_reuses_context(monkeypatch: pytest.MonkeyPatch) -> None:
    context = Mock()
    page = context.new_page.return_value
    playwright, browser = _cdp_mocks(monkeypatch, [context])

    session = generic_browser.CdpDriver.connect("http://browser")
    session.close()
    session.close()

    context.new_page.assert_called_once_with()
    browser.new_context.assert_not_called()
    page.close.assert_called_once_with()
    context.close.assert_not_called()
    browser.close.assert_called_once_with()
    playwright.stop.assert_called_once_with()


def test_cdp_owns_context(monkeypatch: pytest.MonkeyPatch) -> None:
    playwright, browser = _cdp_mocks(monkeypatch, [])
    context = browser.new_context.return_value
    page = context.new_page.return_value

    session = generic_browser.CdpDriver.connect("http://browser")
    session.close()

    browser.new_context.assert_called_once_with()
    page.close.assert_called_once_with()
    context.close.assert_called_once_with()
    browser.close.assert_called_once_with()
    playwright.stop.assert_called_once_with()


def test_cdp_post(monkeypatch: pytest.MonkeyPatch) -> None:
    context = Mock()
    page = context.new_page.return_value
    response = Mock(status=201)
    response.text.return_value = '{"ok":true}'
    page.goto.return_value = response
    _, _ = _cdp_mocks(monkeypatch, [context])

    session = generic_browser.CdpDriver.connect("http://browser")
    status = session.goto(
        "https://example.com/submit",
        method="POST",
        headers={"Content-Type": "application/json"},
        data='{"ok":true}',
        timeout=2500,
    )
    route_handler = page.route.call_args.args[1]
    route = Mock()
    request = Mock()
    request.is_navigation_request.return_value = True
    request.frame = page.main_frame
    route_handler(route, request)
    session.wait_for_selector("xpath", "//main", 1.5)

    assert status == 201
    assert session.response_text() == '{"ok":true}'
    page.set_extra_http_headers.assert_called_once_with({"Content-Type": "application/json"})
    page.goto.assert_called_once_with(
        "https://example.com/submit",
        wait_until="domcontentloaded",
        timeout=2500,
    )
    route.continue_.assert_called_once_with(method="POST", post_data='{"ok":true}')
    page.unroute.assert_called_once_with("**/*", route_handler)
    page.wait_for_selector.assert_called_once_with("xpath=//main", timeout=1500.0)


def test_cdp_connect_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    playwright, _ = _cdp_mocks(monkeypatch, [])
    playwright.chromium.connect_over_cdp.side_effect = RuntimeError("connect failed")

    with pytest.raises(RuntimeError, match="connect failed"):
        generic_browser.CdpDriver.connect("http://browser")

    playwright.stop.assert_called_once_with()
