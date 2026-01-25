from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response
from pydantic import ValidationError

from app.features.core.schemas import CEAction, CEFeature, ConfigEvent, Pagination
from app.features.core.utils import build_pagination, format_validation_errors, normalize_pagination
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
    page, per_page = normalize_pagination(request)
    items, total, current_page, total_pages = await repo.list_paginated(page, per_page)
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
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await repo.get(identifier)):
        return web.json_response({"error": "Preset not found"}, status=web.HTTPNotFound.status_code)

    return web.json_response(data=_serialize(model), status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/presets/", "presets_add")
async def presets_add(request: Request, encoder: Encoder, notify: EventBus, repo: PresetsRepository) -> Response:
    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        item: Preset = Preset.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate preset.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    payload = item.model_dump(exclude_unset=True)
    payload.pop("id", None)
    payload["default"] = False

    try:
        saved = _serialize(await repo.create(payload))
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPBadRequest.status_code)

    notify.emit(
        Events.CONFIG_UPDATE,
        data=ConfigEvent(feature=CEFeature.PRESETS, action=CEAction.CREATE, data=saved),
    )
    return web.json_response(data=saved, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("PATCH", r"api/presets/{id:\d+}", "presets_patch")
async def presets_patch(request: Request, encoder: Encoder, notify: EventBus, repo: PresetsRepository) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await repo.get(identifier)):
        return web.json_response({"error": "Preset not found"}, status=web.HTTPNotFound.status_code)

    if model.default:
        return web.json_response(
            {"error": "Default presets cannot be modified."}, status=web.HTTPBadRequest.status_code
        )

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = PresetPatch.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate preset.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    if validated.name and await repo.get_by_name(validated.name, exclude_id=model.id):
        return web.json_response(
            data={"error": f"Preset with name '{validated.name}' already exists."},
            status=web.HTTPConflict.status_code,
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
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await repo.get(identifier)):
        return web.json_response({"error": "Preset not found"}, status=web.HTTPNotFound.status_code)

    if model.default:
        return web.json_response(
            {"error": "Default presets cannot be modified."}, status=web.HTTPBadRequest.status_code
        )

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = Preset.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate preset.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    if validated.name and await repo.get_by_name(validated.name, exclude_id=model.id):
        return web.json_response(
            data={"error": f"Preset with name '{validated.name}' already exists."},
            status=web.HTTPConflict.status_code,
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
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await repo.get(identifier)):
        return web.json_response({"error": "Preset not found"}, status=web.HTTPNotFound.status_code)

    if model.default:
        return web.json_response({"error": "Default presets cannot be deleted."}, status=web.HTTPBadRequest.status_code)

    deleted = _serialize(await repo.delete(model.id))
    notify.emit(
        Events.CONFIG_UPDATE,
        data=ConfigEvent(feature=CEFeature.PRESETS, action=CEAction.DELETE, data=deleted),
    )
    return web.json_response(data=deleted, status=web.HTTPOk.status_code, dumps=encoder.encode)
