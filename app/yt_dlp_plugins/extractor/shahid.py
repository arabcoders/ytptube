from __future__ import annotations

import hashlib
import hmac
import re
import time
import uuid
from typing import Any, override
from urllib.parse import unquote

from yt_dlp.extractor.shahid import ShahidIE as BaseIE
from yt_dlp.utils import (
    ExtractorError,
    clean_html,
    determine_ext,
    int_or_none,
    parse_iso8601,
    traverse_obj,
    url_or_none,
)

CLIENT_HEADERS = {
    "Shd-Platform": "WEB",
    "Shd-App-Name": "Shahid-Web",
    "Shd-OS": "GNU_LINUX",
    "Shd-OS-Version": "-1",
    "Shd-Browser": "CHROME",
    "Shd-Browser-Version": "131.0.0.0",
}
PRIVATE_LANGUAGE = re.compile(r"q[a-t][a-z]", re.IGNORECASE)


class ShahidIE(BaseIE):
    _VALID_URL = (
        r"https?://(?:www\.)?shahid\.mbc\.net/(?P<lang>[a-z]{2})/"
        r"(?:player/(?:episode|clip|movie)s/[^/?#]+/id-|(?:serie|show|movie)s/[^/?#]+/(?:episode|clip|movie)-)"
        r"(?P<id>\d+)"
    )

    @override
    def _perform_login(self, username: str, password: str) -> None:
        msg = "Use exported Shahid cookies instead of username/password authentication"
        raise ExtractorError(msg, expected=True)

    def _playout(self, video_id: str, language: str, country: str, url: str) -> dict[str, Any]:
        query = {
            "download": "false",
            "jailbreak": "false",
            "ts": str(int(time.time() * 1000)),
            "country": country,
            "outputParameter": "",
        }
        values = {**query, **CLIENT_HEADERS}
        message = (
            video_id + ";" + ";".join(f"{key.lower()}={values[key].lower()}" for key in sorted(values, key=str.lower))
        )
        # The public web client signs the query and six device headers with this UTF-8 key.
        signature = hmac.new(
            b"z3qQSk17nbajIYUF0dU5f4+O/CxjFizcsEJr9ejOYFw=", message.encode(), hashlib.sha256
        ).hexdigest()
        headers = {
            **CLIENT_HEADERS,
            "Shd-Screen-Width": "1920",
            "Shd-Screen-Height": "1080",
            "UUID": "web",
            "Authorization": signature,
            "language": language.upper(),
            "Accept-Language": language,
            "Accept": "application/json",
            "Origin": "https://shahid.mbc.net",
            "Referer": url,
        }
        if token := self._get_cookies(url).get("token"):
            headers["token"] = unquote(token.value)
        else:
            headers["X-Anonymous-Id"] = f"web_{uuid.uuid4()}_{query['ts']}"
        response = self._download_json(
            f"https://api3.shahid.net/proxy/v2.1/playout/v2/stream/{video_id}",
            video_id,
            "Downloading playback JSON",
            query=query,
            headers=headers,
            expected_status=(400, 401, 403, 404, 500),
        )
        if response.get("faults") or response.get("success") is False:
            messages = traverse_obj(response, ("faults", ..., "userMessage"), expected_type=str) or []
            msg = "; ".join(filter(None, map(clean_html, messages))) or "Shahid playback request failed"
            raise ExtractorError(msg, expected=True)
        media = traverse_obj(response, ("playout", "media"), expected_type=dict)
        if not media or not url_or_none(media.get("url")):
            msg = "Shahid did not return a playable media URL"
            raise ExtractorError(msg, expected=True)
        return media

    def _real_extract(self, url: str) -> dict[str, Any]:
        match = self._match_valid_url(url)
        video_id, language = match.group("id", "lang")
        webpage = self._download_webpage(url, video_id)
        props = self._search_nextjs_data(webpage, video_id)["props"]["pageProps"]
        country = traverse_obj(props, ("appGrid", "userCountryISO2"), expected_type=str) or traverse_obj(
            props, ("response", "country"), expected_type=str
        )
        if not country:
            msg = "Unable to determine Shahid playback country"
            raise ExtractorError(msg, expected=True)
        media = self._playout(video_id, language, country, url)
        drm = media.get("drmInfo") or {}
        license_url = url_or_none(drm.get("licenseUrl"))
        if media.get("drm") and (str(drm.get("drmScheme", "")).lower() != "widevine" or not license_url):
            msg = "Shahid did not return a Widevine license URL"
            raise ExtractorError(msg, expected=True)

        headers = {"Referer": url, "Origin": "https://shahid.mbc.net"}
        manifest = media["url"]
        hls = determine_ext(manifest) == "m3u8" or media.get("mediaFormat") == "HLS"
        if hls:
            formats, subtitles = self._extract_m3u8_formats_and_subtitles(
                manifest, video_id, ext="mp4", entry_protocol="m3u8_native", m3u8_id="hls", headers=headers
            )
        else:
            formats, subtitles = self._extract_mpd_formats_and_subtitles(
                manifest, video_id, mpd_id="dash", headers=headers
            )
        for fmt in formats:
            fmt["http_headers"] = headers
            if hls and media.get("drm"):
                fmt["has_drm"] = True
            if fmt.get("has_drm") and license_url:
                fmt["drm"] = {"system": "widevine", "license_url": license_url}
        if any(
            fmt.get("vcodec") == "none" and fmt.get("language") and not PRIVATE_LANGUAGE.fullmatch(fmt["language"])
            for fmt in formats
        ):
            formats = [
                fmt
                for fmt in formats
                if fmt.get("vcodec") != "none" or not PRIVATE_LANGUAGE.fullmatch(fmt.get("language") or "")
            ]
        if external := url_or_none(media.get("externalSubtitles")):
            _, subs = self._extract_m3u8_formats_and_subtitles(external, video_id, headers=headers, fatal=False)
            self._merge_subtitles(subs, target=subtitles)
        for tracks in subtitles.values():
            for track in tracks:
                track["http_headers"] = headers

        product = traverse_obj(props, ("response", "productModel"), expected_type=dict) or {}
        show = product.get("show") or {}
        season = show.get("season") or {}
        title = product.get("title") or self._og_search_title(webpage, default=None) or video_id
        return {
            "id": video_id,
            "title": re.sub(r"^Watch .+? - Season .+?\s*/\s*(Episode .+)$", r"\1", title),
            "description": product.get("longDescription")
            or product.get("description")
            or self._og_search_description(webpage, default=None),
            "thumbnail": self._og_search_thumbnail(webpage, default=None),
            "duration": int_or_none(media.get("durationSeconds") or product.get("duration")),
            "timestamp": parse_iso8601(product.get("createdDate")),
            "series": show.get("title"),
            "season": season.get("title"),
            "season_number": int_or_none(season.get("seasonNumber")),
            "season_id": str(season["id"]) if season.get("id") is not None else None,
            "episode_number": int_or_none(product.get("number")),
            "episode_id": video_id if product.get("productSubType") in {"EPISODE", "CLIP"} else None,
            "categories": traverse_obj(product, ("genres", ..., "title"), expected_type=str),
            "formats": formats,
            "subtitles": subtitles,
            "http_headers": headers,
        }
