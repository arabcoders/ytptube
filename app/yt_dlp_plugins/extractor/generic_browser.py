import base64
import re
import time
import urllib.parse
from typing import Any

from yt_dlp.extractor.generic import GenericIE
from yt_dlp.utils import ExtractorError, determine_ext, mimetype2ext, traverse_obj
from yt_dlp.utils._utils import _request_dump_filename

MEDIA_EXTENSIONS: set[str] = {
    "mp4",
    "m4p",
    "m4v",
    "mov",
    "avi",
    "wmv",
    "flv",
    "webm",
    "mkv",
    "mka",
    "ogv",
    "ogg",
    "mp3",
    "m4a",
    "aac",
    "flac",
    "opus",
    "wav",
    "ape",
    "alac",
    "m3u8",
    "m3u",
    "mpd",
    "f4m",
    "ism",
    "xspf",
    "smil",
}

AUDIO_EXTENSIONS: set[str] = {
    "aac",
    "flac",
    "m4a",
    "mp3",
    "ogg",
    "opus",
    "wav",
    "ape",
    "alac",
}

MEDIA_RESOURCE_TYPES: set[str] = {"media", "video", "audio", "manifest"}

REQUEST_RESOURCE_TYPES: set[str] = {
    "media",
    "video",
    "audio",
    "fetch",
    "xhr",
    "document",
    "manifest",
}

API_RESOURCE_TYPES: set[str] = {"fetch", "xhr"}

_MEDIA_CANDIDATE_EXTS = [
    "m3u8",
    "mpd",
    "mp4",
    "webm",
    "mkv",
    "avi",
    "mov",
    "mp3",
    "m4a",
    "ogg",
]

_MEDIA_ELEMENT_JS = """() => {
    const mediaUrls = [];
    const seen = new Set();
    const addUrl = (url, type) => {
        if (url && !seen.has(url) && !url.startsWith('blob:') && !url.startsWith('data:')) {
            seen.add(url);
            mediaUrls.push({url: url, resourceType: type});
        }
    };
    document.querySelectorAll('video').forEach(v => {
        addUrl(v.src, 'video');
        v.querySelectorAll('source').forEach(s => addUrl(s.src, 'video'));
    });
    document.querySelectorAll('audio').forEach(a => {
        addUrl(a.src, 'audio');
        a.querySelectorAll('source').forEach(s => addUrl(s.src, 'audio'));
    });
    return mediaUrls;
}"""


def _has_possible_media(requests_list: list[dict]) -> bool:
    for req in requests_list:
        url_lower = req.get("url", "").lower()
        for ext in _MEDIA_CANDIDATE_EXTS:
            if f".{ext}" in url_lower or f".{ext}?" in url_lower:
                return True
        ct = (req.get("response", {}).get("headers", {}).get("content-type", "")).lower()
        if any(x in ct for x in ["video", "audio", "mpegurl", "dash+xml"]):
            return True
    return False


def _wait_for_network_idle(
    requests_list: list[dict],
    wait_fn,
    wait_for_media_fn,
    idle_timeout: int = 30000,
    api_poll_interval: int = 500,
    api_poll_attempts: int = 10,
    max_total_timeout: int = 60,
    pending_api: set[str] | None = None,
):
    """Shared network-idle waiting logic for all driver sessions."""
    deadline = time.monotonic() + max_total_timeout

    def bounded_timeout_ms(requested_ms: int) -> int:
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            msg: str = f"Browser wait timed out after {max_total_timeout}s"
            raise Exception(msg)
        return max(1, min(requested_ms, remaining_ms))

    wait_fn(bounded_timeout_ms(idle_timeout))

    for _ in range(api_poll_attempts):
        if _has_possible_media(requests_list):
            return

        if pending_api is not None and len(pending_api) == 0:
            break

        time.sleep(bounded_timeout_ms(api_poll_interval) / 1000)

    if _has_possible_media(requests_list):
        return

    wait_for_media_fn(bounded_timeout_ms(10000))


def _build_media_requests(requests_list: list[dict], media_elements: list[dict]) -> list[dict]:
    result = []
    for media in media_elements:
        existing = next((r for r in requests_list if r.get("url") == media["url"]), None)
        result.append(
            existing
            or {
                "url": media["url"],
                "method": "GET",
                "resourceType": media["resourceType"],
            }
        )
    return result


