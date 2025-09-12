import logging
import uuid

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.Notifications import Notification, NotificationEvents
from app.library.router import route
from app.library.Utils import validate_uuid

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/notifications/", "notifications_list")
async def notifications_list(encoder: Encoder) -> Response:
    """
    Get the notification targets.

    Args:
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    return web.json_response(
        data={
            "notifications": Notification.get_instance().get_targets(),
            "allowedTypes": list(NotificationEvents.get_events().values()),
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("PUT", "api/notifications/", "notification_add")
async def notification_add(request: Request, encoder: Encoder) -> Response:
    """
    Add notification targets.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    post = await request.json()
    if not isinstance(post, list):
        return web.json_response(
            {"error": "Invalid request body expecting list with dicts."},
            status=web.HTTPBadRequest.status_code,
        )

    targets: list = []

    ins: Notification = Notification.get_instance()
    for item in post:
        if not isinstance(item, dict):
            return web.json_response(
                {"error": "Invalid request body expecting list with dicts."},
                status=web.HTTPBadRequest.status_code,
            )

        if not item.get("id", None) or validate_uuid(item.get("id"), version=4):
            item["id"] = str(uuid.uuid4())

        try:
            Notification.validate(item)
        except ValueError as e:
            return web.json_response(
                {"error": f"Invalid notification target settings. {e!s}", "data": item},
                status=web.HTTPBadRequest.status_code,
            )

        targets.append(ins.make_target(item))

    try:
        ins.save(targets=targets)
        ins.load()
    except Exception as e:
        LOG.exception(e)
        return web.json_response({"error": "Failed to save tasks."}, status=web.HTTPInternalServerError.status_code)

    data = {"notifications": targets, "allowedTypes": list(NotificationEvents.get_events().values())}

    return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/notifications/test/", "notification_test")
async def notification_test(encoder: Encoder, notify: EventBus) -> Response:
    """
    Test the notification.

    Args:
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    notify.emit(Events.TEST, title="Test Notification", message="This is a test notification.")

    return web.json_response(data={}, status=web.HTTPOk.status_code, dumps=encoder.encode)
