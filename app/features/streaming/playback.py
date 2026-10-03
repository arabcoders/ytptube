from __future__ import annotations

import math

from aiohttp import web

from app.features.auth.middleware import AUTH_USER_KEY
from app.features.core.utils import api_error_response
from app.library.cache import Cache
from app.library.router import route


def _key(request: web.Request, cache: Cache) -> str:
    user = request.get(AUTH_USER_KEY)
    identity = str(user["id"]) if isinstance(user, dict) and "id" in user else "shared"
    return cache.hash(f"playback:{identity}:{request.match_info['media_id']}")


@route("GET", "api/playback/{media_id}", same_origin=True)
async def playback_get(request: web.Request, cache: Cache) -> web.Response:
    key = _key(request, cache)
    return web.json_response({"position": cache.get(key)}, headers={"Cache-Control": "no-store"})


@route("PUT", "api/playback/{media_id}", same_origin=True)
async def playback_put(request: web.Request, cache: Cache) -> web.Response:
    try:
        payload = await request.json()
        if not isinstance(payload, dict) or "position" not in payload:
            return api_error_response("Invalid position.", code="BAD_REQUEST", status=400)
        position = payload["position"]
        if position is not None and (
            not isinstance(position, (int, float))
            or isinstance(position, bool)
            or not math.isfinite(position)
            or position < 0
        ):
            return api_error_response("Invalid position.", code="BAD_REQUEST", status=400)
    except (ValueError, TypeError, OverflowError):
        return api_error_response("Invalid position.", code="BAD_REQUEST", status=400)
    key = _key(request, cache)
    if position is None:
        cache.delete(key)
    else:
        cache.set(key, float(position), ttl=24 * 60 * 60, persist=True)
    return web.json_response({"position": position})
