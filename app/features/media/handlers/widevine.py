from __future__ import annotations

import base64
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, unquote, urljoin, urlsplit

import httpx
from defusedxml import ElementTree
from yt_dlp.downloader import get_suitable_downloader
from yt_dlp.downloader.dash import DashSegmentsFD
from yt_dlp.downloader.hls import HlsFD
from yt_dlp.networking import Request
from yt_dlp.utils import DownloadError, parse_m3u8_attributes

from app.features.media.types import Handler
from app.library.logging import get_logger
from app.library.Utils import resolve_secret, validate_url

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from yt_dlp import YoutubeDL

LOG = get_logger()
WIDEVINE_SYSTEM_ID = "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"
HEX_KEY = re.compile(r"[0-9a-fA-F]{32}\Z")
HLS_PROTOCOLS = {"m3u8", "m3u8_native"}


class Widevine(Handler):
    name = "widevine"

    def __init__(self, downloader: YoutubeDL, settings: dict[str, Any], options: dict[str, str], path: Path) -> None:
        super().__init__(downloader, settings, options, path)
        self.config = validate_config(settings, options, path)
        self.keys: list[tuple[str, str]] | None = None
        self.ids: set[str] = set()
        self.playlists: dict[str, dict[str, Any]] = {}
        downloader.params["allow_unplayable_formats"] = True

    @contextmanager
    def process(self, info: dict[str, Any]) -> Generator[None]:
        params = self.downloader.params
        allowed = params.get("allow_unplayable_formats")
        native = params.get("hls_prefer_native")
        had_native = "hls_prefer_native" in params
        try:
            sources = info.get("requested_formats") or [info]
            selected = [source for source in sources if encrypted(source)]
            if selected and not (params.get("simulate") or params.get("skip_download")):
                if (
                    info.get("is_live")
                    or params.get("test")
                    or info.get("section_start") is not None
                    or info.get("section_end") is not None
                    or self.downloader.prepare_filename(info) == "-"
                ):
                    msg = "Widevine decryption requires complete on-demand downloads to a file"
                    raise DownloadError(msg)

                has_hls = any(source.get("protocol") in HLS_PROTOCOLS for source in selected)
                options = {**params, "hls_prefer_native": True} if has_hls else params
                for source in selected:
                    protocol = source.get("protocol")
                    hls = protocol in HLS_PROTOCOLS
                    if (
                        protocol not in {"http_dash_segments", *HLS_PROTOCOLS}
                        or source.get("is_live")
                        or source.get("ext") not in {"mp4", "m4a"}
                        or get_suitable_downloader(source.copy(), options) is not (HlsFD if hls else DashSegmentsFD)
                        or (hls and native is False)
                        or (
                            hls
                            and get_suitable_downloader(source.copy(), options, None, protocol="m3u8_frag_urls")
                            is not None
                        )
                    ):
                        msg = "Widevine decryption requires native DASH or fragmented MP4 HLS downloads"
                        raise DownloadError(msg)

                pssh, license_url, self.playlists = metadata(self.downloader, info, self.config, self.options)
                self.downloader.to_screen("[widevine] Acquiring license")
                self.keys = acquire(self.downloader, self.config, pssh, license_url)
                self.downloader.to_screen("[widevine] License acquired; decryption keys ready")
                self.ids = {source["format_id"] for source in selected}
                if has_hls:
                    params["hls_prefer_native"] = True
            params["allow_unplayable_formats"] = False
            yield
        finally:
            params["allow_unplayable_formats"] = allowed
            if had_native:
                params["hls_prefer_native"] = native
            else:
                params.pop("hls_prefer_native", None)
            self.keys = None
            self.ids.clear()
            self.playlists.clear()

    def download(
        self,
        callback: Callable[..., tuple[bool, bool]],
        name: str,
        info: dict[str, Any],
        *,
        subtitle: bool,
        test: bool,
    ) -> tuple[bool, bool]:
        if subtitle or test or not self.config or not self.keys or info.get("format_id") not in self.ids:
            return callback(name, info, subtitle=subtitle, test=test)

        params = self.downloader.params
        allowed = params.get("allow_unplayable_formats")
        try:
            if playlist := self.playlists.get(info["format_id"]):
                info = {**info, **playlist}
                # Preserve encrypted samples for mp4decrypt instead of delegating to ffmpeg.
                params["allow_unplayable_formats"] = True
            result = callback(name, info, subtitle=subtitle, test=test)
        finally:
            params["allow_unplayable_formats"] = allowed
        if result[0]:
            self.downloader.to_screen("[widevine] Decrypting downloaded track")
            decrypt(name, self.keys, self.config.get("mp4decrypt", "mp4decrypt"))
            self.downloader.to_screen("[widevine] Track decrypted")
        return result


