import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.Download import Download
from app.library.DownloadQueue import DownloadQueue
from app.library.router import route
from app.library.Utils import is_downloaded, remove_from_archive
from app.library.YTDLPOpts import YTDLPOpts

if TYPE_CHECKING:
    from library.Download import Download

LOG: logging.Logger = logging.getLogger(__name__)


@route("DELETE", r"api/archive/{id}", "archive.remove")
async def archive_remove(request: Request, queue: DownloadQueue, config: Config) -> Response:
    """
    Remove an item from the archive.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        config (Config): The configuration instance.

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

    if not url:
        id: str = request.match_info.get("id")
        if not id:
            return web.json_response(data={"error": "id is required."}, status=web.HTTPBadRequest.status_code)

        try:
            item: Download | None = queue.done.get_by_id(id)
            if not item:
                return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)

            url = item.info.url
            title = f" '{item.info.title}'"
        except KeyError:
            return web.json_response(data={"error": f"item '{id}' not found."}, status=web.HTTPNotFound.status_code)

    if config.manual_archive:
        remove_from_archive(archive_file=Path(config.manual_archive), url=url)

    archive_file: Path | None = Path(config.archive_file) if config.keep_archive else None
    if item:
        params: YTDLPOpts = YTDLPOpts.get_instance().preset(name=item.info.preset)
        if item.info.cli:
            params.add_cli(item.info.cli, from_user=True)

        params = params.get_all()
        if user_file := params.get("download_archive", None):
            archive_file = Path(user_file)

    if not archive_file:
        return web.json_response(
            data={
                "error": "Archive file is not configured." if not config.keep_archive else "Archive file is not set."
            },
            status=web.HTTPBadRequest.status_code,
        )

    if not archive_file.exists():
        return web.json_response(
            data={"error": f"Archive file '{archive_file}' does not exist."},
            status=web.HTTPNotFound.status_code,
        )

    if not remove_from_archive(archive_file=archive_file, url=url):
        return web.json_response(
            data={"error": f"item{title} not found in '{archive_file}' archive."},
            status=web.HTTPNotFound.status_code,
        )

    return web.json_response(
        data={"message": f"item{title} removed from '{archive_file}' archive."},
        status=web.HTTPOk.status_code,
    )


@route("POST", r"api/archive/{id}", "archive.item")
async def archive_item(request: Request, queue: DownloadQueue, config: Config):
    """
    Manually mark an item as archived.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        config (Config): The configuration instance.

    Returns:
        Response: The response object.

    """
    id: str = request.match_info.get("id")

    if not id:
        return web.json_response(data={"error": "id is required."}, status=web.HTTPBadRequest.status_code)

    try:
        item: Download | None = queue.done.get_by_id(id)
        if not item:
            return web.json_response(data={"error": "item not found."}, status=web.HTTPNotFound.status_code)
    except KeyError:
        return web.json_response(data={"error": "item not found."}, status=web.HTTPNotFound.status_code)

    if config.manual_archive:
        manual_archive = Path(config.manual_archive)
        if manual_archive.exists():
            exists, idDict = is_downloaded(manual_archive, item.info.url)
            if exists is False and idDict.get("archive_id"):
                async with await anyio.open_file(manual_archive, "a") as f:
                    await f.write(f"{idDict['archive_id']} - at: {datetime.now(UTC).isoformat()}\n")

    params: YTDLPOpts = YTDLPOpts.get_instance().preset(name=item.info.preset)
    if item.info.cli:
        params.add_cli(item.info.cli, from_user=True)

    params = params.get_all()

    user_file: str | None = params.get("download_archive", None)
    archive_file: Path = Path(user_file) if user_file else Path(config.archive_file)
    if not archive_file.exists():
        return web.json_response(
            data={"error": f"Archive file '{archive_file}' does not exist."},
            status=web.HTTPNotFound.status_code,
        )

    exists, idDict = is_downloaded(archive_file, item.info.url)
    item_id: str | None = idDict.get("archive_id")
    if not item_id:
        return web.json_response(
            data={"error": "item does not have an archive ID."}, status=web.HTTPBadRequest.status_code
        )

    if exists is True:
        return web.json_response(
            data={"error": f"item '{item_id}' already archived in file '{archive_file}'."},
            status=web.HTTPConflict.status_code,
        )

    async with await anyio.open_file(archive_file, "a") as f:
        await f.write(f"{item_id}\n")

    return web.json_response(
        data={"message": f"item '{item_id}' archived in file '{archive_file}'."},
        status=web.HTTPOk.status_code,
    )
