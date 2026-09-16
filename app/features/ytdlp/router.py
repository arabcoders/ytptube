import copy
import json
import logging
import mimetypes
import re
import secrets
import time
from collections import OrderedDict
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

from aiohttp import helpers, web
from aiohttp.web import Request, Response

from app.features.core.utils import api_error_response
from app.features.downloads.items import Item
from app.features.presets.service import Presets
from app.features.ytdlp.archiver import Archiver
from app.features.ytdlp.extractor import fetch_info
from app.features.ytdlp.shortcut import (
    FORBIDDEN_REQUEST_HEADERS,
    RESPONSE_HEADERS,
    direct_url,
    extracted_headers,
    media_type,
    safe_filename,
    selected_format,
)
from app.features.ytdlp.utils import archive_read, arg_converter, get_archive_id
from app.features.ytdlp.ytdlp_opts import YTDLPCli, YTDLPOpts
from app.library.cache import Cache
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.httpx_client import get_async_client
from app.library.logging import get_logger
from app.library.router import route
from app.library.Utils import validate_url

LOG = get_logger()
ENTRIES_BROWSER_WAIT = 10
SHORTCUT_TTL = 21600
SHORTCUT_RANGE = re.compile(r"^bytes=(?:\d+-\d*|-\d+)$")
SHORTCUT_TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")


def _valid_shortcut_range(value: str) -> bool:
    value = value.strip()
    if not SHORTCUT_RANGE.fullmatch(value):
        return False

    range_value = value.removeprefix("bytes=")
    if range_value.startswith("-"):
        return int(range_value[1:]) > 0

    start, _, end = range_value.partition("-")
    return not end or int(start) <= int(end)


def _annotate_archive(data: dict[str, Any], archive_file: str | None) -> dict[str, Any]:
    annotated = copy.deepcopy(data)
    archive_ids: list[str] = []

    def annotate_entries(entries: list[Any]) -> None:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            archive_id = None
            if isinstance(entry.get("id"), str) and isinstance(entry.get("ie_key"), str):
                archive_id = f"{entry['ie_key'].lower()} {entry['id']}"
                archive_ids.append(archive_id)
            entry["archive_id"] = archive_id
            entry["is_archived"] = False
            if isinstance(entry.get("entries"), list):
                annotate_entries(entry["entries"])

    def mark_entries(entries: list[Any], archived: set[str]) -> None:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry["is_archived"] = entry.get("archive_id") in archived
            if isinstance(entry.get("entries"), list):
                mark_entries(entry["entries"], archived)

    if isinstance(annotated.get("entries"), list):
        annotate_entries(annotated["entries"])
    archived = set(archive_read(archive_file, archive_ids)) if archive_file and archive_ids else set()
    if isinstance(annotated.get("entries"), list):
        mark_entries(annotated["entries"], archived)
    archive_id = annotated.get("archive_id")
    annotated["is_archived"] = bool(archive_id and archive_id in archived) if archive_file else False
    return annotated


def _get_preset_archive(preset: str) -> str | None:
    """
    Resolve the archive file path for a given preset.

    Validates that the preset exists and that applying the preset results
    in yt-dlp options that contain a 'download_archive' path.
    """
    if not preset or not Presets.get_instance().has(preset):
        return None

    try:
        opts: dict = YTDLPOpts.get_instance().preset(preset).get_all()
    except Exception as e:
        LOG.exception(
            "Failed to build yt-dlp options for preset '%s': %s.",
            preset,
            e,
            extra={"preset": preset, "exception_type": type(e).__name__},
        )
        return None

    if not (archive_file := opts.get("download_archive")):
        return None

    if not isinstance(archive_file, str) or len(archive_file.strip()) < 1:
        return None

    return archive_file.strip()


