import json
import logging
import time
from collections import OrderedDict
from collections.abc import Iterable
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response

from app.features.presets.service import Presets
from app.features.ytdlp.archiver import Archiver
from app.features.ytdlp.extractor import fetch_info
from app.features.ytdlp.utils import archive_read, arg_converter, get_archive_id
from app.features.ytdlp.ytdlp_opts import YTDLPCli, YTDLPOpts
from app.library.cache import Cache
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.ItemDTO import Item
from app.library.router import route
from app.library.Utils import validate_url

LOG: logging.Logger = logging.getLogger(__name__)


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
        LOG.error(f"Failed to build yt-dlp opts for preset '{preset}'. {e!s}")
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
        return web.json_response(data={"error": "preset is required."}, status=web.HTTPBadRequest.status_code)

    archive_file: str | None = _get_preset_archive(preset)
    if not archive_file:
        return web.json_response(
            data={"error": f"Preset '{preset}' does not provide a download_archive."},
            status=web.HTTPBadRequest.status_code,
        )

    ids_param: str | None = request.query.get("ids")
    ids: list[str] = []
    if ids_param:
        ids_list = [s.strip() for s in ids_param.split(",") if s and s.strip()]
        ids, invalid = _normalize_ids(ids_list)
        if invalid:
            return web.json_response(
                data={"error": "invalid ids provided.", "invalid_items": invalid},
                status=web.HTTPBadRequest.status_code,
            )

    try:
        data: list[str] = Archiver.get_instance().read(archive_file, ids or None)
        return web.json_response(
            data={"file": archive_file, "items": data, "count": len(data)}, status=web.HTTPOk.status_code
        )
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": f"Failed to read archive file for preset '{preset}'.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
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
        return web.json_response(data={"error": "preset is required."}, status=web.HTTPBadRequest.status_code)

    archive_file: str | None = _get_preset_archive(preset)
    if not archive_file:
        return web.json_response(
            data={"error": f"Preset '{preset}' does not provide a download_archive."},
            status=web.HTTPBadRequest.status_code,
        )

    items, invalid = _normalize_ids((post or {}).get("items", [])) if isinstance(post, dict) else ([], [])
    if invalid:
        return web.json_response(
            data={"error": "invalid ids provided.", "invalid_items": invalid},
            status=web.HTTPBadRequest.status_code,
        )
    if len(items) < 1:
        return web.json_response(
            data={"error": "items is required and must be a non-empty list."}, status=web.HTTPBadRequest.status_code
        )

    skip_check: bool = bool(post.get("skip_check", False)) if isinstance(post, dict) else False

    try:
        status: bool = Archiver.get_instance().add(archive_file, items, skip_check=skip_check)
        return web.json_response(
            data={"file": archive_file, "status": status, "items": items},
            status=web.HTTPOk.status_code if status else web.HTTPNotModified.status_code,
        )
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": f"Failed to add items to archive for preset '{preset}'.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
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
        return web.json_response(data={"error": "preset is required."}, status=web.HTTPBadRequest.status_code)

    archive_file: str | None = _get_preset_archive(preset)
    if not archive_file:
        return web.json_response(
            data={"error": f"Preset '{preset}' does not provide a download_archive."},
            status=web.HTTPBadRequest.status_code,
        )

    items, invalid = _normalize_ids((post or {}).get("items", [])) if isinstance(post, dict) else ([], [])
    if invalid:
        return web.json_response(
            data={"error": "invalid ids provided.", "invalid_items": invalid},
            status=web.HTTPBadRequest.status_code,
        )
    if len(items) < 1:
        return web.json_response(
            data={"error": "items is required and must be a non-empty list."}, status=web.HTTPBadRequest.status_code
        )

    try:
        status: bool = Archiver.get_instance().delete(archive_file, items)
        return web.json_response(
            data={"file": archive_file, "status": status, "items": items},
            status=web.HTTPOk.status_code if status else web.HTTPNotModified.status_code,
        )
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": f"Failed to delete items from archive for preset '{preset}'.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
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
        return web.json_response(data={"error": "args param is required."}, status=web.HTTPBadRequest.status_code)

    try:
        response = {"opts": {}, "output_template": None, "download_path": None}

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
        return web.json_response(
            data={"error": f"Failed to parse command options for yt-dlp. '{err}'."},
            status=web.HTTPBadRequest.status_code,
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
        return web.json_response(
            data={"status": False, "message": "URL is required.", "error": "URL is required."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validate_url(url, allow_internal=config.allow_internal_urls)
    except ValueError as e:
        return web.json_response(
            data={"status": False, "message": str(e), "error": str(e)},
            status=web.HTTPBadRequest.status_code,
        )

    opts: YTDLPOpts = YTDLPOpts.get_instance()

    preset: str = request.query.get("preset", config.default_preset)
    if not Presets.get_instance().get(preset):
        msg: str = f"Preset '{preset}' does not exist."
        return web.json_response(
            data={"status": False, "message": msg, "error": msg},
            status=web.HTTPBadRequest.status_code,
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
            return web.json_response(
                data={"error": f"Failed to parse command options for yt-dlp. '{err}'."},
                status=web.HTTPBadRequest.status_code,
            )

    try:
        key: str = cache.hash(f"{preset}:{url}:{cli_args or ''}")

        if cache.has(key) and not request.query.get("force", False):
            data: Any | None = cache.get(key)
            data["_cached"] = {
                "status": "hit",
                "preset": preset,
                "cli_args": cli_args,
                "key": key,
                "ttl": data.get("_cached", {}).get("ttl", 300),
                "ttl_left": data.get("_cached", {}).get("expires", time.time() + 300) - time.time(),
                "expires": data.get("_cached", {}).get("expires", time.time() + 300),
            }
            return web.json_response(body=json.dumps(data, indent=4, default=str), status=web.HTTPOk.status_code)

        ytdlp_opts: dict = opts.get_all()

        (data, logs) = await fetch_info(
            config=ytdlp_opts,
            url=url,
            debug=False,
            no_archive=True,
            follow_redirect=True,
            sanitize_info=True,
            capture_logs=logging.WARNING,
        )

        if not data or not isinstance(data, dict):
            return web.json_response(
                data={
                    "status": False,
                    "error": f"Failed to extract video info. {'. '.join(logs)}",
                    "message": "Failed to extract video info.",
                },
                status=web.HTTPInternalServerError.status_code,
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

        data["is_archived"] = False

        archive_file: str | None = ytdlp_opts.get("download_archive")
        data["archive_file"] = archive_file or None

        if archive_file and (archive_id := get_archive_id(url=url).get("archive_id")):
            data["archive_id"] = archive_id
            data["is_archived"] = len(archive_read(archive_file, [archive_id])) > 0

        data = OrderedDict(sorted(data.items(), key=lambda item: len(str(item[1]))))

        cache.set(key=key, value=data, ttl=300)

        return web.json_response(body=json.dumps(data, indent=4, default=str), status=web.HTTPOk.status_code)
    except Exception as e:
        LOG.exception(e)
        LOG.error(f"Error encountered while getting video info for '{url}'. '{e!s}'.")
        return web.json_response(
            data={
                "error": "failed to get video info.",
                "message": str(e),
                "formats": [],
            },
            status=web.HTTPInternalServerError.status_code,
        )


@route("GET", "api/yt-dlp/options/", "get_options")
async def get_options() -> Response:
    """
    Get the yt-dlp CLI options.

    Returns:
        Response: The response object with the yt-dlp CLI options.

    """
    from app.features.ytdlp.ytdlp import ytdlp_options

    return web.json_response(body=json.dumps(ytdlp_options(), indent=4, default=str), status=web.HTTPOk.status_code)


@route("POST", "api/yt-dlp/archive_id/", "get_archive_ids")
async def get_archive_ids(request: Request, config: Config) -> Response:
    """
    Get the archive IDs for the given URLs.

    Returns:
        Response: The response object with the yt-dlp CLI options.

    """
    data = (await request.json()) if request.body_exists else None
    if not data or not isinstance(data, list):
        return web.json_response(
            data={"error": "Invalid request. expecting list with URLs."},
            status=web.HTTPBadRequest.status_code,
        )

    response = []

    for i, url in enumerate(data):
        dct = {"index": i, "url": url}
        try:
            validate_url(url, allow_internal=config.allow_internal_urls)
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
        return web.json_response(data={"error": "Console is disabled."}, status=web.HTTPForbidden.status_code)

    data = (await request.json()) if request.body_exists else None
    if not data or not isinstance(data, dict):
        return web.json_response(
            data={"error": "Invalid request. expecting JSON body."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        it = Item.format(data)
    except ValueError as e:
        return web.json_response(data={"error": str(e), "data": data}, status=web.HTTPBadRequest.status_code)

    try:
        command, info = YTDLPCli(item=it, config=config).build()
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": "Failed to build CLI command"},
            status=web.HTTPBadRequest.status_code,
        )

    if request.query.get("full", False):
        return web.json_response(data=info, status=web.HTTPOk.status_code, dumps=encoder.encode)

    return web.json_response(data={"command": command}, status=web.HTTPOk.status_code)
