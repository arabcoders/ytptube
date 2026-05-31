from app.library.Events import EventBus, Events
from app.library.log import get_logger
from app.library.router import RouteType, route

LOG = get_logger()


@route(RouteType.SOCKET, "connect", "socket_connect")
async def connect(notify: EventBus, sid: str):
    notify.emit(
        Events.CONNECTED, data={"sid": sid}, title="Client connected", message=f"Client '{sid}' connected.", to=sid
    )


@route(RouteType.SOCKET, "disconnect", "socket_disconnect")
async def disconnect(sid: str):
    pass
