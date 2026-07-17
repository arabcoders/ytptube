from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response
from pydantic import ValidationError

from app.features.core.schemas import CEAction, CEFeature, ConfigEvent, Pagination
from app.features.core.utils import api_error_response, build_pagination, format_validation_errors, normalize_pagination
from app.features.presets.repository import PresetsRepository
from app.features.presets.schemas import Preset, PresetList, PresetPatch
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.router import route


def _model(model: Any) -> Preset:
    return Preset.model_validate(model)


def _serialize(model: Any) -> dict:
    return _model(model).model_dump()


@route("GET", "api/presets/", "presets")
async def presets_list(request: Request, encoder: Encoder, repo: PresetsRepository) -> Response:
    try:
        page, per_page = normalize_pagination(request)
        items, total, current_page, total_pages = await repo.list_paginated(
            page=page,
            per_page=per_page,
            sort=request.query.get("sort"),
            order=request.query.get("order"),
            exclude_defaults=bool(request.query.get("exclude_defaults", False)),
        )
    except ValueError as exc:
        return api_error_response(
            str(exc),
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.preset"},
            detail=str(exc),
        )

    return web.json_response(
        data=PresetList(
            items=[_model(model) for model in items],
            pagination=Pagination.model_validate(build_pagination(total, current_page, per_page, total_pages)),
        ),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", r"api/presets/{id:\d+}", "presets_get")
async def presets_get(request: Request, encoder: Encoder, repo: PresetsRepository) -> Response:
    if not (identifier := request.match_info.get("id")):
        return api_error_response(
            "ID required",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    if not (model := await repo.get(identifier)):
        return api_error_response(
            "Preset not found",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.preset"},
        )

    return web.json_response(data=_serialize(model), status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/presets/", "presets_add")
async def presets_add(request: Request, encoder: Encoder, notify: EventBus, repo: PresetsRepository) -> Response:
    data = await request.json()

    if not isinstance(data, dict):
        return api_error_response(
            "Invalid request body expecting dict.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    try:
        item: Preset = Preset.model_validate(data)
    except ValidationError as exc:
        return api_error_response(
            "Failed to validate preset.",
            code="VALIDATION_FAILED",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.preset"},
            detail=format_validation_errors(exc),
        )

    payload = item.model_dump(exclude_unset=True)
    payload.pop("id", None)
    payload["default"] = False

    try:
        saved = _serialize(await repo.create(payload))
    except ValueError as exc:
        return api_error_response(
            str(exc),
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.preset"},
            detail=str(exc),
        )

    notify.emit(
        Events.CONFIG_UPDATE,
        data=ConfigEvent(feature=CEFeature.PRESETS, action=CEAction.CREATE, data=saved),
    )
    return web.json_response(data=saved, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("PATCH", r"api/presets/{id:\d+}", "presets_patch")
async def presets_patch(request: Request, encoder: Encoder, notify: EventBus, repo: PresetsRepository) -> Response:
    if not (identifier := request.match_info.get("id")):
        return api_error_response(
            "ID required",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    if not (model := await repo.get(identifier)):
        return api_error_response(
            "Preset not found",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.preset"},
        )

    if model.default:
        return api_error_response(
            "Default presets cannot be modified.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.preset"},
        )

    data = await request.json()

    if not isinstance(data, dict):
        return api_error_response(
            "Invalid request body expecting dict.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = PresetPatch.model_validate(data)
    except ValidationError as exc:
        return api_error_response(
            "Failed to validate preset.",
            code="VALIDATION_FAILED",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.preset"},
            detail=format_validation_errors(exc),
        )

    if validated.name and await repo.get_by_name(validated.name, exclude_id=model.id):
        return api_error_response(
            f"Preset with name '{validated.name}' already exists.",
            code="ALREADY_EXISTS",
            status=web.HTTPConflict.status_code,
            params={"resource": "api.resources.preset", "field": "api.fields.name"},
        )

    payload = validated.model_dump(exclude_unset=True)
    payload.pop("default", None)
    updated = _serialize(await repo.update(model.id, payload))
    notify.emit(
        Events.CONFIG_UPDATE,
        data=ConfigEvent(feature=CEFeature.PRESETS, action=CEAction.UPDATE, data=updated),
    )
    return web.json_response(data=updated, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("PUT", r"api/presets/{id:\d+}", "presets_update")
async def presets_update(request: Request, encoder: Encoder, notify: EventBus, repo: PresetsRepository) -> Response:
    if not (identifier := request.match_info.get("id")):
        return api_error_response(
            "ID required",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    if not (model := await repo.get(identifier)):
        return api_error_response(
            "Preset not found",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.preset"},
        )

    if model.default:
        return api_error_response(
            "Default presets cannot be modified.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.preset"},
        )

    data = await request.json()

    if not isinstance(data, dict):
        return api_error_response(
            "Invalid request body expecting dict.",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = Preset.model_validate(data)
    except ValidationError as exc:
        return api_error_response(
            "Failed to validate preset.",
            code="VALIDATION_FAILED",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.preset"},
            detail=format_validation_errors(exc),
        )

    if validated.name and await repo.get_by_name(validated.name, exclude_id=model.id):
        return api_error_response(
            f"Preset with name '{validated.name}' already exists.",
            code="ALREADY_EXISTS",
            status=web.HTTPConflict.status_code,
            params={"resource": "api.resources.preset", "field": "api.fields.name"},
        )

    payload = validated.model_dump(exclude_unset=True)
    payload.pop("default", None)
    payload.pop("id", None)
    updated = _serialize(await repo.update(model.id, payload))
    notify.emit(
        Events.CONFIG_UPDATE,
        data=ConfigEvent(feature=CEFeature.PRESETS, action=CEAction.UPDATE, data=updated),
    )
    return web.json_response(data=updated, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("DELETE", r"api/presets/{id:\d+}", "presets_delete")
async def presets_delete(request: Request, encoder: Encoder, notify: EventBus, repo: PresetsRepository) -> Response:
    if not (identifier := request.match_info.get("id")):
        return api_error_response(
            "ID required",
            code="BAD_REQUEST",
            status=web.HTTPBadRequest.status_code,
        )

    if not (model := await repo.get(identifier)):
        return api_error_response(
            "Preset not found",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.preset"},
        )

    if model.default:
        return api_error_response(
            "Default presets cannot be deleted.",
            code="INVALID",
            status=web.HTTPBadRequest.status_code,
            params={"resource": "api.resources.preset"},
        )

    deleted = _serialize(await repo.delete(model.id))
    notify.emit(
        Events.CONFIG_UPDATE,
        data=ConfigEvent(feature=CEFeature.PRESETS, action=CEAction.DELETE, data=deleted),
    )
    return web.json_response(data=deleted, status=web.HTTPOk.status_code, dumps=encoder.encode)
