from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.yt_dlp_plugins.extractor import generic_browser


def _make_ie(config: dict[str, str | None] | None = None) -> generic_browser.GenericBrowserIE:
    ie = object.__new__(generic_browser.GenericBrowserIE)
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
    monkeypatch.setenv("YTP_BROWSER_URL", "  selenium+http://browser:4444/wd/hub  ")

    assert ie._get_config("url", "YTP_BROWSER_URL") == "selenium+http://browser:4444/wd/hub"


def test_cfg_arg_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie({"url": "selenium+http://arg:4444/wd/hub"})
    monkeypatch.setenv("YTP_BROWSER_URL", "selenium+http://env:4444/wd/hub")

    assert ie._get_config("url", "YTP_BROWSER_URL") == "selenium+http://arg:4444/wd/hub"


def test_real_extract_env(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()

    monkeypatch.setenv("YTP_BROWSER_URL", "selenium+http://browser:4444/wd/hub")
    monkeypatch.setattr(generic_browser.SeleniumDriver, "is_available", staticmethod(lambda: False))

    with pytest.raises(generic_browser.ExtractorError, match="No matching browser driver available"):
        ie._real_extract("https://example.com/watch")


def test_real_extract_invalid_url(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setenv("YTP_BROWSER_URL", "http://browser:4444/wd/hub")

    with pytest.raises(generic_browser.ExtractorError, match="Invalid browser URL"):
        ie._real_extract("https://example.com/watch")


def test_real_extract_logs_connect_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    ie.__wrapped__ = Mock()
    ie.__wrapped__._real_extract = Mock(return_value={"id": "fallback"})
    monkeypatch.setenv("YTP_BROWSER_URL", "selenium+http://browser:4444/wd/hub")
    monkeypatch.setattr(generic_browser.SeleniumDriver, "is_available", staticmethod(lambda: True))

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


def test_real_extract_logs_session_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setenv("YTP_BROWSER_URL", "playwright+ws://browser")

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
        "Browser extractor session failed for url=%r browser_url=%r driver=%s error=%s",
        "https://example.com/watch",
        "playwright+ws://browser",
        "FakeDriver",
        session.goto.side_effect,
    )
    ie.write_debug.assert_any_call("Selected driver FakeDriver for playwright+ws://browser")
    ie.write_debug.assert_any_call("Loading page https://example.com/watch")


def test_real_extract_logs_non_html_page(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setenv("YTP_BROWSER_URL", "playwright+ws://browser")

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


def test_extract_network_formats_logs_no_media() -> None:
    ie = _make_ie()
    ie.__wrapped__ = Mock()
    ie.__wrapped__._real_extract = Mock(return_value={"id": "fallback"})
    ie._url = "https://example.com/watch"
    ie._extract_network_formats = generic_browser.GenericBrowserIE._extract_network_formats.__get__(
        ie, generic_browser.GenericBrowserIE
    )

    result = ie._extract_network_formats([], "vid", {"title": "title"})

    assert result == {"id": "fallback"}
    ie.write_debug.assert_called_with("No media formats found in 0 browser request(s)")
    ie.report_warning.assert_called_once_with(
        "Generic browser extractor found no media formats. falling back to generic extractor.",
        "vid",
    )


def test_extract_network_formats_playlist_entries_keep_own_urls() -> None:
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


def test_select_driver_selenium(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setattr(generic_browser.SeleniumDriver, "is_available", staticmethod(lambda: True))

    assert ie._select_driver("selenium+http://browser:4444/wd/hub") is generic_browser.SeleniumDriver


def test_select_driver_playwright_ws(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setattr(generic_browser.PlaywrightDriver, "is_available", staticmethod(lambda: True))

    assert ie._select_driver("playwright+ws://playwright:3000/") is generic_browser.PlaywrightDriver


def test_select_driver_playwright_cdp(monkeypatch: pytest.MonkeyPatch) -> None:
    ie = _make_ie()
    monkeypatch.setattr(generic_browser.PlaywrightDriver, "is_available", staticmethod(lambda: True))

    assert ie._select_driver("playwright+cdp://chrome:9222/") is generic_browser.PlaywrightDriver
