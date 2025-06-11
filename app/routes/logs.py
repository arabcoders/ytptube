from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.router import route
from app.library.Utils import read_logfile


@route("GET", "api/logs/", "logs")
async def logs(request: Request, config: Config, encoder: Encoder) -> Response:
    """
    Get recent logs

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    if not config.file_logging:
        return web.json_response(data={"error": "File logging is not enabled."}, status=web.HTTPNotFound.status_code)

    offset = int(request.query.get("offset", 0))
    limit = int(request.query.get("limit", 100))
    if limit < 1 or limit > 150:
        limit = 50

    logs_data = await read_logfile(
        file=Path(config.config_path) / "logs" / "app.log",
        offset=offset,
        limit=limit,
    )

    return web.json_response(
        data={
            "logs": logs_data["logs"],
            "offset": offset,
            "limit": limit,
            "next_offset": logs_data["next_offset"],
            "end_is_reached": logs_data["end_is_reached"],
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )
