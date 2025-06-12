import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.M3u8 import M3u8
from app.library.Playlist import Playlist
from app.library.router import route
from app.library.Segments import Segments
from app.library.Subtitle import Subtitle
from app.library.Utils import StreamingError, get_file

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/player/playlist/{file:.*}.m3u8", "playlist_create")
async def playlist_create(request: Request, config: Config, app: web.Application) -> Response:
    """
    Get the playlist.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        app (web.Application): The aiohttp application instance.

    Returns:
        Response: The response object.

    """
    file: str = request.match_info.get("file")

    if not file:
        return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

    base_path: str = config.base_path.rstrip("/")

    try:
        realFile, status = get_file(download_path=config.download_path, file=file)
        if web.HTTPFound.status_code == status:
            return Response(
                status=web.HTTPFound.status_code,
                headers={
                    "Location": str(
                        app.router["playlist_create"].url_for(
                            file=str(realFile).replace(config.download_path, "").strip("/")
                        )
                    ),
                },
            )

        if web.HTTPNotFound.status_code == status:
            return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

        return web.Response(
            text=await Playlist(download_path=Path(config.download_path), url=f"{base_path}/").make(file=realFile),
            headers={
                "Content-Type": "application/x-mpegURL",
                "Cache-Control": "no-cache",
                "Access-Control-Max-Age": "300",
            },
            status=web.HTTPOk.status_code,
        )
    except StreamingError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPNotFound.status_code)


@route("GET", "api/player/m3u8/{mode}/{file:.*}.m3u8", "m3u8_create")
async def m3u8_create(request: Request, config: Config, app: web.Application) -> Response:
    """
    Get the m3u8 file.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        app (web.Application): The aiohttp application instance.

    Returns:
        Response: The response object.

    """
    file: str = request.match_info.get("file")
    mode: str = request.match_info.get("mode")

    if mode not in ["video", "subtitle"]:
        return web.json_response(
            data={"error": "Only video and subtitle modes are supported."}, status=web.HTTPBadRequest.status_code
        )

    if not file:
        return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

    duration = request.query.get("duration", None)

    if "subtitle" in mode:
        if not duration:
            return web.json_response(data={"error": "duration is required."}, status=web.HTTPBadRequest.status_code)

        duration = float(duration)

    base_path: str = config.base_path.rstrip("/")

    try:
        cls = M3u8(download_path=Path(config.download_path), url=f"{base_path}/")

        realFile, status = get_file(download_path=config.download_path, file=file)
        if web.HTTPFound.status_code == status:
            return Response(
                status=status,
                headers={
                    "Location": str(
                        app.router["m3u8_create"].url_for(
                            mode=mode, file=str(realFile).replace(config.download_path, "").strip("/")
                        )
                    ),
                },
            )

        if web.HTTPNotFound.status_code == status:
            return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

        if "subtitle" in mode:
            text = await cls.make_subtitle(file=realFile, duration=duration)
        else:
            text = await cls.make_stream(file=realFile)
    except StreamingError as e:
        LOG.exception(e)
        return web.json_response(data={"error": str(e)}, status=web.HTTPNotFound.status_code)

    return web.Response(
        text=text,
        headers={
            "Content-Type": "application/x-mpegURL",
            "Cache-Control": "no-cache",
            "Access-Control-Max-Age": "300",
        },
        status=web.HTTPOk.status_code,
    )


@route("GET", r"api/player/segments/{segment:\d+}/{file:.*}.ts", "segments_stream")
async def segments_stream(request: Request, config: Config, app: web.Application) -> Response:
    """
    Get the segments.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        app (web.Application): The aiohttp application instance.

    Returns:
        Response: The response object.

    """
    file: str = request.match_info.get("file")
    segment: int = request.match_info.get("segment")
    sd: int = request.query.get("sd")
    vc: int = int(request.query.get("vc", 0))
    ac: int = int(request.query.get("ac", 0))

    if not file:
        return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

    if not segment:
        return web.json_response(data={"error": "segment id is required."}, status=web.HTTPBadRequest.status_code)

    realFile, status = get_file(download_path=config.download_path, file=file)
    if web.HTTPFound.status_code == status:
        return Response(
            status=status,
            headers={
                "Location": str(
                    app.router["segments"].url_for(
                        segment=segment,
                        file=str(realFile).replace(config.download_path, "").strip("/"),
                    )
                ),
            },
        )

    if web.HTTPNotFound.status_code == status:
        return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

    mtime = realFile.stat().st_mtime

    if request.if_modified_since and request.if_modified_since.timestamp() == mtime:
        lastMod = time.strftime("%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple())
        return web.Response(status=web.HTTPNotModified.status_code, headers={"Last-Modified": lastMod})

    resp = web.StreamResponse(
        status=web.HTTPOk.status_code,
        headers={
            "Content-Type": "video/mpegts",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Pragma": "public",
            "Cache-Control": f"public, max-age={time.time() + 31536000}",
            "Last-Modified": time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple()
            ),
            "Expires": time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(time.time() + 31536000, tz=UTC).timetuple()
            ),
        },
    )

    await resp.prepare(request)

    await Segments(
        download_path=config.download_path,
        index=int(segment),
        duration=float(f"{float(sd if sd else M3u8.duration):.6f}"),
        vconvert=vc == 1,
        aconvert=ac == 1,
    ).stream(realFile, resp)

    return resp


@route("GET", "api/player/subtitle/{file:.*}.vtt", "subtitles_get")
async def subtitles_get(request: Request, config: Config, app: web.Application) -> Response:
    """
    Get the subtitles.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        app (web.Application): The aiohttp application instance.

    Returns:
        Response: The response object.

    """
    file: str = request.match_info.get("file")

    if not file:
        return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

    realFile, status = get_file(download_path=config.download_path, file=file)
    if web.HTTPFound.status_code == status:
        return Response(
            status=status,
            headers={
                "Location": str(
                    app.router["subtitles_get"].url_for(file=str(realFile).replace(config.download_path, "").strip("/"))
                ),
            },
        )

    if web.HTTPNotFound.status_code == status:
        return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

    mtime = realFile.stat().st_mtime

    if request.if_modified_since and request.if_modified_since.timestamp() == mtime:
        lastMod = time.strftime("%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple())
        return web.Response(status=web.HTTPNotModified.status_code, headers={"Last-Modified": lastMod})

    return web.Response(
        body=await Subtitle().make(file=realFile),
        headers={
            "Content-Type": "text/vtt; charset=UTF-8",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Pragma": "public",
            "Cache-Control": f"public, max-age={time.time() + 31536000}",
            "Last-Modified": time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple()
            ),
            "Expires": time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(time.time() + 31536000, tz=UTC).timetuple()
            ),
        },
        status=web.HTTPOk.status_code,
    )
