from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response
from pydantic import ValidationError

from app.features.core.schemas import CEAction, CEFeature, ConfigEvent, Pagination
from app.features.core.utils import api_error_response, build_pagination, format_validation_errors, normalize_pagination
from app.features.dl_fields.schemas import DLField, DLFieldList, DLFieldPatch
from app.features.dl_fields.service import DLFields
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.logging import get_logger
from app.library.router import route

LOG = get_logger()


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
        return api_error_response(
            "Invalid request body expecting dict.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    try:
        item: DLField = DLField.model_validate(data)
    except ValidationError as exc:
        return api_error_response(
            "Failed to validate dl field.",
            code="VALIDATION_FAILED",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.downloadField"},
            detail=format_validation_errors(exc),
        )

    try:
        saved = _serialize(await DLFields.get_instance().save(item=item.model_dump()))
    except ValueError as exc:
        return api_error_response(
            str(exc),
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.downloadField"},
            detail=str(exc),
        )

    notify.emit(Events.CONFIG_UPDATE, data=ConfigEvent(feature=CEFeature.DL_FIELDS, action=CEAction.CREATE, data=saved))

    return web.json_response(data=saved, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("GET", r"api/dl_fields/{id:\d+}", "dl_fields_get")
async def dl_fields_get(request: Request, encoder: Encoder) -> Response:
    if not (identifier := request.match_info.get("id")):
        return api_error_response(
            "ID required",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    if not (model := await DLFields.get_instance().get(identifier)):
        return api_error_response(
            "DL field not found",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.downloadField"},
        )

    return web.json_response(data=_serialize(model), status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("DELETE", r"api/dl_fields/{id:\d+}", "dl_fields_delete")
async def dl_fields_delete(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    if not (identifier := request.match_info.get("id")):
        return api_error_response(
            "ID required",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    try:
        deleted = _serialize(await DLFields.get_instance()._repo.delete(identifier))
        notify.emit(
            Events.CONFIG_UPDATE, data=ConfigEvent(feature=CEFeature.DL_FIELDS, action=CEAction.DELETE, data=deleted)
        )
        return web.json_response(
            data=deleted,
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )
    except KeyError as exc:
        return api_error_response(
            str(exc),
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.downloadField"},
            detail=str(exc),
        )


@route("PATCH", r"api/dl_fields/{id:\d+}", "dl_fields_patch")
async def dl_fields_patch(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    if not (identifier := request.match_info.get("id")):
        return api_error_response(
            "ID required",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    if not (model := await DLFields.get_instance().get(identifier)):
        return api_error_response(
            "DL field not found",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.downloadField"},
        )

    data = await request.json()

    if not isinstance(data, dict):
        return api_error_response(
            "Invalid request body expecting dict.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = DLFieldPatch.model_validate(data)
    except ValidationError as exc:
        return api_error_response(
            "Failed to validate dl field.",
            code="VALIDATION_FAILED",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.downloadField"},
            detail=format_validation_errors(exc),
        )

    if validated.name and await DLFields.get_instance()._repo.get_by_name(validated.name, exclude_id=model.id):
        return api_error_response(
            f"DL field with name '{validated.name}' already exists.",
            code="ALREADY_EXISTS",
            status=web.HTTPConflict.status_code,
            params={"resource": "api.resources.downloadField", "field": "api.fields.name"},
        )

    updated = _serialize(await DLFields.get_instance()._repo.update(model.id, validated.model_dump(exclude_unset=True)))
    notify.emit(
        Events.CONFIG_UPDATE, data=ConfigEvent(feature=CEFeature.DL_FIELDS, action=CEAction.UPDATE, data=updated)
    )
    return web.json_response(
        data=updated,
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("PUT", r"api/dl_fields/{id:\d+}", "dl_fields_update")
async def dl_fields_update(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    if not (identifier := request.match_info.get("id")):
        return api_error_response(
            "ID required",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    if not (model := await DLFields.get_instance().get(identifier)):
        return api_error_response(
            "DL field not found",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.downloadField"},
        )

    data = await request.json()

    if not isinstance(data, dict):
        return api_error_response(
            "Invalid request body expecting dict.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = DLField.model_validate(data)
    except ValidationError as exc:
        return api_error_response(
            "Failed to validate dl field.",
            code="VALIDATION_FAILED",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.downloadField"},
            detail=format_validation_errors(exc),
        )

    if validated.name and await DLFields.get_instance()._repo.get_by_name(validated.name, exclude_id=model.id):
        return api_error_response(
            f"DL field with name '{validated.name}' already exists.",
            code="ALREADY_EXISTS",
            status=web.HTTPConflict.status_code,
            params={"resource": "api.resources.downloadField", "field": "api.fields.name"},
        )

    updated = _serialize(await DLFields.get_instance()._repo.update(model.id, validated.model_dump(exclude_unset=True)))
    notify.emit(
        Events.CONFIG_UPDATE, data=ConfigEvent(feature=CEFeature.DL_FIELDS, action=CEAction.UPDATE, data=updated)
    )

    return web.json_response(data=updated, status=web.HTTPOk.status_code, dumps=encoder.encode)