class RemoteBrowserUnavailableError(ExtractorError):
    pass


class PlaywrightDriver:
    @staticmethod
    def is_available() -> bool:
        try:
            import playwright.sync_api  # noqa: F401

            return True
        except ImportError:
            return False

    @staticmethod
    def connect(ws_url: str, timeout: int | None = None):
        if not PlaywrightDriver.is_available():
            msg = "Playwright is not installed"
            raise ImportError(msg)

        from playwright.sync_api import sync_playwright

        p = sync_playwright().start()

        if ws_url.startswith("pw+"):
            browser = p.chromium.connect(ws_url[3:], timeout=timeout or 30000)
        else:
            browser = p.chromium.connect_over_cdp(ws_url, timeout=timeout or 30000)

        context = browser.new_context()
        page = context.new_page()

        requests_list: list[dict] = []
        pending_api: set[str] = set()

        def on_request(request):
            resource_type = request.resource_type
            if resource_type not in REQUEST_RESOURCE_TYPES:
                return
            url_str = request.url
            if resource_type in API_RESOURCE_TYPES:
                pending_api.add(url_str)
            requests_list.append(
                {
                    "url": url_str,
                    "method": request.method,
                    "resourceType": resource_type,
                    "headers": dict(request.headers),
                }
            )

        def on_response(response):
            request = response.request
            if request.resource_type not in REQUEST_RESOURCE_TYPES:
                return
            url_str = response.url
            pending_api.discard(url_str)
            existing = next(
                (r for r in requests_list if r.get("url") == url_str and not r.get("response")),
                None,
            )
            payload = {"status": response.status, "headers": dict(response.headers)}
            if existing:
                existing["response"] = payload
            else:
                requests_list.append(
                    {
                        "url": url_str,
                        "method": request.method,
                        "resourceType": request.resource_type,
                        "headers": dict(request.headers),
                        "response": payload,
                    }
                )

        page.on("request", on_request)
        page.on("response", on_response)

        class Session:
            def goto(self, target_url: str):
                page.goto(target_url, wait_until="domcontentloaded")

            def wait_for_network_idle(
                self,
                idle_timeout=30000,
                api_poll_interval=500,
                api_poll_attempts=10,
                max_total_timeout=60,
            ):
                def wait_fn(timeout_ms):
                    try:
                        page.wait_for_load_state("networkidle", timeout=timeout_ms)
                    except Exception:
                        pass

                def wait_for_media_fn(timeout_ms):
                    try:
                        page.wait_for_function(
                            """() => {
                                const videos = document.querySelectorAll('video[src], video > source[src]');
                                const audios = document.querySelectorAll('audio[src], audio > source[src]');
                                return videos.length > 0 || audios.length > 0;
                            }""",
                            timeout=timeout_ms,
                        )
                    except Exception:
                        pass

                _wait_for_network_idle(
                    requests_list,
                    wait_fn,
                    wait_for_media_fn,
                    idle_timeout,
                    api_poll_interval,
                    api_poll_attempts,
                    max_total_timeout,
                    pending_api,
                )

            def content(self) -> str:
                return page.content()

            def get_requests(self) -> list[dict]:
                return list(requests_list)

            def get_media_requests(self) -> list[dict]:
                return _build_media_requests(requests_list, page.evaluate(_MEDIA_ELEMENT_JS))

            def close(self):
                context.close()
                browser.close()
                p.stop()

        return Session()


