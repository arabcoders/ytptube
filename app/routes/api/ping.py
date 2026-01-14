from aiohttp import web
from aiohttp.web import Response

from app.library.downloads import DownloadQueue
from app.library.router import route


@route("GET", "api/ping/", "ping")
async def ping(queue: DownloadQueue) -> Response:
    """
    Ping the server.

    Returns:
        Response: The response object.

    """
    await queue.queue.test()

    return web.json_response(data={"status": "pong"}, status=web.HTTPOk.status_code)
