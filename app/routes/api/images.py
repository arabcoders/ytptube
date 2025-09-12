import logging
import random
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from aiohttp import web
from aiohttp.web import Request, Response
from yt_dlp.utils.networking import random_user_agent

from app.library.ag_utils import ag
from app.library.cache import Cache
from app.library.config import Config
from app.library.router import route
from app.library.Utils import validate_url
from app.library.YTDLPOpts import YTDLPOpts

LOG: logging.Logger = logging.getLogger(__name__)

IS_REQUESTING_BACKGROUND: bool = False


@route("GET", "api/thumbnail/", "get_thumbnail")
async def get_thumbnail(request: Request, config: Config) -> Response:
    """
    Get the thumbnail.

    Args:
        request (Request): The request object.
        config (Config): The configuration object.

    Returns:
        Response: The response object.

    """
    url: str | None = request.query.get("url")
    if not url:
        return web.json_response(data={"error": "URL is required."}, status=web.HTTPForbidden.status_code)

    try:
        validate_url(url)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPForbidden.status_code)

    try:
        ytdlp_args: dict = YTDLPOpts.get_instance().preset(name=config.default_preset).get_all()
        opts: dict[str, Any] = {
            "headers": {
                "User-Agent": request.headers.get("User-Agent", ytdlp_args.get("user_agent", random_user_agent())),
            },
        }

        if proxy := ytdlp_args.get("proxy"):
            opts["proxy"] = proxy

        try:
            from httpx_curl_cffi import AsyncCurlTransport, CurlOpt

            opts["transport"] = AsyncCurlTransport(
                impersonate="chrome",
                default_headers=True,
                curl_options={CurlOpt.FRESH_CONNECT: True},
            )
            opts.pop("headers", None)
        except Exception:
            pass

        async with httpx.AsyncClient(**opts) as client:
            LOG.debug(f"Fetching thumbnail from '{url}'.")
            response = await client.request(method="GET", url=url, follow_redirects=True)

            return web.Response(
                body=response.content,
                headers={
                    "Content-Type": response.headers.get("Content-Type"),
                    "Pragma": "public",
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": f"public, max-age={time.time() + 31536000}",
                    "Expires": time.strftime(
                        "%a, %d %b %Y %H:%M:%S GMT",
                        datetime.fromtimestamp(time.time() + 31536000, tz=UTC).timetuple(),
                    ),
                },
            )
    except Exception as e:
        LOG.error(f"Error fetching thumbnail from '{url}'. '{e}'.")
        return web.json_response(
            data={"error": "failed to retrieve the thumbnail."}, status=web.HTTPInternalServerError.status_code
        )


@route("GET", "api/random/background/", "get_background")
async def get_background(request: Request, config: Config, cache: Cache) -> Response:
    """
    Get random background.

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        cache (Cache): The cache object.

    Returns:
        Response: The response object.

    """
    global IS_REQUESTING_BACKGROUND  # noqa: PLW0603

    backend = None

    if IS_REQUESTING_BACKGROUND:
        return web.Response(status=web.HTTPTooManyRequests.status_code)

    try:
        IS_REQUESTING_BACKGROUND = True
        backend = random.choice(config.pictures_backends)  # noqa: S311
        CACHE_KEY_BING = "random_background_bing"
        CACHE_KEY = "random_background"

        if cache.has(CACHE_KEY) and not request.query.get("force", False):
            data = await cache.aget(CACHE_KEY)
            return web.Response(
                body=data.get("content"),
                headers={
                    "X-Cache": "HIT",
                    "X-Cache-TTL": str(await cache.attl(CACHE_KEY)),
                    "X-Image-Via": data.get("backend"),
                    **data.get("headers"),
                },
            )

        ytdlp_args: dict = YTDLPOpts.get_instance().preset(name=config.default_preset).get_all()
        opts: dict[str, Any] = {
            "headers": {
                "User-Agent": request.headers.get("User-Agent", ytdlp_args.get("user_agent", random_user_agent())),
            },
        }

        if proxy := ytdlp_args.get("proxy"):
            opts["proxy"] = proxy

        try:
            from httpx_curl_cffi import AsyncCurlTransport, CurlOpt

            opts["transport"] = AsyncCurlTransport(
                impersonate="chrome",
                default_headers=True,
                curl_options={CurlOpt.FRESH_CONNECT: True},
            )
            opts.pop("headers", None)
        except Exception:
            pass

        async with httpx.AsyncClient(**opts) as client:
            if backend.startswith("https://www.bing.com/HPImageArchive.aspx"):
                if not cache.has(CACHE_KEY_BING):
                    response = await client.request(method="GET", url=backend)
                    if response.status_code != web.HTTPOk.status_code:
                        return web.json_response(
                            data={"error": "failed to retrieve the random background image."},
                            status=web.HTTPInternalServerError.status_code,
                        )

                    img_url: str | None = ag(response.json(), "images.0.url")
                    if not img_url:
                        return web.json_response(
                            data={"error": "failed to retrieve the random background image."},
                            status=web.HTTPInternalServerError.status_code,
                        )

                    backend = f"https://www.bing.com{img_url}"
                    await cache.aset(key=CACHE_KEY_BING, value=backend, ttl=3600 * 24)
                else:
                    backend: str = await cache.aget(CACHE_KEY_BING)

            LOG.debug(f"Requesting random picture from '{backend!s}'.")

            response = await client.request(method="GET", url=backend, follow_redirects=True)

            if response.status_code != web.HTTPOk.status_code:
                return web.json_response(
                    data={"error": "failed to retrieve the random background image."},
                    status=web.HTTPInternalServerError.status_code,
                )

            data: dict[str, Any] = {
                "content": response.content,
                "backend": urlparse(backend).netloc,
                "headers": {
                    "Content-Type": response.headers.get("Content-Type", "image/jpeg"),
                    "Content-Length": str(len(response.content)),
                },
            }

            await cache.aset(key=CACHE_KEY, value=data, ttl=3600)

            LOG.debug(f"Random background image from '{backend!s}' cached.")

            return web.Response(
                body=data.get("content"),
                headers={
                    "X-Cache": "MISS",
                    "X-Cache-TTL": "3600",
                    "X-Image-Via": data.get("backend"),
                    **data.get("headers"),
                },
            )
    except Exception as e:
        LOG.error(f"Failed to request random background image from '{backend!s}'.'. '{e!s}'.")
        return web.json_response(
            data={"error": "failed to retrieve the random background image."},
            status=web.HTTPInternalServerError.status_code,
        )
    finally:
        IS_REQUESTING_BACKGROUND = False
