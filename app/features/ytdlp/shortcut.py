from __future__ import annotations

import http.cookiejar
import re
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request

from yt_dlp.cookies import LenientSimpleCookie

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
RESPONSE_HEADERS = {"content-type", "content-length", "content-range", "accept-ranges", "etag", "last-modified"}
FORBIDDEN_REQUEST_HEADERS = HOP_BY_HOP | {"host", "range"}


def direct_url(item: Any) -> bool:
    if not isinstance(item, dict) or not isinstance(item.get("url"), str):
        return False
    parsed = urlparse(item["url"])
    return (
        parsed.scheme.lower() in {"http", "https"}
        and parsed.hostname is not None
        and not parsed.username
        and not parsed.password
        and not parsed.path.lower().endswith((".m3u8", ".mpd"))
        and not item.get("fragments")
        and str(item.get("protocol", "")).lower() not in {"m3u8", "m3u8_native", "http_dash_segments", "dash"}
    )


def selected_format(info: dict[str, Any]) -> dict[str, Any]:
    if any(
        isinstance(info.get(key), list) and len(info[key]) > 1 for key in ("requested_formats", "requested_downloads")
    ):
        message = "Multiple selected formats are not supported."
        raise ValueError(message)
    if not direct_url(info):
        message = "No directly downloadable format was selected."
        raise ValueError(message)
    return info


def safe_filename(info: dict[str, Any], fmt: dict[str, Any]) -> str:
    title = _SAFE_NAME.sub("_", str(info.get("title") or "download")).strip("._") or "download"
    ext = re.sub(r"[^a-z0-9]+", "", str(fmt.get("ext") or info.get("ext") or "bin").lower())[:12] or "bin"
    return f"{title[:160]}.{ext}"


def media_type(fmt: dict[str, Any]) -> str:
    video = fmt.get("vcodec") not in {None, "none"}
    audio = fmt.get("acodec") not in {None, "none"}
    return "video+audio" if video and audio else "video" if video else "audio" if audio else "unknown"


def _headers(*sources: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if (
                not isinstance(key, str)
                or not isinstance(value, str)
                or "\r" in key
                or "\n" in key
                or "\r" in value
                or "\n" in value
            ):
                continue
            if key.lower() not in HOP_BY_HOP:
                existing = next((name for name in result if name.lower() == key.lower()), None)
                if existing is not None:
                    result.pop(existing)
                result[key] = value
    return result


def _cookie_header(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        cookies = LenientSimpleCookie(value)
        pairs = [(cookie.key, cookie.value) for cookie in cookies.values()]
    elif isinstance(value, dict):
        pairs = [(key, item) for key, item in value.items() if isinstance(key, str) and isinstance(item, str)]
    elif isinstance(value, list):
        pairs = [
            (item["name"], item["value"])
            for item in value
            if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("value"), str)
        ]
    else:
        return None
    if any("\r" in key or "\n" in key or "\r" in item or "\n" in item for key, item in pairs):
        return None
    result = "; ".join(f"{key}={item}" for key, item in pairs)
    return result or None


def cookie_file_header(path: Any, url: str) -> str | None:
    if not isinstance(path, str) or not path:
        return None
    jar = http.cookiejar.MozillaCookieJar(path)
    try:
        jar.load(ignore_discard=True, ignore_expires=False)
    except (OSError, ValueError):
        return None
    request = Request(url)  # noqa: S310
    jar.add_cookie_header(request)
    return request.get_header("Cookie")


def extracted_headers(fmt: dict[str, Any], info: dict[str, Any], opts: dict[str, Any]) -> dict[str, str]:
    result = _headers(opts.get("http_headers"), info.get("http_headers"), fmt.get("http_headers"))
    format_headers = fmt.get("http_headers")
    explicit_cookie = (
        next((value for key, value in format_headers.items() if key.lower() == "cookie"), None)
        if isinstance(format_headers, dict)
        else None
    )
    cookie = (
        _cookie_header(explicit_cookie)
        or _cookie_header(fmt.get("h_cookies"))
        or _cookie_header(fmt.get("cookies"))
        or _cookie_header(info.get("h_cookies"))
        or _cookie_header(info.get("cookies"))
    )
    if cookie is None:
        cookie = _cookie_header(cookie_file_header(opts.get("cookiefile"), str(fmt["url"])))
    if cookie:
        existing = next((name for name in result if name.lower() == "cookie"), None)
        if existing is not None:
            result.pop(existing)
        result["Cookie"] = cookie
    return result
