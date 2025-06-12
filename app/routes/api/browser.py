import logging
from pathlib import Path
from urllib.parse import unquote_plus

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.ffprobe import ffprobe
from app.library.router import route
from app.library.Utils import get_file, get_file_sidecar, get_files, get_mime_type

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/file/ffprobe/{file:.*}", "ffprobe")
async def get_ffprobe(request: Request, config: Config, encoder: Encoder, app: web.Application) -> Response:
    """
    Get the ffprobe data.

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        encoder (Encoder): The encoder object.
        app (web.Application): The aiohttp application object.

    Returns:
        Response: The response object.

    """
    file: str = request.match_info.get("file")
    if not file:
        return web.json_response(data={"error": "file is required."}, status=web.HTTPBadRequest.status_code)

    try:
        realFile, status = get_file(download_path=config.download_path, file=file)
        if web.HTTPFound.status_code == status:
            return Response(
                status=web.HTTPFound.status_code,
                headers={
                    "Location": str(
                        app.router["ffprobe"].url_for(
                            file=str(realFile.relative_to(config.download_path).as_posix()).strip("/")
                        )
                    ),
                },
            )

        if web.HTTPNotFound.status_code == status:
            return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

        return web.json_response(data=await ffprobe(realFile), status=web.HTTPOk.status_code, dumps=encoder.encode)
    except Exception as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)


@route("GET", "api/file/info/{file:.*}", "file_info")
async def get_file_info(request: Request, config: Config, encoder: Encoder, app: web.Application) -> Response:
    """
    Get file info

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        encoder (Encoder): The encoder object.
        app (web.Application): The aiohttp application object.

    Returns:
        Response: The response object.

    """
    file: str = request.match_info.get("file")
    if not file:
        return web.json_response(data={"error": "file is required."}, status=web.HTTPBadRequest.status_code)

    try:
        realFile, status = get_file(download_path=config.download_path, file=file)
        if web.HTTPFound.status_code == status:
            return Response(
                status=web.HTTPFound.status_code,
                headers={
                    "Location": str(
                        app.router["file_info"].url_for(
                            file=str(realFile.relative_to(config.download_path).as_posix()).strip("/")
                        )
                    ),
                },
            )

        if web.HTTPNotFound.status_code == status:
            return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

        ff_info = await ffprobe(realFile)

        response = {
            "title": realFile.stem,
            "ffprobe": ff_info,
            "mimetype": get_mime_type(ff_info.get("metadata", {}), realFile),
            "sidecar": get_file_sidecar(realFile),
        }

        for key in response["sidecar"]:
            for i, f in enumerate(response["sidecar"][key]):
                response["sidecar"][key][i]["file"] = str(
                    realFile.with_name(f["file"].name).relative_to(config.download_path)
                ).strip("/")

        return web.json_response(data=response, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except Exception as e:
        LOG.exception(e)
        return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)


@route("GET", "api/file/browser/{path:.*}", "file_browser")
async def file_browser(request: Request, config: Config, encoder: Encoder) -> Response:
    """
    Get the file browser.

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        encoder (Encoder): The encoder object.

    Returns:
        Response: The response object.

    """
    if not config.browser_enabled:
        return web.json_response(data={"error": "File browser is disabled."}, status=web.HTTPForbidden.status_code)

    req_path: str = request.match_info.get("path")
    req_path: str = "/" if not req_path else unquote_plus(req_path)

    test: Path = Path(config.download_path).joinpath(req_path)
    if not test.exists():
        return web.json_response(
            data={"error": f"path '{req_path}' does not exist."}, status=web.HTTPNotFound.status_code
        )

    if not test.is_dir() and not test.is_symlink():
        return web.json_response(
            data={"error": f"path '{req_path}' is not a directory."}, status=web.HTTPBadRequest.status_code
        )

    try:
        return web.json_response(
            data={
                "path": req_path,
                "contents": get_files(base_path=Path(config.download_path), dir=req_path),
            },
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )
    except OSError as e:
        LOG.exception(e)
        return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)
