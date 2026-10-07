from __future__ import annotations

import json
import math
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import anyio
from aiohttp import web

from app.features.auth.middleware import AUTH_USER_KEY
from app.features.core.utils import api_error_response
from app.features.streaming.service import Player, PlayerError, PlayerManager
from app.features.streaming.types import FFProbeError, StreamingError
from app.features.streaming.utils import SEGMENT_DURATION, PreparationBusyError, SegmentIndexError, segment_window
from app.library.cache import Cache
from app.library.logging import get_logger
from app.library.router import route
from app.library.Utils import get_file_sidecar, get_mime_type
from app.routes.api.download import file_response

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

LOG = get_logger()


def _key(request: web.Request, cache: Cache) -> str:
    user = request.get(AUTH_USER_KEY)
    identity = str(user["id"]) if isinstance(user, dict) and "id" in user else "shared"
    return cache.hash(f"playback:{identity}:{request.match_info['media_id']}")


@route("GET", "api/playback/{media_id}", "playback_get", same_origin=True)
async def playback_get(request: web.Request, cache: Cache) -> web.Response:
    key = _key(request, cache)
    return web.json_response({"position": cache.get(key)}, headers={"Cache-Control": "no-store"})


@route("PUT", "api/playback/{media_id}", "playback_put", same_origin=True)
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


def owner(request: web.Request) -> str:
    user = request.get(AUTH_USER_KEY)
    return str(user["id"]) if isinstance(user, dict) and "id" in user else "shared"


def player_errors[**P](
    handler: Callable[P, Awaitable[web.StreamResponse]],
) -> Callable[P, Awaitable[web.StreamResponse]]:
    @wraps(handler)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> web.StreamResponse:
        try:
            return await handler(*args, **kwargs)
        except web.HTTPException:
            raise
        except SegmentIndexError:
            return api_error_response("Segment index is outside the media duration.", code="NOT_FOUND", status=404)
        except PreparationBusyError:
            return api_error_response("Media preparation is busy.", code="UNAVAILABLE", status=503)
        except PlayerError as exc:
            code = {404: "NOT_FOUND", 409: "CONFLICT", 410: "EXPIRED", 503: "UNAVAILABLE"}.get(exc.status, "INVALID")
            return api_error_response(str(exc), code=code, status=exc.status)
        except (ValueError, TypeError, OverflowError):
            return api_error_response("Invalid player options.", code="INVALID", status=400)
        except (FFProbeError, StreamingError, TimeoutError, OSError):
            LOG.exception("Player preparation failed.")
            return api_error_response("Unable to prepare playback.", code="INTERNAL_ERROR", status=502)

    return wrapped


def payload(player: Player, players: PlayerManager) -> dict:
    probe = player.resource.probe
    assert probe is not None
    file = player.resource.file
    images = get_file_sidecar(file).get("image", [])
    poster = (
        file.with_name(images[0]["file"].name).relative_to(Path(players.config.download_path).resolve()).as_posix()
        if images
        else None
    )
    base = f"{players.config.base_path.rstrip('/')}/api/player/media/{player.resource.id}"
    tracks = players.tracks(player)
    subtitles = []
    for id, track in tracks.items():
        entry = dict(track)
        entry["url"] = f"{base}/subtitles/{id}" if track["renderer"] in {"native", "assjs"} else ""
        subtitles.append(entry)
    return {
        "player_id": player.id,
        "media_url": f"{base}/file",
        "generation": list(player.resource.identity),
        "expires_in": 900,
        "audio_stream_index": player.audio,
        "subtitle_track_id": player.subtitle,
        "ffprobe": probe.serialize(),
        "title": file.stem,
        "mimetype": get_mime_type(probe.metadata, file),
        "poster": poster,
        "audio_tracks": [
            {
                "stream_index": s.index,
                "lang": getattr(s, "tags", {}).get("language", "und"),
                "name": getattr(s, "tags", {}).get("title", ""),
                "codec": s.codec() or "unknown",
                "channels": getattr(s, "channels", None),
                "channel_layout": getattr(s, "channel_layout", ""),
                "default": bool(getattr(s, "disposition", {}).get("default", 0)),
            }
            for s in probe.audio
        ],
        "subtitles": subtitles,
        "fonts": [{"id": f"f{s.index}", "url": f"{base}/fonts/f{s.index}"} for s in players.fonts(player)],
        "stream_url": f"{base}/stream.m3u8?{urlencode({'audio': player.audio if player.audio is not None else 'auto', 'subtitle': player.subtitle or 'off'})}",
    }


@route("POST", "api/player/open/{file:.*}", "player_open")
@player_errors
async def player_open(request: web.Request, players: PlayerManager) -> web.Response:
    file = request.match_info["file"]
    if not file:
        msg = "Media filename is required."
        raise PlayerError(msg)
    player = await players.open(owner(request), file)
    return web.json_response(payload(player, players), headers={"Cache-Control": "private, no-store"})


