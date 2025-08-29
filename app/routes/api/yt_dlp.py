import json
import logging
import time
from collections import OrderedDict
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.cache import Cache
from app.library.config import Config
from app.library.Presets import Presets
from app.library.router import route
from app.library.Utils import (
    REMOVE_KEYS,
    archive_read,
    arg_converter,
    extract_info,
    get_archive_id,
    validate_url,
)
from app.library.YTDLPOpts import YTDLPOpts

LOG: logging.Logger = logging.getLogger(__name__)


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

        bad_options = {k: v for d in REMOVE_KEYS for k, v in d.items()}
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
        validate_url(url)
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

        if ytdlp_proxy := config.get_ytdlp_args().get("proxy", None):
            opts = opts.add({"proxy": ytdlp_proxy})

        logs: list = []

        ytdlp_opts: dict = {
            **opts.get_all(),
            "callback": {
                "func": lambda _, msg: logs.append(msg),
                "level": logging.WARNING,
                "name": "callback-logger",
            },
        }

        data = extract_info(
            config=ytdlp_opts,
            url=url,
            debug=False,
            no_archive=True,
            follow_redirect=True,
            sanitize_info=True,
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

        is_archived = False
        if (archive_file := ytdlp_opts.get("download_archive")) and (
            archive_id := get_archive_id(url=url).get("archive_id")
        ):
            is_archived: bool = len(archive_read(archive_file, [archive_id])) > 0

        data["is_archived"] = is_archived

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
    from app.library.ytdlp import ytdlp_options

    return web.json_response(body=json.dumps(ytdlp_options(), indent=4, default=str), status=web.HTTPOk.status_code)


@route("POST", "api/yt-dlp/archive_id/", "get_archive_ids")
async def get_archive_ids(request: Request) -> Response:
    """
    Get the yt-dlp CLI options.

    Returns:
        Response: The response object with the yt-dlp CLI options.

    """
    from app.library.Utils import get_archive_id

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
            validate_url(url)
            dct.update(get_archive_id(url))
        except ValueError as e:
            dct.update({"id": None, "ie_key": None, "archive_id": None, "error": str(e)})

        response.append(dct)

    return web.json_response(data=response, status=web.HTTPOk.status_code)
