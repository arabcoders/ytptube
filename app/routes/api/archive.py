import logging
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.Download import Download
from app.library.DownloadQueue import DownloadQueue
from app.library.router import route
from app.library.Utils import archive_add, archive_delete, archive_read, get_archive_id
from app.library.YTDLPOpts import YTDLPOpts

if TYPE_CHECKING:
    from library.Download import Download

LOG: logging.Logger = logging.getLogger(__name__)


@route("POST", r"api/archive/{id}", "archive.item")
async def archive_item(request: Request, queue: DownloadQueue):
    """
    Manually mark an item as archived.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        config (Config): The configuration instance.

    Returns:
        Response: The response object.

    """
    if not (id := request.match_info.get("id")):
        return web.json_response(data={"error": "id is required."}, status=web.HTTPBadRequest.status_code)

    try:
        item: Download | None = queue.done.get_by_id(id)
        if not item:
            return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)
    except KeyError:
        return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)

    params: dict = item.get_ytdlp_opts().get_all()

    if not (archive_file := params.get("download_archive")):
        return web.json_response(
            data={"error": f"item '{item.info.title}' does not have an archive file."},
            status=web.HTTPBadRequest.status_code,
        )

    idDict = get_archive_id(url=item.info.url)
    if not (archive_id := idDict.get("archive_id")):
        return web.json_response(
            data={"error": f"item '{item.info.title}' does not have an archive ID."},
            status=web.HTTPBadRequest.status_code,
        )

    if len(archive_read(archive_file, [archive_id])) > 0:
        return web.json_response(
            data={"error": f"item '{item.info.title}' already archived."},
            status=web.HTTPConflict.status_code,
        )

    archive_add(archive_file, [archive_id])

    return web.json_response(
        data={"message": f"item '{item.info.title}' archived."},
        status=web.HTTPOk.status_code,
    )


@route("DELETE", r"api/archive/{id}", "archive.remove")
async def archive_remove(request: Request, queue: DownloadQueue) -> Response:
    """
    Remove an item from the archive.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.

    Returns:
        Response: The response object.

    """
    item = None
    try:
        data: dict | None = await request.json()
    except Exception:
        data = {}

    title: str = ""
    url: str | None = data.get("url")
    id: str | None = request.match_info.get("id")
    preset: str | None = data.get("preset",)

    if not id and not url:
        return web.json_response(data={"error": "id or url is required."}, status=web.HTTPBadRequest.status_code)

    if id:
        try:
            item: Download | None = queue.done.get_by_id(id)
            if not item:
                return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)

            url = item.info.url
            title = f" '{item.info.title}'"
            params = item.get_ytdlp_opts().get_all()
        except KeyError:
            return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)
    else:
        params: YTDLPOpts = YTDLPOpts.get_instance()
        if preset := data.get("preset"):
            params = params.preset(name=preset)

        params = params.get_all()

    if not (archive_file := params.get("download_archive", None)):
        return web.json_response(
            data={"error": "Archive file is not configured."},
            status=web.HTTPBadRequest.status_code,
        )

    archive_file = Path(archive_file)

    if not archive_file.exists():
        return web.json_response(
            data={"error": f"Archive file '{archive_file}' does not exist."},
            status=web.HTTPNotFound.status_code,
        )

    idDict = get_archive_id(url=url)
    if not (archive_id := idDict.get("archive_id")):
        return web.json_response(
            data={"error": "item does not have an archive ID."},
            status=web.HTTPBadRequest.status_code,
        )

    if not archive_delete(archive_file, [archive_id]):
        return web.json_response(
            data={"error": f"item{title} not found in '{archive_file}' archive."},
            status=web.HTTPNotFound.status_code,
        )

    return web.json_response(
        data={"message": f"item{title} removed from '{archive_file}' archive."},
        status=web.HTTPOk.status_code,
    )
