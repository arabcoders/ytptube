import logging
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response
from pydantic import ValidationError

from app.features.core.schemas import Pagination
from app.features.core.utils import build_pagination, format_validation_errors, normalize_pagination
from app.features.dl_fields.schemas import DLField, DLFieldList, DLFieldPatch
from app.features.dl_fields.service import DLFields
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.router import route

LOG: logging.Logger = logging.getLogger(__name__)


def _model(model: Any) -> DLField:
    return DLField.model_validate(model)


def _serialize(model: Any) -> dict:
    return _model(model).model_dump()


@route("GET", "api/dl_fields/", "dl_fields")
async def dl_fields_list(request: Request, encoder: Encoder) -> Response:
    repo = DLFields.get_instance()._repo
    page, per_page = normalize_pagination(request)
    items, total, current_page, total_pages = await repo.list_paginated(page, per_page)
    return web.json_response(
        data=DLFieldList(
            items=[_model(model) for model in items],
            pagination=Pagination.model_validate(build_pagination(total, current_page, per_page, total_pages)),
        ),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/dl_fields/", "dl_fields_add")
async def dl_fields_add(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        item: DLField = DLField.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate dl field.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        saved = _serialize(await DLFields.get_instance().save(item=item.model_dump()))
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPBadRequest.status_code)

    notify.emit(Events.DLFIELDS_UPDATE, data=[saved])

    return web.json_response(data=saved, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("GET", "api/dl_fields/{id}", "dl_fields_get")
async def dl_fields_get(request: Request, encoder: Encoder) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await DLFields.get_instance().get(identifier)):
        return web.json_response({"error": "DL field not found"}, status=web.HTTPNotFound.status_code)

    return web.json_response(data=_serialize(model), status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("DELETE", "api/dl_fields/{id}", "dl_fields_delete")
async def dl_fields_delete(request: Request, encoder: Encoder) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    try:
        return web.json_response(
            data=_serialize(await DLFields.get_instance()._repo.delete(identifier)),
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )
    except KeyError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPNotFound.status_code)


@route("PATCH", "api/dl_fields/{id}", "dl_fields_patch")
async def dl_fields_patch(request: Request, encoder: Encoder) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await DLFields.get_instance().get(identifier)):
        return web.json_response({"error": "DL field not found"}, status=web.HTTPNotFound.status_code)

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = DLFieldPatch.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate dl field.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    if validated.name and await DLFields.get_instance()._repo.get_by_name(validated.name, exclude_id=model.id):
        return web.json_response(
            data={"error": f"DL field with name '{validated.name}' already exists."},
            status=web.HTTPConflict.status_code,
        )

    dct = validated.model_dump(exclude_unset=True)

    return web.json_response(
        data=_serialize(await DLFields.get_instance()._repo.update(model.id, dct)),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("PUT", "api/dl_fields/{id}", "dl_fields_update")
async def dl_fields_update(request: Request, encoder: Encoder) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await DLFields.get_instance().get(identifier)):
        return web.json_response({"error": "DL field not found"}, status=web.HTTPNotFound.status_code)

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = DLField.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate dl field.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    if validated.name and await DLFields.get_instance()._repo.get_by_name(validated.name, exclude_id=model.id):
        return web.json_response(
            data={"error": f"DL field with name '{validated.name}' already exists."},
            status=web.HTTPConflict.status_code,
        )

    return web.json_response(
        data=_serialize(await DLFields.get_instance()._repo.update(model.id, validated.model_dump(exclude_unset=True))),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )
