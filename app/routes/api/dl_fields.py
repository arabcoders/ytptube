import logging
import uuid

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.dl_fields import DLField, DLFields
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.router import route
from app.library.Utils import init_class, validate_uuid

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/dl_fields/", "dl_fields")
async def dl_fields(request: Request, encoder: Encoder) -> Response:
    """
    Get the dl_fields.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    data: list[DLField] = DLFields.get_instance().get_all()
    filter_fields: str | None = request.query.get("filter", None)

    if filter_fields:
        fields: list[str] = [field.strip() for field in filter_fields.split(",")]
        data = [{key: value for key, value in preset.serialize().items() if key in fields} for preset in data]

    return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("PUT", "api/dl_fields/", "dl_fields_add")
async def dl_fields_add(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    """
    Add presets.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object

    """
    data = await request.json()

    if not isinstance(data, list):
        return web.json_response(
            {"error": "Invalid request body expecting list with dicts."},
            status=web.HTTPBadRequest.status_code,
        )

    items: list[DLField] = []

    cls = DLFields.get_instance()

    for item in data:
        if not isinstance(item, dict):
            return web.json_response(
                {"error": "Invalid request body expecting list with dicts."},
                status=web.HTTPBadRequest.status_code,
            )

        if not item.get("name"):
            return web.json_response(
                {"error": "name is required.", "data": item}, status=web.HTTPBadRequest.status_code
            )

        if not item.get("id", None) or not validate_uuid(item.get("id"), version=4):
            item["id"] = str(uuid.uuid4())

        try:
            cls.validate(item)
        except ValueError as e:
            return web.json_response(
                {"error": f"Failed to validate preset '{item.get('name')}'. '{e!s}'"},
                status=web.HTTPBadRequest.status_code,
            )

        items.append(init_class(DLField, item))

    try:
        items = cls.save(items=items).load().get_all()
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            {"error": "Failed to save download fields.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )

    notify.emit(Events.DLFIELDS_UPDATE, data=items)
    return web.json_response(data=items, status=web.HTTPOk.status_code, dumps=encoder.encode)