def _pssh(data: bytes) -> list[str]:
    result = []
    offset = 0
    while offset < len(data):
        size = int.from_bytes(data[offset : offset + 4])
        kind = data[offset + 4 : offset + 8]
        header = 8
        if size == 1:
            size = int.from_bytes(data[offset + 8 : offset + 16])
            header = 16
        elif size == 0:
            size = len(data) - offset
        if size < header or offset + size > len(data):
            msg = "Invalid Widevine HLS initialization segment"
            raise DownloadError(msg)
        box = data[offset : offset + size]
        if kind == b"moov":
            result.extend(_pssh(box[header:]))
        elif kind == b"pssh" and box[header + 4 : header + 20] == bytes.fromhex(
            WIDEVINE_SYSTEM_ID[9:].replace("-", "")
        ):
            result.append(base64.b64encode(box).decode())
        offset += size
    return result


def _hls(downloader: Any, source: dict[str, Any], *, init: bool) -> tuple[dict[str, Any], list[str]]:
    headers = source.get("http_headers")
    url = source["url"]
    playlist = source.get("hls_media_playlist_data")
    if not playlist:
        _url(url)
        with downloader.urlopen(Request(url, headers=headers, extensions={"timeout": 30})) as response:
            url = getattr(response, "url", url)
            playlist = response.read().decode("utf-8-sig")
    _url(url)

    lines = [line.strip() for line in playlist.splitlines() if line.strip()]
    if not lines or lines[0] != "#EXTM3U" or "#EXT-X-ENDLIST" not in lines:
        msg = "Widevine HLS requires an on-demand media playlist"
        raise DownloadError(msg)

    keys = []
    maps = []
    segments = False
    for line in lines:
        if line.startswith(("#EXT-X-KEY:", "#EXT-X-SESSION-KEY:")):
            attrs = parse_m3u8_attributes(line.split(":", 1)[1])
            if attrs.get("METHOD") not in {"NONE", "SAMPLE-AES", "SAMPLE-AES-CTR"}:
                msg = "Unsupported Widevine HLS encryption method"
                raise DownloadError(msg)
            if attrs.get("KEYFORMAT", "").lower() == WIDEVINE_SYSTEM_ID:
                keys.append(attrs)
        elif line.startswith("#EXT-X-MAP:"):
            if segments or maps:
                msg = "Widevine HLS requires a single initialization segment"
                raise DownloadError(msg)
            maps.append(parse_m3u8_attributes(line.split(":", 1)[1]))
        elif line == "#EXT-X-DISCONTINUITY" or line.startswith("#EXT-X-GAP"):
            msg = "Discontinuous Widevine HLS playlists are not supported"
            raise DownloadError(msg)
        elif not line.startswith("#"):
            _url(urljoin(url, line))
            segments = True

    if not keys and (master := source.get("manifest_url")) and master != source["url"]:
        for line in _read(downloader, master, headers=headers).decode("utf-8-sig").splitlines():
            if line.strip().startswith("#EXT-X-SESSION-KEY:"):
                attrs = parse_m3u8_attributes(line.strip().split(":", 1)[1])
                if attrs.get("KEYFORMAT", "").lower() == WIDEVINE_SYSTEM_ID:
                    keys.append(attrs)

    if not segments or not maps or not maps[0].get("URI") or not keys:
        msg = "Widevine HLS requires fragmented MP4 and a Widevine key declaration"
        raise DownloadError(msg)
    if any(key.get("METHOD") not in {"SAMPLE-AES", "SAMPLE-AES-CTR"} for key in keys):
        msg = "Unsupported Widevine HLS encryption method"
        raise DownloadError(msg)
    if len({(key.get("METHOD"), key.get("URI"), key.get("KEYID")) for key in keys}) > 1:
        msg = "Widevine HLS key rotation is not supported"
        raise DownloadError(msg)

    init_url = _url(urljoin(url, maps[0]["URI"]))
    init_headers = dict(headers or {})
    if byte_range := maps[0].get("BYTERANGE"):
        msg = "Invalid Widevine HLS initialization byte range"
        try:
            length, _, start = byte_range.partition("@")
            length, start = int(length), int(start or "0")
        except ValueError:
            raise DownloadError(msg) from None
        if length <= 0 or start < 0:
            raise DownloadError(msg)
        init_headers["Range"] = f"bytes={start}-{start + length - 1}"

    pssh = []
    for key in keys:
        uri = key.get("URI", "")
        if uri.startswith("data:"):
            encoding, separator, value = uri.partition(",")
            if not separator or not encoding.endswith(";base64"):
                msg = "Invalid Widevine HLS initialization data"
                raise DownloadError(msg)
            pssh.append(unquote(value))
    if init and not pssh:
        pssh.extend(_pssh(_read(downloader, init_url, headers=init_headers)))
    return {"url": url, "hls_media_playlist_data": playlist}, pssh