@route("PUT", "api/player/leases/{id}", "player_refresh")
@player_errors
async def player_refresh(request: web.Request, players: PlayerManager) -> web.Response:
    body = await request.json()
    if not isinstance(body, dict) or set(body) - {"audio_stream_index", "subtitle_track_id"}:
        msg = "Invalid player options."
        raise PlayerError(msg)
    player = await players.get(request.match_info["id"], owner(request))
    players.select(player, body.get("audio_stream_index", player.audio), body.get("subtitle_track_id", player.subtitle))
    return web.json_response(payload(player, players), headers={"Cache-Control": "private, no-store"})


@route("DELETE", "api/player/leases/{id}", "player_close")
@player_errors
async def player_close(request: web.Request, players: PlayerManager) -> web.Response:
    await players.close(request.match_info["id"], owner(request))
    return web.Response(status=204, headers={"Cache-Control": "private, no-store"})


def selection(request: web.Request, player: Player, players: PlayerManager) -> tuple[int | None, int | None]:
    audio_arg = request.query.get("audio", "auto")
    audio = None if audio_arg == "auto" else int(audio_arg)
    subtitle = request.query.get("subtitle", "off")
    probe = player.resource.probe
    assert probe is not None
    if audio is not None and not any(s.index == audio for s in probe.audio):
        msg = "Unknown audio track."
        raise PlayerError(msg)
    track = players.tracks(player).get(subtitle) if subtitle != "off" else None
    if subtitle != "off" and track is None:
        msg = "Unknown subtitle track."
        raise PlayerError(msg)
    if track and track["renderer"] == "unsupported":
        msg = "This subtitle format is not supported."
        raise PlayerError(msg)
    bitmap = int(subtitle[1:]) if track and track["renderer"] == "bitmap" else None
    return audio, bitmap


@route("GET", "api/player/media/{media}/stream.m3u8", "player_stream")
@player_errors
async def player_stream(request: web.Request, players: PlayerManager) -> web.Response:
    player = await players.media(request.match_info["media"], owner(request))
    selection(request, player, players)
    probe = player.resource.probe
    assert probe is not None
    duration = float(probe.metadata["duration"])
    query = urlencode({"audio": request.query.get("audio", "auto"), "subtitle": request.query.get("subtitle", "off")})
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-TARGETDURATION:{math.ceil(SEGMENT_DURATION)}",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXT-X-PLAYLIST-TYPE:VOD",
    ]
    for index in range(math.ceil(duration / SEGMENT_DURATION)):
        _, length = segment_window(index, duration)
        lines += [f"#EXTINF:{length:.6f},", f"segments/{index}.ts?{query}"]
    lines.append("#EXT-X-ENDLIST")
    return web.Response(
        text="\n".join(lines),
        content_type="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "private, max-age=300"},
    )


@route("GET", "api/player/media/{media}/file", "player_media")
@route("HEAD", "api/player/media/{media}/file", "player_media_head")
@player_errors
async def player_media(request: web.Request, players: PlayerManager) -> web.FileResponse:
    player = await players.media(request.match_info["media"], owner(request))
    response = file_response(player.resource.file)
    response.headers["Cache-Control"] = "private, max-age=300"
    return response


@route("GET", r"api/player/media/{media}/segments/{index:\d+}.ts", "player_segment")
@route("GET", "api/player/media/{media}/subtitles/{track}", "player_subtitle")
@route("GET", "api/player/media/{media}/fonts/{font}", "player_font")
@player_errors
async def player_artifact(request: web.Request, players: PlayerManager) -> web.StreamResponse:
    player = await players.media(request.match_info["media"], owner(request))
    if "index" in request.match_info:
        audio, bitmap = selection(request, player, players)
        index = int(request.match_info["index"])
        assert player.resource.probe is not None
        segment_window(index, float(player.resource.probe.metadata["duration"]))
        key = ("segment", index, audio, bitmap)
    elif "track" in request.match_info:
        track = request.match_info["track"]
        if track not in players.tracks(player):
            msg = "Unknown subtitle track."
            raise PlayerError(msg, 404)
        key = ("subtitle", track)
    else:
        key = ("font", request.match_info["font"])
    async with players.artifact(player, key, shared=True) as artifact:
        headers = {
            "Content-Type": artifact.content_type,
            "Content-Length": str(artifact.size),
            "Cache-Control": "private, max-age=300",
        }
        if artifact.metadata is not None:
            headers["X-YTP-Font"] = json.dumps(artifact.metadata, ensure_ascii=True)
        response = web.StreamResponse(headers=headers)
        await players.check(player, shared=True)
        try:
            await response.prepare(request)
            async with await anyio.open_file(artifact.file, "rb") as output:
                while chunk := await output.read(65536):
                    await players.check(player, shared=True)
                    await response.write(chunk)
            await players.check(player, shared=True)
            await response.write_eof()
        except (PlayerError, ConnectionError):
            response.force_close()
            if request.transport is not None:
                request.transport.close()
        return response
