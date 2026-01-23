import logging
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response
from pydantic import ValidationError

from app.features.core.schemas import CEAction, CEFeature, ConfigEvent, Pagination
from app.features.core.utils import build_pagination, format_validation_errors, normalize_pagination
from app.features.notifications.schemas import Notification, NotificationEvents, NotificationList, NotificationPatch
from app.features.notifications.service import Notifications
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.router import route

LOG: logging.Logger = logging.getLogger(__name__)


def _model(model: Any) -> Notification:
    return Notifications.get_instance().model_to_schema(model)


def _serialize(model: Any) -> dict:
    return _model(model).model_dump()


@route("GET", "api/notifications/", "notifications_list")
async def notifications_list(request: Request, encoder: Encoder) -> Response:
    page, per_page = normalize_pagination(request)
    items, total, current_page, total_pages = await Notifications.get_instance().list_paginated(page, per_page)
    return web.json_response(
        data=NotificationList(
            items=[_model(model) for model in items],
            pagination=Pagination.model_validate(build_pagination(total, current_page, per_page, total_pages)),
        ),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/notifications/events/", "notifications_events")
async def notifications_events(encoder: Encoder) -> Response:
    return web.json_response(
        data={"events": list(NotificationEvents.get_events().values())},
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/notifications/test/", "notification_test")
async def notification_test(encoder: Encoder, notify: EventBus) -> Response:
    notify.emit(Events.TEST, title="Test Notification", message="This is a test notification.")
    return web.json_response(data={}, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/notifications/", "notification_add")
async def notifications_add(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        item: Notification = Notification.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate notification.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        saved = _serialize(await Notifications.get_instance().create(item))
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPBadRequest.status_code)

    notify.emit(
        Events.CONFIG_UPDATE,
        data=ConfigEvent(feature=CEFeature.NOTIFICATIONS, action=CEAction.CREATE, data=saved),
    )
    return web.json_response(data=saved, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("GET", r"api/notifications/{id:\d+}", "notification_get")
async def notifications_get(request: Request, encoder: Encoder) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await Notifications.get_instance().get(identifier)):
        return web.json_response({"error": "Notification not found"}, status=web.HTTPNotFound.status_code)

    return web.json_response(data=_serialize(model), status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("DELETE", r"api/notifications/{id:\d+}", "notification_delete")
async def notifications_delete(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    try:
        deleted = _serialize(await Notifications.get_instance().delete(identifier))
        notify.emit(
            Events.CONFIG_UPDATE,
            data=ConfigEvent(feature=CEFeature.NOTIFICATIONS, action=CEAction.DELETE, data=deleted),
        )
        return web.json_response(
            data=deleted,
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )
    except KeyError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPNotFound.status_code)


@route("PATCH", r"api/notifications/{id:\d+}", "notification_patch")
async def notifications_patch(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await Notifications.get_instance().get(identifier)):
        return web.json_response({"error": "Notification not found"}, status=web.HTTPNotFound.status_code)

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = NotificationPatch.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate notification.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    current = _model(model).model_dump()
    if validated.name is not None:
        current["name"] = validated.name
    if validated.on is not None:
        current["on"] = validated.on
    if validated.presets is not None:
        current["presets"] = validated.presets
    if validated.enabled is not None:
        current["enabled"] = validated.enabled

    if validated.request is not None:
        request_payload = current.get("request", {})
        if validated.request.url is not None:
            request_payload["url"] = validated.request.url
        if validated.request.method is not None:
            request_payload["method"] = validated.request.method
        if validated.request.type is not None:
            request_payload["type"] = validated.request.type
        if validated.request.headers is not None:
            request_payload["headers"] = [header.model_dump() for header in validated.request.headers]
        if validated.request.data_key is not None:
            request_payload["data_key"] = validated.request.data_key
        current["request"] = request_payload

    try:
        updated = _serialize(await Notifications.get_instance().update(model.id, current))
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPBadRequest.status_code)
    except KeyError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPNotFound.status_code)

    notify.emit(
        Events.CONFIG_UPDATE,
        data=ConfigEvent(feature=CEFeature.NOTIFICATIONS, action=CEAction.UPDATE, data=updated),
    )
    return web.json_response(
        data=updated,
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("PUT", r"api/notifications/{id:\d+}", "notification_update")
async def notifications_update(request: Request, encoder: Encoder, notify: EventBus) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    if not (model := await Notifications.get_instance().get(identifier)):
        return web.json_response({"error": "Notification not found"}, status=web.HTTPNotFound.status_code)

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = Notification.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate notification.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        updated = _serialize(await Notifications.get_instance().update(model.id, validated))
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPBadRequest.status_code)
    except KeyError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPNotFound.status_code)

    notify.emit(
        Events.CONFIG_UPDATE,
        data=ConfigEvent(feature=CEFeature.NOTIFICATIONS, action=CEAction.UPDATE, data=updated),
    )
    return web.json_response(data=updated, status=web.HTTPOk.status_code, dumps=encoder.encode)