def _normalize_ids(items: Iterable[str] | None) -> tuple[list[str], list[str]]:
    """
    Validate and normalize archive IDs.

    - Trims whitespace
    - Enforces that each ID has at least two whitespace-separated tokens
      (e.g., "youtube ABC123") as required by yt-dlp's archive format
    - De-duplicates while preserving order

    Returns a tuple: (valid_ids, invalid_inputs)
    """
    if not items:
        return ([], [])

    seen: set[str] = set()
    valid: list[str] = []
    invalid: list[str] = []

    for raw in items:
        if raw is None:
            continue

        s = str(raw).strip()
        if not s:
            continue

        if len(s.split()) < 2:
            invalid.append(s)
            continue

        if s in seen:
            continue

        seen.add(s)
        valid.append(s)

    return (valid, invalid)


@route("GET", "api/archiver/", "archiver")
async def archiver_get(request: Request) -> Response:
    """
    Read IDs from the download archive for a given preset.

    Query params:
      - preset: required preset name/id
      - ids: optional comma-separated list to filter; when omitted, returns all
    """
    preset: str | None = request.query.get("preset")
    if not preset:
        return api_error_response(
            "preset is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.preset"},
        )

    archive_file: str | None = _get_preset_archive(preset)
    if not archive_file:
        return api_error_response(
            f"Preset '{preset}' does not provide a download_archive.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.preset"},
        )

    ids_param: str | None = request.query.get("ids")
    ids: list[str] = []
    if ids_param:
        ids_list = [s.strip() for s in ids_param.split(",") if s and s.strip()]
        ids, invalid = _normalize_ids(ids_list)
        if invalid:
            return api_error_response(
                "invalid ids provided.",
                code="INVALID",
                status=web.HTTPBadRequest.status_code,
                params={"field": "api.fields.ids"},
                extra={"invalid_items": invalid},
            )

    try:
        data: list[str] = Archiver.get_instance().read(archive_file, ids or None)
        return web.json_response(
            data={"file": archive_file, "items": data, "count": len(data)}, status=web.HTTPOk.status_code
        )
    except Exception as e:
        LOG.exception(
            "Failed to read archive file '%s' for preset '%s': %s.",
            archive_file,
            preset,
            e,
            extra={
                "route": "api/archiver/",
                "action": "read_archive",
                "preset": preset,
                "archive_file": archive_file,
                "ids": ids,
            },
        )
        return api_error_response(
            f"Failed to read archive file for preset '{preset}'.",
            code="OPERATION_FAILED",
            status=web.HTTPInternalServerError.status_code,
            message=str(e),
        )