def _url(value: object) -> str:
    if not isinstance(value, str) or urlsplit(value).scheme not in {"http", "https"}:
        msg = "Widevine URLs must use http or https"
        raise ValueError(msg)
    validate_url(value)
    return value


def validate_config(data: dict[str, Any], options: dict[str, str], path: Path) -> dict[str, Any]:
    if any(not isinstance(data.get(key), str) or not data[key].strip() for key in ("api_url", "api_key", "device")):
        msg = "Widevine configuration requires api_url, api_key, and device"
        raise ValueError(msg)
    data["api_url"] = _url(data["api_url"])
    try:
        data["api_key"] = resolve_secret(data["api_key"].strip(), base_dir=path.parent)
    except ValueError as exc:
        msg = "Unable to read Widevine API key"
        raise ValueError(msg) from exc
    for key in ("license_url", "pssh", "mp4decrypt"):
        if key in data and (not isinstance(data[key], str) or not data[key].strip()):
            msg = f"Widevine {key} must be a non-blank string"
            raise ValueError(msg)
    for url in (data.get("license_url"), options.get("license_url")):
        if url:
            _url(url)
    headers = data.get("license_headers", {})
    if not isinstance(headers, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()
    ):
        msg = "Widevine license_headers must be an object of strings"
        raise ValueError(msg)
    if not isinstance(data.get("privacy", False), bool):
        msg = "Widevine privacy must be a boolean"
        raise ValueError(msg)
    if data.get("license_type", "STREAMING") not in ("STREAMING", "OFFLINE", "AUTOMATIC"):
        msg = "Widevine license_type is invalid"
        raise ValueError(msg)
    return data


def encrypted(info: dict[str, Any]) -> bool:
    return bool((info.get("has_drm") and info["has_drm"] != "maybe") or info.get("drm"))


def _read(downloader: Any, url: str, *, body: bytes | None = None, headers: dict[str, str] | None = None) -> bytes:
    _url(url)
    with downloader.urlopen(Request(url, data=body, headers=headers, extensions={"timeout": 30})) as response:
        return response.read()


def metadata(
    downloader: Any, info: dict[str, Any], config: dict[str, Any], options: dict[str, str]
) -> tuple[list[str], str, dict[str, dict[str, Any]]]:
    sources = info.get("requested_formats") or [info]
    pssh = []
    license_url = options.get("license_url") or config.get("license_url")
    override = options.get("pssh") or config.get("pssh")
    manifests = {}
    playlists = {}
    for source in sources:
        if not encrypted(source):
            continue
        protection = source.get("drm") or {}
        if protection.get("system", "widevine").lower() != "widevine":
            msg = "Only Widevine DRM is supported"
            raise DownloadError(msg)
        license_url = license_url or protection.get("license_url")
        value = override or protection.get("pssh")
        if source.get("protocol") in HLS_PROTOCOLS:
            try:
                playlist, values = _hls(downloader, source, init=not value)
            except DownloadError:
                raise
            except Exception:
                msg = "Unable to read Widevine HLS metadata"
                raise DownloadError(msg) from None
            playlists[source["format_id"]] = playlist
            pssh.extend([value] if value else values)
        elif value:
            pssh.append(value)
        elif manifest := source.get("manifest_url"):
            manifests[manifest] = source.get("http_headers")

    for manifest, headers in manifests.items():
        try:
            root = ElementTree.fromstring(_read(downloader, manifest, headers=headers))
            for element in root.iter():
                if element.tag.rsplit("}", 1)[-1] != "ContentProtection":
                    continue
                if element.get("schemeIdUri", "").lower() != WIDEVINE_SYSTEM_ID:
                    continue
                if element.get("licenseUrl") and not license_url:
                    license_url = urljoin(manifest, element.get("licenseUrl"))
                for child in element.iter():
                    name = child.tag.rsplit("}", 1)[-1].lower()
                    if name == "pssh" and child.text:
                        pssh.append("".join(child.text.split()))
                    elif name in {"laurl", "license"}:
                        value = child.get("licenseUrl") or child.get("href") or child.text
                        if value and not license_url:
                            license_url = urljoin(manifest, value.strip())
        except Exception:
            msg = "Unable to read Widevine manifest metadata"
            raise DownloadError(msg) from None
    if not pssh or not license_url:
        msg = "Widevine stream metadata is incomplete"
        raise DownloadError(msg)
    try:
        decoded = [base64.b64decode(value, validate=True) for value in pssh]
        _url(license_url)
    except (TypeError, ValueError):
        msg = "Invalid Widevine stream metadata"
        raise DownloadError(msg) from None
    if not all(decoded):
        msg = "Invalid Widevine stream metadata"
        raise DownloadError(msg)
    return list(dict.fromkeys(pssh)), license_url, playlists


def acquire(downloader: Any, config: dict[str, Any], pssh: list[str], license_url: str) -> list[tuple[str, str]]:
    keys = {}
    api = config["api_url"].rstrip("/")
    device = quote(config["device"], safe="")
    headers = {"Content-Type": "application/octet-stream", **config.get("license_headers", {})}
    with httpx.Client(timeout=30.0) as client:

        def serve(method: str, endpoint: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
            response = client.request(
                method, f"{api}/{device}/{endpoint}", headers={"X-Secret-Key": config["api_key"]}, json=body
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status", 200) >= 400:
                msg = "Widevine key service request failed"
                raise DownloadError(msg)
            return payload.get("data") or {}

        try:
            for init in pssh:
                session = serve("GET", "open")["session_id"]
                try:
                    if config.get("privacy"):
                        certificate = _read(downloader, license_url, body=base64.b64decode("CAQ="), headers=headers)
                        serve(
                            "POST",
                            "set_service_certificate",
                            {"session_id": session, "cert_b64": base64.b64encode(certificate).decode()},
                        )
                    challenge = serve(
                        "POST",
                        f"get_license_challenge/{config.get('license_type', 'STREAMING')}",
                        {"session_id": session, "init_data": init, "privacy_mode": config.get("privacy", False)},
                    )
                    body = base64.b64decode(challenge["challenge_b64"], validate=True)
                    license_message = _read(downloader, license_url, body=body, headers=headers)
                    serve(
                        "POST",
                        "parse_license",
                        {"session_id": session, "license_message": base64.b64encode(license_message).decode()},
                    )
                    for key in serve("POST", "get_keys/CONTENT", {"session_id": session}).get("keys", []):
                        kid, value = key["key_id"], key["key"]
                        if (
                            not isinstance(kid, str)
                            or not isinstance(value, str)
                            or not HEX_KEY.fullmatch(kid)
                            or not HEX_KEY.fullmatch(value)
                        ):
                            msg = "Widevine key service returned invalid content keys"
                            raise DownloadError(msg)
                        keys[kid.lower()] = value.lower()
                finally:
                    try:
                        serve("GET", f"close/{quote(session, safe='')}")
                    except Exception:
                        LOG.warning("Unable to close widevine key service session")
        except Exception:
            msg = "Widevine license exchange failed"
            raise DownloadError(msg) from None
    if not keys:
        msg = "Widevine key service returned no content keys"
        raise DownloadError(msg)
    return list(keys.items())


def decrypt(path: str, keys: list[tuple[str, str]], executable: str) -> None:
    source = Path(path)
    fd, name = tempfile.mkstemp(prefix=".widevine-", suffix=source.suffix, dir=source.parent)
    os.close(fd)
    output = Path(name)
    try:
        stat = source.stat()
        key_args = [item for kid, key in keys for item in ("--key", f"{kid}:{key}")]
        process = subprocess.Popen(
            [executable, *key_args, str(source), str(output)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        try:
            process.communicate(timeout=60)
        finally:
            try:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
            finally:
                if process.stderr:
                    process.stderr.close()
        if process.returncode or not output.is_file() or output.stat().st_size == 0:
            msg = "Widevine decryption failed"
            raise DownloadError(msg)
        output.chmod(stat.st_mode)
        os.utime(output, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        output.replace(source)
    except (OSError, subprocess.SubprocessError):
        msg = "Widevine decryption failed"
        raise DownloadError(msg) from None
    finally:
        output.unlink(missing_ok=True)
