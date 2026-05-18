import logging
import random
from typing import Any
from urllib.parse import urlparse, urlsplit, urlunsplit

from aiohttp import web
from aiohttp.web import Request, Response

from app.features.ytdlp.ytdlp_opts import YTDLPOpts
from app.library.ag_utils import ag
from app.library.cache import Cache
from app.library.config import Config
from app.library.httpx_client import Globals, build_request_headers, get_async_client, resolve_curl_transport
from app.library.router import route

LOG: logging.Logger = logging.getLogger(__name__)

IS_REQUESTING_BACKGROUND: bool = False


def _safe_url(url: str | None) -> str:
    if not url:
        return ""

    try:
        parsed = urlsplit(url)
    except Exception:
        return str(url)

    netloc: str = parsed.netloc
    if parsed.username or parsed.password:
        host: str = parsed.hostname or ""
        if parsed.port:
            host: str = f"{host}:{parsed.port}"
        netloc: str = f"redacted:redacted@{host}" if host else "redacted:redacted"

    query: str = "redacted" if parsed.query else ""
    fragment: str = "redacted" if parsed.fragment else ""
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, fragment))


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
        backend: str = random.choice(config.pictures_backends)
        safe_backend: str = _safe_url(backend)
        CACHE_KEY_BING = "random_background_bing"
        CACHE_KEY = "random_background"

        if cache.has(CACHE_KEY) and not request.query.get("force", False):
            cached_data = await cache.aget(CACHE_KEY)
            if isinstance(cached_data, dict):
                cached_headers = cached_data.get("headers")
                if not isinstance(cached_headers, dict):
                    cached_headers = {}
                cached_headers = {str(key): str(value) for key, value in cached_headers.items()}
                cached_backend = cached_data.get("backend")
                if not isinstance(cached_backend, str):
                    cached_backend = "" if cached_backend is None else str(cached_backend)
                return web.Response(
                    body=cached_data.get("content"),
                    headers={
                        "X-Cache": "HIT",
                        "X-Cache-TTL": str(await cache.attl(CACHE_KEY)),
                        "X-Image-Via": cached_backend,
                        **cached_headers,
                    },
                )

        ytdlp_args: dict = YTDLPOpts.get_instance().preset(name=config.default_preset).get_all()
        use_curl: bool = resolve_curl_transport()
        request_headers: dict = build_request_headers(
            user_agent=request.headers.get("User-Agent", ytdlp_args.get("user_agent", Globals.get_random_agent())),
            use_curl=use_curl,
        )
        proxy: str | None = ytdlp_args.get("proxy")

        client = get_async_client(proxy=proxy, use_curl=use_curl)
        if backend.startswith("https://www.bing.com/HPImageArchive.aspx"):
            if not cache.has(CACHE_KEY_BING):
                response = await client.request(method="GET", url=backend, headers=request_headers)
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

                backend: str = f"https://www.bing.com{img_url}"
                safe_backend: str = _safe_url(backend)
                await cache.aset(key=CACHE_KEY_BING, value=backend, ttl=3600 * 24)
            else:
                backend = await cache.aget(CACHE_KEY_BING)
                safe_backend = _safe_url(backend if isinstance(backend, str) else None)

        if not isinstance(backend, str) or not backend:
            return web.json_response(
                data={"error": "failed to retrieve the random background image."},
                status=web.HTTPInternalServerError.status_code,
            )

        LOG.debug(f"Requesting random picture from '{safe_backend}'.")

        response = await client.request(
            method="GET",
            url=backend,
            follow_redirects=True,
            headers=request_headers,
        )

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
        response_headers: dict[str, str] = data["headers"]
        image_via = str(data.get("backend") or "")

        await cache.aset(key=CACHE_KEY, value=data, ttl=3600)

        LOG.debug(f"Random background image from '{safe_backend}' cached.")

        return web.Response(
            body=data.get("content"),
            headers={
                "X-Cache": "MISS",
                "X-Cache-TTL": "3600",
                "X-Image-Via": image_via,
                **response_headers,
            },
        )
    except Exception as e:
        LOG.error(f"Failed to request random background image from '{safe_backend}'. '{e!s}'.")
        return web.json_response(
            data={"error": "failed to retrieve the random background image."},
            status=web.HTTPInternalServerError.status_code,
        )
    finally:
        IS_REQUESTING_BACKGROUND = False