@route("POST", "api/archiver/", "archiver_add")
async def archiver_add(request: Request) -> Response:
    """
    Append IDs to the download archive for a given preset.

    Body: { "preset": string, "items": [string, ...], "skip_check": bool? }
    """
    post = await request.json()
    preset: str | None = post.get("preset") if isinstance(post, dict) else None
    if not preset:
        return api_error_response(
            "preset is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.preset"},
        )

    archive_file: str | None = _get_preset_archive(preset)
    if not archive_file:
        return api_error_response(
            f"Preset '{preset}' does not provide a download_archive.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.preset"},
        )

    items, invalid = _normalize_ids((post or {}).get("items", [])) if isinstance(post, dict) else ([], [])
    if invalid:
        return api_error_response(
            "invalid ids provided.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
            extra={"invalid_items": invalid},
        )
    if len(items) < 1:
        return api_error_response(
            "items is required and must be a non-empty list.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    skip_check: bool = bool(post.get("skip_check", False)) if isinstance(post, dict) else False

    try:
        status: bool = Archiver.get_instance().add(archive_file, items, skip_check=skip_check)
        return web.json_response(
            data={"file": archive_file, "status": status, "items": items},
            status=web.HTTPOk.status_code if status else web.HTTPNotModified.status_code,
        )
    except Exception as e:
        LOG.exception(
            "Failed to add %s item(s) to archive file '%s' for preset '%s': %s.",
            len(items),
            archive_file,
            preset,
            e,
            extra={
                "route": "api/archiver/",
                "action": "add_archive_items",
                "preset": preset,
                "archive_file": archive_file,
                "item_count": len(items),
                "skip_check": skip_check,
            },
        )
        return api_error_response(
            f"Failed to add items to archive for preset '{preset}'.",
            code="OPERATION_FAILED",
            status=web.HTTPInternalServerError.status_code,
            message=str(e),
        )


@route("DELETE", "api/archiver/", "archiver_delete")
async def archiver_delete(request: Request) -> Response:
    """
    Remove IDs from the download archive for a given preset.

    Body: { "preset": string, "items": [string, ...] }
    """
    post = await request.json()
    preset: str | None = post.get("preset") if isinstance(post, dict) else None
    if not preset:
        return api_error_response(
            "preset is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.preset"},
        )

    archive_file: str | None = _get_preset_archive(preset)
    if not archive_file:
        return api_error_response(
            f"Preset '{preset}' does not provide a download_archive.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.preset"},
        )

    items, invalid = _normalize_ids((post or {}).get("items", [])) if isinstance(post, dict) else ([], [])
    if invalid:
        return api_error_response(
            "invalid ids provided.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
            extra={"invalid_items": invalid},
        )
    if len(items) < 1:
        return api_error_response(
            "items is required and must be a non-empty list.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.ids"},
        )

    try:
        status: bool = Archiver.get_instance().delete(archive_file, items)
        return web.json_response(
            data={"file": archive_file, "status": status, "items": items},
            status=web.HTTPOk.status_code if status else web.HTTPNotModified.status_code,
        )
    except Exception as e:
        LOG.exception(
            "Failed to delete %s item(s) from archive file '%s' for preset '%s': %s.",
            len(items),
            archive_file,
            preset,
            e,
            extra={
                "route": "api/archiver/",
                "action": "delete_archive_items",
                "preset": preset,
                "archive_file": archive_file,
                "item_count": len(items),
            },
        )
        return api_error_response(
            f"Failed to delete items from archive for preset '{preset}'.",
            code="OPERATION_FAILED",
            status=web.HTTPInternalServerError.status_code,
            message=str(e),
        )


@route("POST", "api/yt-dlp/convert/", "convert")
async def convert(request: Request) -> Response:
    """
    Convert the yt-dlp args to a dict.

    Args:
        request (Request): The request object.

    Returns:
        Response: The response object.

    """
    post = await request.json()
    args: str | None = post.get("args")

    if not args:
        return api_error_response(
            "args param is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.args"},
        )

    try:
        response: dict[str, Any] = {"opts": {}, "output_template": None, "download_path": None}

        data = arg_converter(args, dumps=True)

        if "outtmpl" in data and "default" in data["outtmpl"]:
            response["output_template"] = data["outtmpl"]["default"]

        if "paths" in data and "home" in data["paths"]:
            response["download_path"] = data["paths"]["home"]

        if "format" in data:
            response["format"] = data["format"]

        from app.features.ytdlp.utils import _DATA

        bad_options = {k: v for d in _DATA.REMOVE_KEYS for k, v in d.items()}
        removed_options = []

        for key in data:
            if key in bad_options.items():
                removed_options.append(bad_options[key])
                continue
            if not key.startswith("_"):
                response["opts"][key] = data[key]

        if len(removed_options) > 0:
            response["removed_options"] = removed_options

        return web.json_response(data=response, status=web.HTTPOk.status_code)
    except Exception as e:
        err = str(e).strip()
        err = err.split("\n")[-1] if "\n" in err else err
        err = err.replace("main.py: error: ", "").strip().capitalize()
        return api_error_response(
            f"Failed to parse command options for yt-dlp. '{err}'.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.args"},
            detail=err,
        )


