import base64
import importlib.util
import math
import os
import re
import time
import urllib.parse
from typing import Any

from yt_dlp.extractor.generic import GenericIE
from yt_dlp.utils import ExtractorError, determine_ext, make_archive_id, mimetype2ext, traverse_obj
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

POST_MEDIA_POLL_INTERVAL_MS = 250
POST_MEDIA_POLL_ATTEMPTS = 8
BROWSER_WAIT_SECONDS = 60.0
BROWSER_WAIT_MAX_SECONDS = 300.0
NETWORK_IDLE_SLICE_MS = 500
HARD_HTTP_STATUSES: set[int] = {404, 410, 500, 502, 503, 504}

MEDIA_CANDIDATE_EXTS: list[str] = [
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

MEDIA_ELEMENT_JS: str = """() => {
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
        for ext in MEDIA_CANDIDATE_EXTS:
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
    max_total_timeout: float = BROWSER_WAIT_SECONDS,
    pending_api: set[str] | None = None,
):
    """Shared network-idle waiting logic for all driver sessions."""
    deadline = time.monotonic() + max(0, max_total_timeout)

    def bounded_timeout_ms(requested_ms: int, phase_deadline: float | None = None) -> int:
        end = min(deadline, phase_deadline) if phase_deadline is not None else deadline
        remaining_ms = int((end - time.monotonic()) * 1000)
        return max(0, min(requested_ms, remaining_ms))

    def wait_for_late_media() -> None:
        for _ in range(POST_MEDIA_POLL_ATTEMPTS):
            if _has_possible_media(requests_list):
                return
            if not (timeout_ms := bounded_timeout_ms(POST_MEDIA_POLL_INTERVAL_MS)):
                return
            time.sleep(timeout_ms / 1000)

    if _has_possible_media(requests_list):
        return

    idle_deadline = min(deadline, time.monotonic() + idle_timeout / 1000)
    while timeout_ms := bounded_timeout_ms(NETWORK_IDLE_SLICE_MS, idle_deadline):
        if wait_fn(timeout_ms):
            break
        if _has_possible_media(requests_list):
            return

    for _ in range(api_poll_attempts):
        if _has_possible_media(requests_list):
            return

        if pending_api is not None and len(pending_api) == 0:
            break

        if not (timeout_ms := bounded_timeout_ms(api_poll_interval)):
            return
        wait_fn(timeout_ms)

    if _has_possible_media(requests_list):
        return

    if not (timeout_ms := bounded_timeout_ms(10000)):
        return
    if wait_for_media_fn(timeout_ms):
        return
    wait_for_late_media()


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


class CdpDriver:
    @staticmethod
    def is_available() -> bool:
        return importlib.util.find_spec("playwright.sync_api") is not None

    @staticmethod
    def connect(browser_url: str, timeout: int | None = None):
        if not CdpDriver.is_available():
            msg = "Playwright is not installed"
            raise ImportError(msg)

        parsed = urllib.parse.urlsplit(browser_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.path.rstrip("/").lower().endswith("/wd/hub")
        ):
            msg = "Invalid CDP browser URL. Use an absolute http(s) URL"
            raise ValueError(msg)

        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = None
        context = None
        page = None
        owns_context = False
        try:
            browser = playwright.chromium.connect_over_cdp(browser_url, timeout=timeout or 30000)
            if browser.contexts:
                context = browser.contexts[0]
            else:
                context = browser.new_context()
                owns_context = True
            page = context.new_page()
        except Exception:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            if owns_context and context is not None:
                try:
                    context.close()
                except Exception:
                    pass
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            try:
                playwright.stop()
            except Exception:
                pass
            raise

        requests_list: list[dict] = []
        pending_api: set[str] = set()
        last_response = None

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
            closed = False

            def goto(
                self,
                target_url: str,
                *,
                method: str = "GET",
                headers: dict[str, str] | None = None,
                data: str | bytes | None = None,
                timeout: int | None = None,
            ) -> int | None:
                nonlocal last_response

                if headers:
                    page.set_extra_http_headers(headers)

                route_handler = None
                method = method.upper()
                if method != "GET" or data is not None:
                    main_request_seen = False

                    def route_handler(route, request):
                        nonlocal main_request_seen
                        if main_request_seen or not request.is_navigation_request() or request.frame != page.main_frame:
                            route.continue_()
                            return

                        main_request_seen = True
                        options: dict[str, Any] = {}
                        if method != "GET":
                            options["method"] = method
                        if data is not None:
                            options["post_data"] = data
                        route.continue_(**options)

                    page.route("**/*", route_handler)

                try:
                    last_response = page.goto(target_url, wait_until="domcontentloaded", timeout=timeout)
                finally:
                    if route_handler is not None:
                        page.unroute("**/*", route_handler)
                return last_response.status if last_response else None

            def response_text(self) -> str | None:
                return last_response.text() if last_response else None

            def wait_for_selector(self, selector_type: str, expression: str, timeout: float) -> None:
                selector = f"xpath={expression}" if selector_type == "xpath" else expression
                page.wait_for_selector(selector, timeout=timeout * 1000)

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
                        return True
                    except Exception:
                        return False

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
                        return True
                    except Exception:
                        return False

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

            def get_page(self):
                return page

            def get_requests(self) -> list[dict]:
                return list(requests_list)

            def get_media_requests(self) -> list[dict]:
                return _build_media_requests(requests_list, page.evaluate(MEDIA_ELEMENT_JS))

            def close(self):
                if self.closed:
                    return
                self.closed = True

                try:
                    page.close()
                finally:
                    try:
                        if owns_context:
                            context.close()
                    finally:
                        try:
                            browser.close()
                        finally:
                            playwright.stop()

        return Session()


class GenericBrowserIE(GenericIE, plugin_name="browser"):
    _WORKING = True
    _failed: bool = False
    _remote_browser_failures: dict[str, str] = {}
    _url: str = ""
    __wrapped__: Any

    def _fallback_extract(self, url: str) -> dict[str, Any]:
        return self.__wrapped__._real_extract(self, url)

    def _get_config(self, name: str, env_name: str) -> str | None:
        value = self._configuration_arg(name, [None])[0]
        if value is None:
            value = os.environ.get(env_name)

        if isinstance(value, str):
            value = value.strip() or None

        return value

    def _get_wait(self) -> float:
        value = self._configuration_arg("wait", [None])[0]
        if value is None:
            return BROWSER_WAIT_SECONDS

        try:
            wait = float(value)
        except (TypeError, ValueError) as e:
            msg = f"Invalid browser wait value {value!r}; expected seconds between 0 and {BROWSER_WAIT_MAX_SECONDS:g}"
            raise ExtractorError(msg, expected=True) from e

        if not math.isfinite(wait) or not 0 <= wait <= BROWSER_WAIT_MAX_SECONDS:
            msg = f"Invalid browser wait value {value!r}; expected seconds between 0 and {BROWSER_WAIT_MAX_SECONDS:g}"
            raise ExtractorError(msg, expected=True)
        return wait

    def _safe_url(self, browser_url: str) -> str:
        try:
            parsed = urllib.parse.urlsplit(browser_url)
        except Exception:
            return browser_url

        netloc = parsed.netloc
        if parsed.username or parsed.password:
            host = parsed.hostname or ""
            if parsed.port:
                host = f"{host}:{parsed.port}"
            netloc = f"***:***@{host}" if host else "***:***"

        query = "***" if parsed.query else ""
        fragment = "***" if parsed.fragment else ""
        return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, query, fragment))

    def _real_extract(self, url: str) -> dict[str, Any]:
        self._url = url

        if not (browser_url := self._get_config("url", "YTP_BROWSER_URL")) or self._failed:
            return self._fallback_extract(url)

        video_id: str = self._generic_id(url)
        if urllib.parse.urlsplit(browser_url).scheme.lower() not in {"http", "https"}:
            self.report_warning("Browser URL must use http or https; falling back to generic extractor.", video_id)
            return self._fallback_extract(url)

        safe_url = self._safe_url(browser_url)
        wait = self._get_wait()

        timeout: int | None = self._get_timeout_ms()
        self.to_screen(f"Using remote browser for {url}")

        if not (driver := self._select_driver(browser_url)):
            msg: str = (
                "No matching browser driver available for the configured browser URL. "
                "Install playwright to use the configured browser."
            )
            raise ExtractorError(msg)

        self.write_debug(f"Selected driver {driver.__name__} for {safe_url}")

        try:
            session = driver.connect(browser_url, timeout)
        except Exception as e:
            message = str(e)
            self._failed = True
            self.report_warning(f"Remote browser unavailable: {message}, marking as failed.", video_id)
            return self._fallback_extract(url)

        fallback_status: int | None = None
        try:
            self.report_extraction(url)
            self.write_debug(f"Loading page {url}")
            status = session.goto(url)
            fallback_status = status if isinstance(status, int) else None

            if fallback_status not in HARD_HTTP_STATUSES:
                session.wait_for_network_idle(
                    api_poll_attempts=10,
                    api_poll_interval=500,
                    max_total_timeout=wait,
                )

            webpage = session.content()
            requests = self._merge_requests(session.get_requests(), session.get_media_requests())
            self.write_debug(f"Captured {len(requests)} network requests")

            downloader = self._downloader
            if downloader and downloader.params.get("dump_intermediate_pages"):
                self.to_screen(f"Browser content dump for: {url}")
                self.to_screen(base64.b64encode(webpage.encode("utf-8")).decode("ascii"))

            if downloader and downloader.params.get("write_pages"):
                filename = _request_dump_filename(url, video_id, None, downloader.params.get("trim_file_name"))
                self.to_screen(f"Saving request to {filename}")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(webpage)

            if downloader and downloader.params.get("debug_printtraffic"):
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
                info_dict["title"] = self._generic_title(url, webpage)
                info_dict["description"] = self._og_search_description(webpage, default=None) or self._html_search_meta(
                    "description", webpage, default=None
                )
                thumbnail = self._og_search_thumbnail(webpage, default=None)
                if thumbnail:
                    info_dict["thumbnail"] = thumbnail
            elif webpage:
                self.write_debug(f"Page content did not look like HTML for {url}")
                self.write_debug(webpage)

            network_info = self._extract_network_formats(requests, video_id, info_dict)
            if network_info:
                self.write_debug(f"Resolved media from browser requests for {url}")
                if network_info.get("_type") == "playlist" and network_info.get("entries"):
                    return self.playlist_result(network_info["entries"], **info_dict)
                info_dict.update(network_info)
                return info_dict

            fallback_status = fallback_status or next(
                (
                    status
                    for req in reversed(requests)
                    if req.get("resourceType") == "document"
                    and isinstance(status := req.get("response", {}).get("status"), int)
                ),
                None,
            )
        except Exception as e:
            self.report_warning(
                f"Browser extractor session failed for url={url!r} browser_url={safe_url!r} "
                f"driver={driver.__name__} error={e!s}",
                video_id,
            )
            raise
        finally:
            try:
                session.close()
            except Exception as e:
                self.report_warning(
                    f"Browser session close failed for url={url!r} browser_url={safe_url!r} "
                    f"driver={driver.__name__} error={e!s}",
                    video_id,
                )

        if fallback_status is not None and not (200 <= fallback_status <= 301 or fallback_status in {400, 401}):
            msg = f"Remote browser returned HTTP Error {fallback_status}"
            raise ExtractorError(msg, expected=True)

        self.report_warning(
            "Generic browser extractor found no media formats; falling back to generic extractor.", video_id
        )
        return self._fallback_extract(url)

    def _select_driver(self, browser_url: str):
        parsed = urllib.parse.urlsplit(browser_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.path.rstrip("/").lower().endswith("/wd/hub")
        ):
            msg = "Invalid browser URL. Use an absolute http(s) URL"
            raise ExtractorError(msg)
        return CdpDriver if CdpDriver.is_available() else None

    def _extract_network_formats(
        self, requests: list[dict], video_id: str, base_info: dict[str, Any]
    ) -> dict[str, Any] | None:
        candidates = self._pick_network_candidates(requests)
        formats: list[dict[str, Any]] = []
        direct_formats: list[dict[str, Any]] = []
        subtitles: dict[str, Any] = {}
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
            self.write_debug(f"No media formats found in {len(requests)} browser request(s)")
            return None

        if not has_manifest_formats and len(direct_formats) > 1:
            base_title = (base_info.get("title") or "").strip() or video_id
            entries = []
            for index, fmt in enumerate(direct_formats, start=1):
                entry_url = fmt.get("url")
                entry_id = f"{video_id}-{index}"
                entries.append(
                    {
                        "id": entry_id,
                        "title": f"{base_title} ({index})",
                        "_old_archive_ids": [make_archive_id("generic", entry_id)],
                        "formats": [fmt],
                        "url": entry_url,
                        "webpage_url": entry_url,
                        "original_url": entry_url,
                        "ext": fmt.get("ext"),
                        "protocol": fmt.get("protocol"),
                        "direct": True,
                    }
                )
            return {"_type": "playlist", "entries": entries}

        result: dict[str, Any] = {"formats": formats, "direct": True}
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
            if (
                resource_type
                and resource_type.lower() not in MEDIA_RESOURCE_TYPES
                and not has_media_ext
                and not has_media_header_ext
            ):
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

    def _get_timeout_ms(self) -> int | None:
        downloader = self._downloader
        socket_timeout = downloader.params.get("socket_timeout") if downloader else None
        if isinstance(socket_timeout, (int, float)) and socket_timeout > 0:
            return int(socket_timeout * 1000)
        return None