class SeleniumDriver:
    @staticmethod
    def is_available() -> bool:
        try:
            import selenium.webdriver  # noqa: F401

            return True
        except ImportError:
            return False

    @staticmethod
    def connect(ws_url: str, timeout: int | None = None):  # noqa: ARG004
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        driver = webdriver.Remote(command_executor=ws_url, options=Options())
        requests_list: list[dict] = []

        def capture_requests():
            try:
                urls = driver.execute_script("return performance.getEntriesByType('resource').map(e => e.name);")
                for u in urls:
                    if any(r.get("url") == u for r in requests_list):
                        continue
                    ext = determine_ext(u, default_ext="")
                    resource_type = (
                        "manifest"
                        if ext in ("m3u8", "mpd", "f4m", "ism")
                        else "video"
                        if ext in ("mp4", "webm", "mkv", "avi", "mov")
                        else "audio"
                        if ext in ("mp3", "m4a", "ogg", "wav", "flac")
                        else None
                    )
                    if resource_type:
                        requests_list.append({"url": u, "method": "GET", "resourceType": resource_type})
            except Exception:
                pass

        class Session:
            def goto(self, target_url: str):
                driver.get(target_url)

            def wait_for_network_idle(
                self,
                idle_timeout=30000,
                api_poll_interval=500,
                api_poll_attempts=10,
                max_total_timeout=60,
            ):
                def wait_fn(timeout_ms):
                    time.sleep(min(2, timeout_ms / 1000))

                def wait_for_media_fn(timeout_ms):
                    try:
                        WebDriverWait(driver, max(0.001, timeout_ms / 1000)).until(
                            lambda d: (
                                d.find_elements(By.TAG_NAME, "video")
                                or d.find_elements(By.TAG_NAME, "source")
                                or d.find_elements(By.TAG_NAME, "audio")
                            )
                        )
                        capture_requests()
                    except Exception:
                        pass

                # Wrap capture_requests into each poll iteration via a custom pending_api proxy
                class _PendingProxy(set):
                    def __len__(self):
                        capture_requests()
                        return 0  # always signal "no pending" so we rely on media check

                _wait_for_network_idle(
                    requests_list,
                    wait_fn,
                    wait_for_media_fn,
                    idle_timeout,
                    api_poll_interval,
                    api_poll_attempts,
                    max_total_timeout,
                    _PendingProxy(),
                )

            def content(self) -> str:
                return driver.page_source

            def get_requests(self) -> list[dict]:
                return list(requests_list)

            def get_media_requests(self) -> list[dict]:
                try:
                    return _build_media_requests(requests_list, driver.execute_script(_MEDIA_ELEMENT_JS))
                except Exception:
                    return []

            def close(self):
                driver.quit()

        return Session()


DRIVERS: list[type] = [PlaywrightDriver, SeleniumDriver]