@route("GET", "api/yt-dlp/url/info/", "get_info")
async def get_info(request: Request, cache: Cache, config: Config) -> Response:
    """
    Get the video info.

    Args:
        request (Request): The request object.
        cache (Cache): The cache instance.
        config (Config): The config instance.

    Returns:
        Response: The response object

    """
    url: str | None = request.query.get("url")
    if not url:
        return api_error_response(
            "URL is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.url"},
            message="URL is required.",
            extra={"status": False},
        )

    try:
        validate_url(url)
    except ValueError as e:
        return api_error_response(
            str(e),
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.url"},
            message=str(e),
            detail=str(e),
            extra={"status": False},
        )

    opts: YTDLPOpts = YTDLPOpts.get_instance()

    preset: str = request.query.get("preset", config.default_preset)
    include_entries: bool = request.query.get("entries", "").lower() in {"1", "true", "yes"}
    if not Presets.get_instance().get(preset):
        msg: str = f"Preset '{preset}' does not exist."
        return api_error_response(
            msg,
            code="NOT_FOUND",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.preset"},
            message=msg,
            extra={"status": False},
        )

    opts = opts.preset(preset)

    if cli_args := request.query.get("args", None):
        try:
            arg_converter(cli_args, dumps=True)
            opts = opts.add_cli(cli_args, from_user=True)
        except Exception as e:
            err = str(e).strip()
            err = err.split("\n")[-1] if "\n" in err else err
            err = err.replace("main.py: error: ", "").strip().capitalize()
            return api_error_response(
                f"Failed to parse command options for yt-dlp. '{err}'.",
                code="INVALID",
                status=web.HTTPBadRequest.status_code,
                params={"field": "api.fields.args"},
                detail=err,
            )

    try:
        cache_suffix = ":entries" if include_entries else ""
        key: str = cache.hash(f"{preset}:{url}:{cli_args or ''}{cache_suffix}")

        if cache.has(key) and not request.query.get("force", False):
            data: Any | None = cache.get(key)
            if data is None:
                data = {}
            data = _annotate_archive(data, opts.get_all().get("download_archive"))
            data["_cached"] = {
                "status": "hit",
                "preset": preset,
                "cli_args": cli_args,
                "key": key,
                "ttl": data.get("_cached", {}).get("ttl", 300),
                "ttl_left": data.get("_cached", {}).get("expires", time.time() + 300) - time.time(),
                "expires": data.get("_cached", {}).get("expires", time.time() + 300),
            }
            return web.json_response(text=json.dumps(data, indent=4, default=str), status=web.HTTPOk.status_code)

        ytdlp_opts: dict = opts.get_all()
        if include_entries:
            ytdlp_opts.pop("noplaylist", None)
            ytdlp_opts["extract_flat"] = "in_playlist"
            ytdlp_opts["skip_download"] = True
            extractor_args = ytdlp_opts.setdefault("extractor_args", {})
            generic_args = extractor_args.setdefault("generic", {})
            wait_values = generic_args.get("wait")
            if not wait_values:
                generic_args["wait"] = [str(ENTRIES_BROWSER_WAIT)]
            else:
                try:
                    if float(wait_values[0]) > ENTRIES_BROWSER_WAIT:
                        generic_args["wait"] = [str(ENTRIES_BROWSER_WAIT)]
                except (TypeError, ValueError):
                    pass

        (data, logs) = await fetch_info(
            config=ytdlp_opts,
            url=url,
            debug=False,
            no_archive=True,
            follow_redirect=True,
            sanitize_info=not include_entries,
            capture_logs=logging.WARNING,
        )

        if not data or not isinstance(data, dict):
            return api_error_response(
                f"Failed to extract video info. {'. '.join(logs)}",
                code="OPERATION_FAILED",
                status=web.HTTPInternalServerError.status_code,
                message="Failed to extract video info.",
                extra={"status": False},
            )

        if data and "formats" in data:
            from yt_dlp.cookies import LenientSimpleCookie

            for index, item in enumerate(data["formats"]):
                if "cookies" in item and len(item["cookies"]) > 0:
                    cookies: list[str] = [f"{c.key}={c.value}" for c in LenientSimpleCookie(item["cookies"]).values()]
                    if len(cookies) > 0:
                        data["formats"][index]["h_cookies"] = "; ".join(cookies)
                        data["formats"][index]["h_cookies"] = data["formats"][index]["h_cookies"].strip()

        data["_cached"] = {
            "status": "miss",
            "preset": preset,
            "cli_args": cli_args,
            "key": key,
            "ttl": 300,
            "ttl_left": 300,
            "expires": time.time() + 300,
        }

        archive_file: str | None = ytdlp_opts.get("download_archive")
        data["archive_file"] = archive_file or None

        if archive_file and (archive_id := get_archive_id(url=url).get("archive_id")):
            data["archive_id"] = archive_id

        data = OrderedDict(sorted(data.items(), key=lambda item: len(str(item[1]))))

        cache.set(key=key, value=data, ttl=300)

        return web.json_response(
            text=json.dumps(_annotate_archive(data, archive_file), indent=4, default=str),
            status=web.HTTPOk.status_code,
        )
    except Exception as e:
        LOG.exception(
            "Failed to get video info for '%s': %s.",
            url,
            e,
            extra={
                "route": "api/yt-dlp/url/info/",
                "action": "get_video_info",
                "url": url,
                "preset": preset,
                "cache_key": key if "key" in locals() else None,
                "has_cli_args": bool(cli_args),
            },
        )
        return api_error_response(
            "failed to get video info.",
            code="OPERATION_FAILED",
            status=web.HTTPInternalServerError.status_code,
            message=str(e),
            detail=str(e),
            extra={"formats": []},
        )


