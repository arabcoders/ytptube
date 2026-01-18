import logging
from collections import OrderedDict
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response
from pydantic import ValidationError

from app.features.conditions.schemas import Condition, ConditionList, ConditionPatch
from app.features.conditions.service import Conditions
from app.features.core.schemas import Pagination
from app.features.core.utils import build_pagination, format_validation_errors, normalize_pagination
from app.library.cache import Cache
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.router import route

LOG: logging.Logger = logging.getLogger(__name__)


def _model(model: Any) -> Condition:
    return Condition.model_validate(model)


def _serialize(model: Any) -> dict:
    return _model(model).model_dump()


@route("GET", "api/conditions/", name="conditions_list")
async def conditions_list(request: Request, encoder: Encoder) -> Response:
    """
    Get the conditions

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    repo = Conditions.get_instance()._repo

    page, per_page = normalize_pagination(request)
    items, total, current_page, total_pages = await repo.list_paginated(page, per_page)
    return web.json_response(
        data=ConditionList(
            items=[_model(model) for model in items],
            pagination=Pagination.model_validate(build_pagination(total, current_page, per_page, total_pages)),
        ),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/conditions/test/", name="condition_test")
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

    if not (url := params.get("url")):
        return web.json_response({"error": "url is required."}, status=web.HTTPBadRequest.status_code)

    if not (cond := params.get("condition")):
        return web.json_response({"error": "condition is required."}, status=web.HTTPBadRequest.status_code)

    try:
        preset: str = params.get("preset", config.default_preset)
        key: str = cache.hash(url + str(preset))
        if not cache.has(key):
            from app.library.Utils import fetch_info
            from app.library.YTDLPOpts import YTDLPOpts

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
        from app.library.mini_filter import match_str

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


@route("POST", "api/conditions/", name="condition_add")
async def conditions_add(request: Request, encoder: Encoder) -> Response:
    """
    Add Condition.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object

    """
    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting list with dicts."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        item: Condition = Condition.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate condition.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        data = _serialize(await Conditions.get_instance().save(item=item.model_dump()))
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPBadRequest.status_code)

    return web.json_response(
        data=data,
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/conditions/{id}", name="condition_get")
async def conditions_get(request: Request, encoder: Encoder) -> Response:
    """
    Get the conditions

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    if not (id := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await Conditions.get_instance().get(id)):
        return web.json_response({"error": "Condition not found"}, status=web.HTTPNotFound.status_code)

    return web.json_response(data=_serialize(model), status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("DELETE", "api/conditions/{id}", name="condition_delete")
async def conditions_delete(request: Request, encoder: Encoder) -> Response:
    """
    Delete Condition.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    if not (id := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    try:
        return web.json_response(
            data=_serialize(await Conditions.get_instance()._repo.delete(id)),
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )
    except KeyError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPNotFound.status_code)


@route("PATCH", "api/conditions/{id}", name="condition_patch")
async def conditions_patch(request: Request, encoder: Encoder) -> Response:
    """
    Patch Condition.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    if not (id := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await Conditions.get_instance().get(id)):
        return web.json_response({"error": "Condition not found"}, status=web.HTTPNotFound.status_code)

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting list with dicts."},
            status=web.HTTPBadRequest.status_code,
        )

    service = Conditions.get_instance()

    try:
        validated = ConditionPatch.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate condition.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    if validated.name and await service._repo.get_by_name(validated.name, exclude_id=model.id):
        return web.json_response(
            data={"error": f"Condition with name '{validated.name}' already exists."},
            status=web.HTTPConflict.status_code,
        )

    dct = validated.model_dump(exclude_unset=True)

    return web.json_response(
        data=_serialize(await service._repo.update(model.id, dct)),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("PUT", "api/conditions/{id}", name="condition_update")
async def conditions_update(request: Request, encoder: Encoder) -> Response:
    """
    Update Condition.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    if not (id := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await Conditions.get_instance().get(id)):
        return web.json_response({"error": "Condition not found"}, status=web.HTTPNotFound.status_code)

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting list with dicts."},
            status=web.HTTPBadRequest.status_code,
        )

    service = Conditions.get_instance()

    try:
        validated = Condition.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate condition.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    if validated.name and await service._repo.get_by_name(validated.name, exclude_id=model.id):
        return web.json_response(
            data={"error": f"Condition with name '{validated.name}' already exists."},
            status=web.HTTPConflict.status_code,
        )

    return web.json_response(
        data=_serialize(await service._repo.update(model.id, validated.model_dump(exclude_unset=True))),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )
