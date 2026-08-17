import time
from datetime import UTC, datetime
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response
from aiohttp.web_response import StreamResponse

from app.features.core.utils import api_error_response
from app.features.streaming.library.ffprobe import ffmpeg_bin, ffprobe_bin
from app.features.streaming.library.m3u8 import M3u8
from app.features.streaming.library.playlist import Playlist
from app.features.streaming.library.segments import Segments
from app.features.streaming.library.subtitle import Subtitle, get_subtitle_tracks
from app.features.streaming.types import FFProbeError, StreamingError
from app.library.config import Config
from app.library.log import get_logger
from app.library.router import route
from app.library.Utils import get_file

LOG = get_logger()


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
    file: str | None = request.match_info.get("file")

    if not file:
        return api_error_response(
            "file is required",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.file"},
        )

    base_path: str = config.base_path.rstrip("/")

    if ffprobe_bin() is None:
        return api_error_response(
            "ffprobe is not available on this system.",
            code="FFPROBE_UNAVAILABLE",
            status=web.HTTPServiceUnavailable.status_code,
        )

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
            return api_error_response(
                f"File '{file}' does not exist.",
                code="NOT_FOUND",
                status=status,
                params={"resource": "api.resources.file"},
            )

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
        return api_error_response(
            str(e),
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.file"},
            detail=str(e),
        )
    except FFProbeError:
        return api_error_response(
            "Unable to read media metadata.",
            code="INTERNAL_ERROR",
            status=web.HTTPInternalServerError.status_code,
        )


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
    file: str | None = request.match_info.get("file")
    mode: str | None = request.match_info.get("mode")

    if mode not in ["video", "subtitle"]:
        return api_error_response(
            "Only video and subtitle modes are supported.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.mode"},
        )

    if not file:
        return api_error_response(
            "file is required",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.file"},
        )

    duration: float | None = None
    duration_arg = request.query.get("duration", None)

    if "subtitle" in mode:
        if not duration_arg:
            return api_error_response(
                "duration is required.",
                code="REQUIRED",
                status=web.HTTPBadRequest.status_code,
                params={"field": "api.fields.duration"},
            )

        duration = float(duration_arg)

    base_path: str = config.base_path.rstrip("/")

    if "video" in mode and ffprobe_bin() is None:
        return api_error_response(
            "ffprobe is not available on this system.",
            code="FFPROBE_UNAVAILABLE",
            status=web.HTTPServiceUnavailable.status_code,
        )

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
            return api_error_response(
                f"File '{file}' does not exist.",
                code="NOT_FOUND",
                status=status,
                params={"resource": "api.resources.file"},
            )

        if "subtitle" in mode:
            if duration is None:
                return api_error_response(
                    "duration is required.",
                    code="REQUIRED",
                    status=web.HTTPBadRequest.status_code,
                    params={"field": "api.fields.duration"},
                )
            text = await cls.make_subtitle(file=realFile, duration=duration)
        else:
            text = await cls.make_stream(file=realFile)
    except StreamingError as e:
        LOG.exception(
            "Failed to create %s streaming playlist for '%s': %s.",
            mode,
            file,
            e,
            extra={"route": "streaming.playlist", "file_path": file, "mode": mode, "exception_type": type(e).__name__},
        )
        return api_error_response(
            str(e),
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.file"},
            detail=str(e),
        )
    except FFProbeError:
        return api_error_response(
            "Unable to read media metadata.",
            code="INTERNAL_ERROR",
            status=web.HTTPInternalServerError.status_code,
        )

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
async def segments_stream(request: Request, config: Config, app: web.Application) -> StreamResponse:
    """
    Get the segments.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        app (web.Application): The aiohttp application instance.

    Returns:
        Response: The response object.

    """
    file: str | None = request.match_info.get("file")
    segment: str | None = request.match_info.get("segment")
    sd: str | None = request.query.get("sd")
    vc: int = int(request.query.get("vc", 0))
    ac: int = int(request.query.get("ac", 0))

    if not file:
        return api_error_response(
            "file is required",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.file"},
        )

    if not segment:
        return api_error_response(
            "segment id is required.",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.segmentId"},
        )

    realFile, status = get_file(download_path=config.download_path, file=file)
    if web.HTTPFound.status_code == status:
        return Response(
            status=status,
            headers={
                "Location": str(
                    app.router["segments_stream"].url_for(
                        segment=segment,
                        file=str(realFile).replace(config.download_path, "").strip("/"),
                    )
                ),
            },
        )

    if web.HTTPNotFound.status_code == status:
        return api_error_response(
            f"File '{file}' does not exist.",
            code="NOT_FOUND",
            status=status,
            params={"resource": "api.resources.file"},
        )

    mtime = realFile.stat().st_mtime

    if request.if_modified_since and request.if_modified_since.timestamp() == mtime:
        lastMod = time.strftime("%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple())
        return web.Response(status=web.HTTPNotModified.status_code, headers={"Last-Modified": lastMod})

    if ffmpeg_bin() is None:
        return api_error_response(
            "ffmpeg is not available on this system.",
            code="FFMPEG_UNAVAILABLE",
            status=web.HTTPServiceUnavailable.status_code,
        )

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

    try:
        await Segments(
            download_path=config.download_path,
            index=int(segment),
            duration=float(f"{float(sd or M3u8.duration):.6f}"),
            vconvert=vc == 1,
            aconvert=ac == 1,
        ).stream(realFile, resp)
    except StreamingError as e:
        LOG.warning(
            "Failed to stream segment %s for '%s': %s.",
            segment,
            file,
            e,
            extra={"route": "streaming.segments", "file_path": file, "segment": segment, "error": str(e)},
        )
        try:
            await resp.write_eof()
        except (ConnectionResetError, BrokenPipeError, RuntimeError):
            pass
        return resp

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
    file: str | None = request.match_info.get("file")

    if not file:
        return api_error_response(
            "file is required",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.file"},
        )

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
        return api_error_response(
            f"File '{file}' does not exist.",
            code="NOT_FOUND",
            status=status,
            params={"resource": "api.resources.file"},
        )

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


@route("GET", "api/player/subtitles/manifest/{file:.*}", "subtitles_manifest_get")
async def subtitles_manifest_get(request: Request, config: Config, app: web.Application) -> Response:
    """
    Get subtitle track metadata for a media file.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        app (web.Application): The aiohttp application instance.

    Returns:
        Response: The response object.

    """
    file: str | None = request.match_info.get("file")

    if not file:
        return api_error_response(
            "file is required",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.file"},
        )

    realFile, status = get_file(download_path=config.download_path, file=file)
    if web.HTTPFound.status_code == status:
        return Response(
            status=status,
            headers={
                "Location": str(
                    app.router["subtitles_manifest_get"].url_for(
                        file=str(realFile).replace(config.download_path, "").strip("/")
                    )
                ),
            },
        )

    if web.HTTPNotFound.status_code == status:
        return api_error_response(
            f"File '{file}' does not exist.",
            code="NOT_FOUND",
            status=status,
            params={"resource": "api.resources.file"},
        )

    tracks = [
        {
            "lang": track.lang,
            "name": track.name,
            "source_format": track.source_format,
            "delivery_format": track.delivery_format,
            "renderer": track.renderer,
            "url": str(
                app.router["subtitles_track_get"].url_for(
                    source_format=track.source_format,
                    file=str(track.file).replace(config.download_path, "").strip("/"),
                )
            ),
        }
        for track in get_subtitle_tracks(realFile)
    ]

    return web.json_response(data={"subtitles": tracks}, status=web.HTTPOk.status_code)


@route("GET", "api/player/subtitles/{source_format}/{file:.*}", "subtitles_track_get")
async def subtitles_track_get(request: Request, config: Config, app: web.Application) -> Response:
    """
    Get a subtitle file using its preferred delivery format.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        app (web.Application): The aiohttp application instance.

    Returns:
        Response: The response object.

    """
    file: str | None = request.match_info.get("file")
    source_format: str | None = request.match_info.get("source_format")

    if not file:
        return api_error_response(
            "file is required",
            code="REQUIRED",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.file"},
        )

    fmt = Subtitle.normalize_format(source_format or "")
    if fmt is None:
        return api_error_response(
            "Only vtt, srt, and ass subtitle formats are supported.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.type"},
        )

    realFile, status = get_file(download_path=config.download_path, file=file)
    if web.HTTPFound.status_code == status:
        return Response(
            status=status,
            headers={
                "Location": str(
                    app.router["subtitles_track_get"].url_for(
                        source_format=fmt,
                        file=str(realFile).replace(config.download_path, "").strip("/"),
                    )
                ),
            },
        )

    if web.HTTPNotFound.status_code == status:
        return api_error_response(
            f"File '{file}' does not exist.",
            code="NOT_FOUND",
            status=status,
            params={"resource": "api.resources.file"},
        )

    if Subtitle.normalize_format(realFile.suffix) != fmt:
        return api_error_response(
            f"Subtitle file '{file}' does not match requested source format '{fmt}'.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"field": "api.fields.type"},
        )

    mtime = realFile.stat().st_mtime

    if request.if_modified_since and request.if_modified_since.timestamp() == mtime:
        lastMod = time.strftime("%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple())
        return web.Response(status=web.HTTPNotModified.status_code, headers={"Last-Modified": lastMod})

    body, content_type = await Subtitle().make_delivery(file=realFile)
    return web.Response(
        body=body,
        headers={
            "Content-Type": content_type,
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