@route("GET", "api/yt-dlp/options/", "get_options")
async def get_options() -> Response:
    """
    Get the yt-dlp CLI options.

    Returns:
        Response: The response object with the yt-dlp CLI options.

    """
    from app.features.ytdlp.ytdlp import ytdlp_options

    return web.json_response(text=json.dumps(ytdlp_options(), indent=4, default=str), status=web.HTTPOk.status_code)


@route("POST", "api/yt-dlp/archive_id/", "get_archive_ids")
async def get_archive_ids(request: Request) -> Response:
    """
    Get the archive IDs for the given URLs.

    Returns:
        Response: The response object with the yt-dlp CLI options.

    """
    data = (await request.json()) if request.body_exists else None
    if not data or not isinstance(data, list):
        return api_error_response(
            "Invalid request. expecting list with URLs.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    response = []

    for i, url in enumerate(data):
        dct: dict[str, Any] = {"index": i, "url": url}
        if not isinstance(url, str):
            dct.update({"id": None, "ie_key": None, "archive_id": None, "error": "URL must be a string."})
            response.append(dct)
            continue
        try:
            validate_url(url)
            dct.update(get_archive_id(url))
        except ValueError as e:
            dct.update({"id": None, "ie_key": None, "archive_id": None, "error": str(e)})

        response.append(dct)

    return web.json_response(data=response, status=web.HTTPOk.status_code)


@route("POST", "api/yt-dlp/command/", "make_command")
async def make_command(request: Request, config: Config, encoder: Encoder) -> Response:
    """
    Build yt-dlp CLI command.

    Args:
        request (Request): The request object.
        config (Config): The config instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object with the merged fields and final yt-dlp CLI command string.

    """
    if not config.console_enabled:
        return api_error_response(
            "Console is disabled.",
            code="FEATURE_DISABLED",
            status=web.HTTPForbidden.status_code,
            params={"feature": "api.features.console"},
        )

    data = (await request.json()) if request.body_exists else None
    if not data or not isinstance(data, dict):
        return api_error_response(
            "Invalid request. expecting JSON body.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    try:
        it = Item.format(data)
    except ValueError as e:
        return api_error_response(
            str(e),
            code="VALIDATION_FAILED",
            status=web.HTTPBadRequest.status_code,
            detail=str(e),
            extra={"data": data},
        )

    try:
        command, info = YTDLPCli(item=it, config=config).build()
    except Exception as e:
        LOG.exception(
            "Failed to build yt-dlp command for '%s': %s.",
            it.url,
            e,
            extra={
                "route": "api/yt-dlp/command/",
                "action": "build_command",
                "url": it.url,
                "preset": it.preset,
                "has_cookies": bool(it.cookies),
                "exception_type": type(e).__name__,
            },
        )
        return api_error_response(
            f"Failed to build CLI command: {e}",
            code="OPERATION_FAILED",
            status=web.HTTPBadRequest.status_code,
            detail=str(e),
        )

    if request.query.get("full", False):
        return web.json_response(data=info, status=web.HTTPOk.status_code, dumps=encoder.encode)

    return web.json_response(data={"command": command}, status=web.HTTPOk.status_code)


@route("GET", "api/yt-dlp/shortcut/info", "shortcut.info")
async def shortcut_info(request: Request, cache: Cache, config: Config) -> Response:
    if not (url := request.query.get("url")):
        return api_error_response("URL is required.", code="REQUIRED", status=web.HTTPBadRequest.status_code)

    try:
        validate_url(url)
    except ValueError as exc:
        return api_error_response(str(exc), code="INVALID", status=web.HTTPBadRequest.status_code)

    preset: str = request.query.get("preset") or config.default_preset
    if not Presets.get_instance().get(preset):
        return api_error_response(
            f"Preset '{preset}' does not exist.", code="NOT_FOUND", status=web.HTTPNotFound.status_code
        )

    try:
        opts = YTDLPOpts.get_instance().preset(preset).get_all()
        opts["format"] = "best"
        opts.pop("format_sort", None)
        opts.pop("format_sort_force", None)
        opts["noplaylist"] = True
        opts.pop("download_archive", None)
        data, _logs = await fetch_info(
            config=opts,
            url=url,
            debug=False,
            no_archive=True,
            follow_redirect=True,
            sanitize_info=False,
            capture_logs=logging.WARNING,
        )
    except Exception:
        LOG.exception("Shortcut extraction failed.", extra={"route": "shortcut.info"})
        return api_error_response(
            "Failed to extract video info.", code="OPERATION_FAILED", status=web.HTTPInternalServerError.status_code
        )

    if not isinstance(data, dict):
        return api_error_response(
            "Failed to extract video info.", code="OPERATION_FAILED", status=web.HTTPInternalServerError.status_code
        )

    if data.get("_type") in {"playlist", "multi_video"} or data.get("entries"):
        return api_error_response(
            "Playlists are not supported.", code="OPERATION_FAILED", status=web.HTTPBadRequest.status_code
        )

    if data.get("is_live") or data.get("is_upcoming") or data.get("live_status") in {"is_live", "is_upcoming", "live"}:
        return api_error_response(
            "Live and upcoming content are not supported.",
            code="OPERATION_FAILED",
            status=web.HTTPBadRequest.status_code,
        )

    try:
        selected = selected_format(data)
    except ValueError as exc:
        return api_error_response(str(exc), code="OPERATION_FAILED", status=web.HTTPBadRequest.status_code)

    token: str = secrets.token_urlsafe(18)
    impersonate: str | None = opts.get("impersonate")
    filename: str = safe_filename(data, selected)
    extension: str = filename.rsplit(".", 1)[-1]
    descriptor = {
        "format": selected,
        "headers": extracted_headers(selected, data, opts),
        "filename": filename,
        "ext": extension,
        "proxy": opts.get("proxy"),
        "use_curl": opts.get("use_curl", True) if isinstance(opts.get("use_curl", True), bool) else True,
        "curl_impersonate": impersonate if isinstance(impersonate, str) else "chrome",
        "curl_default_headers": opts.get("curl_default_headers", True)
        if isinstance(opts.get("curl_default_headers", True), bool)
        else True,
        "timeout": opts.get("socket_timeout", 30) if isinstance(opts.get("socket_timeout", 30), (int, float)) else 30,
    }

    cache.set(f"shortcut:{token}", descriptor, ttl=SHORTCUT_TTL, persist=False)

    fields = (
        "title",
        "id",
        "format",
        "format_id",
        "format_note",
        "ext",
        "width",
        "height",
        "resolution",
        "duration",
        "media_type",
        "vcodec",
        "acodec",
        "filename",
    )

    result = {
        key: (media_type(selected) if key == "media_type" else filename if key == "filename" else data.get(key))
        for key in fields
    }

    if result.get("resolution") is None and result.get("width") and result.get("height"):
        result["resolution"] = f"{result['width']}x{result['height']}"

    result["filesize"] = selected.get("filesize") or selected.get("filesize_approx") or data.get("filesize_approx")
    result["download_url"] = f"/api/yt-dlp/shortcut/download/{token}"

    return web.json_response({key: value for key, value in result.items() if value is not None})


@route("GET", "api/yt-dlp/shortcut/download/{token}", "shortcut.download")
async def shortcut_download(request: Request, cache: Cache) -> Response | web.StreamResponse:
    if not (token := request.match_info.get("token")):
        return api_error_response("Download token is required.", code="REQUIRED", status=web.HTTPBadRequest.status_code)

    descriptor = cache.get(f"shortcut:{token}") if isinstance(token, str) and SHORTCUT_TOKEN.fullmatch(token) else None
    if (
        not isinstance(descriptor, dict)
        or not isinstance(descriptor.get("format"), dict)
        or not isinstance(descriptor.get("headers"), dict)
        or not isinstance(descriptor.get("filename"), str)
        or not isinstance(descriptor.get("ext"), str)
    ):
        return api_error_response(
            "Invalid or expired download token.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code
        )

    selected = descriptor["format"]
    if not isinstance(selected, dict) or not direct_url(selected):
        return api_error_response("Invalid download target.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    url = selected["url"]
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or parsed.username or parsed.password:
        return api_error_response("Invalid download target.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    range_header = request.headers.get("Range")
    if range_header and not _valid_shortcut_range(range_header):
        return api_error_response("Invalid Range header.", code="INVALID", status=web.HTTPBadRequest.status_code)

    headers = descriptor["headers"]
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()):
        return api_error_response("Invalid download token.", code="BAD_REQUEST", status=web.HTTPBadRequest.status_code)

    headers = extracted_headers(selected, {}, {"http_headers": headers})
    upstream_headers = {key: value for key, value in headers.items() if key.lower() not in FORBIDDEN_REQUEST_HEADERS}
    if range_header:
        upstream_headers["Range"] = range_header.strip()

    try:
        client = get_async_client(
            proxy=descriptor.get("proxy"),
            use_curl=descriptor.get("use_curl", True),
            curl_impersonate=descriptor.get("curl_impersonate", "chrome"),
            curl_default_headers=descriptor.get("curl_default_headers", True),
        )
        upstream = await client.send(
            client.build_request("GET", url, headers=upstream_headers, timeout=descriptor.get("timeout", 30)),
            stream=True,
            follow_redirects=True,
        )
    except Exception:
        LOG.exception("Shortcut upstream request failed.", extra={"route": "shortcut.download"})
        return api_error_response(
            "Unable to retrieve the download.", code="OPERATION_FAILED", status=web.HTTPBadGateway.status_code
        )

    if upstream.status_code not in {200, 206}:
        await upstream.aclose()
        return api_error_response(
            "Unable to retrieve the download.", code="OPERATION_FAILED", status=web.HTTPBadGateway.status_code
        )

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() in RESPONSE_HEADERS
        and "\r" not in key
        and "\n" not in key
        and "\r" not in value
        and "\n" not in value
    }

    filename = descriptor["filename"]
    extension = descriptor["ext"]
    if not any(key.lower() == "content-type" for key in response_headers):
        response_headers["Content-Type"] = mimetypes.guess_type(f"file.{extension}")[0] or "application/octet-stream"

    response_headers["Cache-Control"] = "no-store"
    response_headers["X-Content-Type-Options"] = "nosniff"
    response_headers["Content-Disposition"] = helpers.content_disposition_header("attachment", filename=filename)
    response = web.StreamResponse(status=upstream.status_code, headers=response_headers)

    try:
        await response.prepare(request)
        async for chunk in upstream.aiter_bytes(64 * 1024):
            if request.transport is None or request.transport.is_closing():
                break
            await response.write(chunk)
        await response.write_eof()
    except (ConnectionError, RuntimeError):
        LOG.info("Shortcut client disconnected during download.", extra={"route": "shortcut.download"})
    finally:
        await upstream.aclose()

    return response
