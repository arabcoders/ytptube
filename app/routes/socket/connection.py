import logging

from app.library.router import RouteType, route

LOG: logging.Logger = logging.getLogger(__name__)


@route(RouteType.SOCKET, "connect", "socket_connect")
async def connect(sid: str):
    pass


@route(RouteType.SOCKET, "disconnect", "socket_disconnect")
async def disconnect(sid: str):
    pass
