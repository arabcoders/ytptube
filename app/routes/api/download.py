import logging

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.router import route
from app.library.Utils import get_file

LOG: logging.Logger = logging.getLogger(__name__)


@route(["GET", "HEAD"], "/api/download/{filename:.+}", "download_static")
async def download_file(request: Request, config: Config, app: web.Application) -> Response:
    """
    Serve download files.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        app (web.Application): The aiohttp application instance.

    Returns:
        Response: The file response with correct MIME type.

    """
    if not (filename := request.match_info.get("filename")):
        return web.json_response({"error": "Filename required"}, status=web.HTTPBadRequest.status_code)

    try:
        realFile, status = get_file(download_path=config.download_path, file=filename)
        if web.HTTPFound.status_code == status:
            return Response(
                status=web.HTTPFound.status_code,
                headers={
                    "Location": str(
                        app.router["download_static"].url_for(
                            file=str(realFile).replace(config.download_path, "").strip("/")
                        )
                    ),
                },
            )

        if web.HTTPNotFound.status_code == status:
            return web.json_response(data={"error": "File not found"}, status=status)
    except Exception as e:
        LOG.exception("Error retrieving file '%s': %s", filename, str(e))
        return web.json_response(
            data={"error": "Internal server error."},
            status=web.HTTPInternalServerError.status_code,
        )

    if not realFile.is_file():
        return web.json_response({"error": "File not found"}, status=web.HTTPNotFound.status_code)

    from app.routes.api._static import EXT_TO_MIME

    content_type = EXT_TO_MIME.get(realFile.suffix)
    if not content_type:
        import mimetypes

        content_type, _ = mimetypes.guess_type(str(realFile))
        if not content_type:
            content_type = "application/octet-stream"

    return web.FileResponse(path=str(realFile), headers={"Content-Type": content_type})
