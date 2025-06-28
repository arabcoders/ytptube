import asyncio
import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

import anyio
from aiohttp import web
from aiohttp.web import Request, Response

from app.library.cache import Cache
from app.library.config import Config
from app.library.Presets import Preset, Presets
from app.library.router import route
from app.library.Utils import REMOVE_KEYS, arg_converter, extract_info, validate_url
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

    preset: str = request.query.get("preset", config.default_preset)
    exists: Preset | None = Presets.get_instance().get(preset)
    if not exists:
        msg: str = f"Preset '{preset}' does not exist."
        return web.json_response(
            data={"status": False, "message": msg, "error": msg},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        key: str = cache.hash(f"{preset}:{url}")

        if cache.has(key) and not request.query.get("force", False):
            data: Any | None = cache.get(key)
            data["_cached"] = {
                "status": "hit",
                "preset": preset,
                "key": key,
                "ttl": data.get("_cached", {}).get("ttl", 300),
                "ttl_left": data.get("_cached", {}).get("expires", time.time() + 300) - time.time(),
                "expires": data.get("_cached", {}).get("expires", time.time() + 300),
            }
            return web.Response(body=json.dumps(data, indent=4, default=str), status=web.HTTPOk.status_code)

        opts: dict = {}

        if ytdlp_proxy := config.get_ytdlp_args().get("proxy", None):
            opts["proxy"] = ytdlp_proxy

        ytdlp_opts: dict = YTDLPOpts.get_instance().preset(name=preset).add(opts).get_all()

        data = extract_info(
            config=ytdlp_opts,
            url=url,
            debug=False,
            no_archive=True,
            follow_redirect=True,
            sanitize_info=True,
        )

        if "formats" in data:
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
            "key": key,
            "ttl": 300,
            "ttl_left": 300,
            "expires": time.time() + 300,
        }

        data = OrderedDict(sorted(data.items(), key=lambda item: len(str(item[1]))))

        cache.set(key=key, value=data, ttl=300)

        return web.Response(body=json.dumps(data, indent=4, default=str), status=web.HTTPOk.status_code)
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


@route("GET", "api/yt-dlp/archive/recheck/", "archive_recheck")
async def archive_recheck(cache: Cache) -> Response:
    """
    Recheck the manual archive entries.

    Args:
        cache (Cache): The cache instance.

    Returns:
        Response: The response object

    """
    config: Config = Config.get_instance()
    if not config.manual_archive:
        return web.json_response(data={"error": "Manual archive is not enabled."}, status=web.HTTPNotFound.status_code)

    manual_archive = Path(config.manual_archive)
    if not manual_archive.exists():
        return web.json_response(
            data={"error": "Manual archive file not found.", "file": manual_archive},
            status=web.HTTPNotFound.status_code,
        )

    tasks: list = []
    response: list = []

    def info_wrapper(id: str, url: str) -> tuple[str, dict]:
        try:
            return (
                id,
                extract_info(
                    config={
                        "proxy": config.get_ytdlp_args().get("proxy", None),
                        "simulate": True,
                        "dump_single_json": True,
                    },
                    url=url,
                    no_archive=True,
                ),
            )
        except Exception as e:
            return (id, {"error": str(e)})

    async with await anyio.open_file(manual_archive) as f:
        # line format is "youtube ID - at: ISO8601"
        async for line in f:
            line = line.strip()

            if not line or not line.startswith("youtube"):
                continue

            id = line.split(" ")[1].strip()

            if not id:
                continue

            url = f"https://www.youtube.com/watch?v={id}"
            key = cache.hash(id)

            if cache.has(key):
                data = cache.get(key)
                response.append({id: bool(data.get("id", None)) if isinstance(data, dict) else False})
                continue

            tasks.append(
                asyncio.get_event_loop().run_in_executor(None, lambda i=id, url=url: info_wrapper(id=i, url=url))
            )

    if len(tasks) > 0:
        results = await asyncio.gather(*tasks)
        for data in results:
            if not data:
                continue

            id, info = data
            cache.set(key=cache.hash(id), value=info, ttl=3600 * 6)
            response.append({id: bool(data.get("id", None)) if isinstance(data, dict) else False})

    return web.json_response(data=response, status=web.HTTPOk.status_code)