class GenericBrowserIE(GenericIE, plugin_name="browser"):
    _WORKING = True
    _failed: bool = False
    _remote_browser_failures: dict[str, str] = {}
    _url: str = ""

    def _real_extract(self, url: str) -> dict[str, Any]:
        self._url = url
        preferred_driver: str | None = self._configuration_arg("driver", [None])[0]

        if not (remote_browser := self._configuration_arg("remote_browser", [None])[0]) or self._failed:
            return self.__wrapped__._real_extract(self, url)

        video_id: str = self._generic_id(url)
        timeout: int | None = self._get_timeout_ms()

        if not (driver := self._select_driver(preferred_driver, remote_browser)):
            available: list[str] = [d.__name__ for d in DRIVERS if d.isAvailable()]
            msg: str = (
                f"No browser driver available. Install playwright or selenium. "
                f"Available drivers: {available if available else 'none'}"
            )
            raise ExtractorError(msg)

        try:
            session = driver.connect(remote_browser, timeout)
        except Exception as e:
            message = str(e)
            self._failed = True
            self.report_warning(f"Remote browser unavailable: {message}, marking as failed.", video_id)
            return self.__wrapped__._real_extract(self, url)

        try:
            self.report_extraction(url)
            session.goto(url)

            session.wait_for_network_idle(
                api_poll_attempts=10,
                api_poll_interval=500,
                max_total_timeout=60,
            )

            webpage = session.content()
            requests = self._merge_requests(session.get_requests(), session.get_media_requests())

            if self._downloader.params.get("dump_intermediate_pages"):
                self.to_screen(f"Browser content dump for: {url}")
                self.to_screen(base64.b64encode(webpage.encode("utf-8")).decode("ascii"))

            if self._downloader.params.get("write_pages"):
                filename = _request_dump_filename(url, video_id, None, self._downloader.params.get("trim_file_name"))
                self.to_screen(f"Saving request to {filename}")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(webpage)

            if self._downloader.params.get("debug_printtraffic"):
                self.to_screen(f"[browser] {url}")
                self.to_screen(f"[browser] Captured '{len(requests)}' network requests")
                for req in requests:
                    self.to_screen(f"[browser] {req.get('method', 'GET')} {req.get('url', '')}")
                    if req.get("response", {}).get("status"):
                        self.to_screen(f"[browser] Status: {req['response']['status']}")
                    for key, value in req.get("response", {}).get("headers", {}).items():
                        self.to_screen(f"[browser] {key}: {value}")

            info_dict = {
                "id": video_id,
                "title": self._generic_title(url),
                "webpage_url": url,
                "original_url": url,
                "_type": "video",
            }

            if webpage and self._looks_like_html(webpage):
                info_dict["title"] = self._get_title(webpage) or self._generic_title(url, webpage)
                info_dict["description"] = self._get_desc(webpage)
                thumbnail = self._og_search_thumbnail(webpage, default=None)
                if thumbnail:
                    info_dict["thumbnail"] = thumbnail

            network_info = self._extract_network_formats(requests, video_id, info_dict)
            if network_info:
                if network_info.get("_type") == "playlist" and network_info.get("entries"):
                    return self.playlist_result(network_info["entries"], **info_dict)
                info_dict.update(network_info)

            return info_dict
        finally:
            session.close()

    def _select_driver(self, preferred: str | None, ws_url: str):
        if preferred:
            for driver in DRIVERS:
                if driver.__name__.lower().startswith(preferred.lower()):
                    if driver.isAvailable():
                        return driver

                    self.report_warning(f"Preferred driver {driver.__name__} not available")
                    return None

        if ws_url.startswith("pw+") and PlaywrightDriver.is_available():
            return PlaywrightDriver

        for driver in DRIVERS:
            if driver.isAvailable():
                return driver

        return None

    def _extract_network_formats(
        self, requests: list[dict], video_id: str, base_info: dict[str, Any]
    ) -> dict[str, Any] | None:
        candidates = self._pick_network_candidates(requests)
        formats = []
        direct_formats = []
        subtitles = {}
        source_counts = {}
        has_manifest_formats = False

        manifest_extractors = {
            "m3u8": lambda url, hdrs: self._extract_m3u8_formats(
                url,
                video_id,
                ext="mp4",
                entry_protocol="m3u8_native",
                m3u8_id="hls",
                headers=hdrs,
                fatal=False,
            ),
            "mpd": lambda url, hdrs: self._extract_mpd_formats(url, video_id, headers=hdrs, fatal=False),
            "f4m": lambda url, hdrs: self._extract_f4m_formats(url, video_id, headers=hdrs, fatal=False),
            "ism": lambda url, hdrs: self._extract_ism_formats(url, video_id, headers=hdrs, fatal=False),
        }
        manifest_keys: dict[str, str] = {
            "m3u8": "hls",
            "mpd": "mpd",
            "f4m": "f4m",
            "ism": "ism",
        }

        for candidate in candidates:
            ext = (
                determine_ext(candidate.get("url"), default_ext="")
                or self._ext_from_headers(candidate)
                or candidate.get("_fallbackExt")
            )
            if not ext:
                continue

            request_headers = self._sanitize_network_headers(candidate.get("headers", {}))
            url = candidate["url"]

            is_ism = ext == "ism" or ".ism/manifest" in url.lower()
            effective_ext = "ism" if is_ism else ext

            if effective_ext in manifest_extractors:
                try:
                    extracted = manifest_extractors[effective_ext](url, request_headers)
                    formats.extend(extracted)
                    if extracted:
                        has_manifest_formats = True
                    key = manifest_keys[effective_ext]
                    if extracted:
                        source_counts[key] = source_counts.get(key, 0) + len(extracted)
                except Exception:
                    pass
                continue

            if ext in MEDIA_EXTENSIONS:
                fmt = {
                    "format_id": ext,
                    "url": url,
                    "ext": "mp4" if ext == "m3u8" else ext,
                    "protocol": self._url_protocol(url),
                }
                if ext in AUDIO_EXTENSIONS:
                    fmt["vcodec"] = "none"
                if request_headers:
                    fmt["http_headers"] = request_headers
                formats.append(fmt)
                direct_formats.append(fmt)
                source_counts["direct"] = source_counts.get("direct", 0) + 1

        if not formats:
            self.report_warning(
                "Generic browser extractor found no media formats. falling back to generic extractor.", video_id
            )
            return self.__wrapped__._real_extract(self, self._url)

        if not has_manifest_formats and len(direct_formats) > 1:
            base_title = (base_info.get("title") or "").strip() or video_id
            entries = []
            for index, fmt in enumerate(direct_formats, start=1):
                entries.append(
                    {
                        "id": f"{video_id}-{index}",
                        "title": f"{base_title} ({index})",
                        "formats": [fmt],
                        "url": fmt.get("url"),
                        "ext": fmt.get("ext"),
                        "protocol": fmt.get("protocol"),
                    }
                )
            return {"_type": "playlist", "entries": entries}

        result = {"formats": formats, "direct": True}
        if subtitles:
            result["subtitles"] = subtitles
        if formats and formats[0].get("url"):
            result["url"] = formats[0]["url"]
            result["ext"] = formats[0].get("ext")
            result["protocol"] = formats[0].get("protocol")

        return result

    def _sanitize_network_headers(self, headers: dict[str, str]) -> dict[str, str] | None:
        if not headers:
            return None
        cleaned = {
            k: v
            for k, v in headers.items()
            if not k.lower().startswith(":") and not (k.lower() == "cookie" and len(v) > 2000)
        }
        return cleaned if cleaned else None

    def _pick_network_candidates(self, requests: list[dict]) -> list[dict]:
        out = []
        for entry in requests:
            if entry.get("method", "GET").upper() != "GET":
                continue
            url = entry.get("url")
            if not url or url.startswith(("blob:", "data:")):
                continue

            ext = determine_ext(url, default_ext="")
            header_ext = self._ext_from_headers(entry)
            has_media_ext = ext and ext in MEDIA_EXTENSIONS
            has_media_header_ext = header_ext and header_ext in MEDIA_EXTENSIONS

            resource_type = entry.get("resourceType")
            if resource_type and resource_type.lower() not in MEDIA_RESOURCE_TYPES:  # noqa: SIM102
                if not has_media_ext and not has_media_header_ext:
                    continue

            if not ext and not header_ext:
                rt = (resource_type or "").lower()
                if rt in ("video", "media"):
                    entry["_fallbackExt"] = "mp4"
                elif rt == "audio":
                    entry["_fallbackExt"] = "mp3"
                else:
                    continue

            out.append(entry)
        return out

    def _ext_from_headers(self, entry: dict) -> str | None:
        headers = traverse_obj(entry, ("response", "headers")) or {}
        content_type = headers.get("content-type") or headers.get("Content-Type")
        return mimetype2ext(content_type) if content_type else None

    def _merge_requests(self, network: list[dict], media: list[dict]) -> list[dict]:
        merged = list(network)
        seen = {r.get("url") for r in network if r.get("url")}
        for m in media:
            if m.get("url") and m["url"] not in seen:
                merged.append(m)
                seen.add(m["url"])
        return merged

    def _url_protocol(self, url: str) -> str:
        try:
            return urllib.parse.urlparse(url).scheme or "http"
        except Exception:
            return "http"

    def _looks_like_html(self, content: str) -> bool:
        return bool(
            re.search(
                r"<(?:!doctype\s+html|html|head|body|meta|title|script|video|iframe|link)\b",
                content[:1024],
                re.IGNORECASE,
            )
        )

    def _get_title(self, webpage: str) -> str | None:
        return self._extract_from_html(
            webpage,
            [
                r"<title>([^<]+)</title>",
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+name=["\']title["\'][^>]+content=["\']([^"\']+)["\']',
                r"<h1[^>]*>([^<]+)</h1>",
            ],
        )

    def _get_desc(self, webpage: str) -> str | None:
        return self._extract_from_html(
            webpage,
            [
                r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
                r'<p[^>]*class=["\']description["\'][^>]*>([^<]+)</p>',
            ],
        )

    def _extract_from_html(self, webpage: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, webpage, re.IGNORECASE)
            if match and match.group(1):
                return match.group(1).strip()
        return None

    def _get_timeout_ms(self) -> int | None:
        socket_timeout = self._downloader.params.get("socket_timeout")
        if isinstance(socket_timeout, (int, float)) and socket_timeout > 0:
            return int(socket_timeout * 1000)
        return None
