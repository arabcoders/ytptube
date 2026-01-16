import logging
import uuid
from collections import OrderedDict

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.cache import Cache
from app.library.conditions import Condition, Conditions
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.mini_filter import match_str
from app.library.router import route
from app.library.Utils import fetch_info, init_class, validate_uuid
from app.library.YTDLPOpts import YTDLPOpts

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/conditions/", "conditions_list")
async def conditions_list(encoder: Encoder) -> Response:
    """
    Get the conditions

    Args:
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    return web.json_response(
        data=Conditions.get_instance().get_all(),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("PUT", "api/conditions/", "conditions_add")
async def conditions_add(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    """
    Save Conditions.

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

    items: list = []

    cls = Conditions.get_instance()

    for item in data:
        if not isinstance(item, dict):
            return web.json_response(
                {"error": "Invalid request body expecting list with dicts."},
                status=web.HTTPBadRequest.status_code,
            )

        if not item.get("name"):
            return web.json_response(
                {"error": "Name is required.", "data": item}, status=web.HTTPBadRequest.status_code
            )

        if not item.get("filter"):
            return web.json_response(
                {"error": "Filter is required.", "data": item}, status=web.HTTPBadRequest.status_code
            )

        if not item.get("cli") and len(item.get("extras", {}).keys()) < 1:
            return web.json_response(
                {"error": "A Condition Must have cli options or extras", "data": item},
                status=web.HTTPBadRequest.status_code,
            )

        if not item.get("cli"):
            item["cli"] = ""

        if not item.get("extras"):
            item["extras"] = {}

        if "enabled" not in item:
            item["enabled"] = True

        if "priority" not in item:
            item["priority"] = 0

        if "description" not in item:
            item["description"] = ""

        if not item.get("id", None) or not validate_uuid(item.get("id"), version=4):
            item["id"] = str(uuid.uuid4())

        try:
            cls.validate(item)
        except ValueError as e:
            return web.json_response(
                {"error": f"Failed to validate condition '{item.get('name')}'. '{e!s}'"},
                status=web.HTTPBadRequest.status_code,
            )

        items.append(init_class(Condition, item))

    try:
        items = cls.save(items=items).load().get_all()
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            {"error": "Failed to save conditions.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )

    notify.emit(Events.CONDITIONS_UPDATE, data=items)
    return web.json_response(data=items, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/conditions/test/", "conditions_test")
async def conditions_test(request: Request, encoder: Encoder, cache: Cache, config: Config) -> Response:
    """
    Test condition against URL.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.
        cache (Cache): The cache instance.
        config (Config): The configuration instance.

    Returns:
        Response: The response object

    """
    params = await request.json()

    if not isinstance(params, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    url: str | None = params.get("url")
    if not url:
        return web.json_response({"error": "url is required."}, status=web.HTTPBadRequest.status_code)

    cond: str | None = params.get("condition")
    if not cond:
        return web.json_response({"error": "condition is required."}, status=web.HTTPBadRequest.status_code)

    try:
        preset: str = params.get("preset", config.default_preset)
        key: str = cache.hash(url + str(preset))
        if not cache.has(key):
            data: dict | None = await fetch_info(
                config=YTDLPOpts.get_instance().preset(name=preset).get_all(),
                url=url,
                debug=False,
                no_archive=True,
                follow_redirect=True,
                sanitize_info=True,
            )

            if not data:
                return web.json_response(
                    data={"error": f"Failed to extract info from '{url!s}'."},
                    status=web.HTTPBadRequest.status_code,
                )
            cache.set(key=key, value=data, ttl=600)
        else:
            data = cache.get(key)
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": f"Failed to extract video info. '{e!s}'"},
            status=web.HTTPInternalServerError.status_code,
        )

    try:
        status: bool = match_str(cond, data)
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": str(e)},
            status=web.HTTPBadRequest.status_code,
        )

    return web.json_response(
        data={
            "status": status,
            "condition": cond,
            "data": OrderedDict(sorted(data.items(), key=lambda item: len(str(item[1])))),
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )
