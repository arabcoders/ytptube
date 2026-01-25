from __future__ import annotations

import asyncio
import logging
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.features.notifications.models import NotificationModel
from app.features.notifications.repository import NotificationsRepository
from app.features.notifications.schemas import (
    Notification,
    NotificationEvents,
    NotificationRequest,
    NotificationRequestHeader,
    NotificationRequestType,
)
from app.features.presets.schemas import Preset
from app.features.presets.service import Presets
from app.library.BackgroundWorker import BackgroundWorker
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.Events import Event, EventBus, Events
from app.library.httpx_client import async_client
from app.library.ItemDTO import Item, ItemDTO
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from collections.abc import Awaitable

    import httpx
    from aiohttp import web

LOG: logging.Logger = logging.getLogger("feature.notifications")


class Notifications(metaclass=Singleton):
    def __init__(
        self,
        repo: NotificationsRepository | None = None,
        client: httpx.AsyncClient | None = None,
        encoder: Encoder | None = None,
        config: Config | None = None,
        background_worker: BackgroundWorker | None = None,
    ) -> None:
        self._repo: NotificationsRepository = repo or NotificationsRepository.get_instance()

        config = config or Config.get_instance()

        self._debug: bool = config.debug
        self._version: str = config.app_version
        self._client: httpx.AsyncClient = client or async_client()
        self._encoder: Encoder = encoder or Encoder()
        self._offload: BackgroundWorker = background_worker or BackgroundWorker.get_instance()

    @staticmethod
    def get_instance() -> Notifications:
        return Notifications()

    async def on_shutdown(self, _: web.Application) -> None:
        pass

    def attach(self, _: web.Application) -> None:
        async def handle_event(_, __):
            await self._repo.run_migrations()

        EventBus.get_instance().subscribe(Events.STARTED, handle_event, "NotificationsRepository.run_migrations")
        EventBus.get_instance().subscribe(NotificationEvents.events(), self.emit, f"{__class__.__name__}.emit")

    async def list(self) -> list[NotificationModel]:
        return await self._repo.list()

    async def list_paginated(self, page: int, per_page: int) -> tuple[list[NotificationModel], int, int, int]:
        return await self._repo.list_paginated(page, per_page)

    async def get(self, identifier: int | str) -> NotificationModel | None:
        return await self._repo.get(identifier)

    async def create(self, item: Notification | dict) -> NotificationModel:
        if not isinstance(item, Notification):
            item = Notification.model_validate(item)
        normalized = self._normalize(item)
        payload = self._payload_from_schema(normalized)
        return await self._repo.create(payload)

    async def update(self, identifier: int | str, payload: Notification | dict) -> NotificationModel:
        if not isinstance(payload, Notification):
            payload = Notification.model_validate(payload)
        normalized = self._normalize(payload)
        update_payload = self._payload_from_schema(normalized)
        return await self._repo.update(identifier, update_payload)

    async def delete(self, identifier: int | str) -> NotificationModel:
        return await self._repo.delete(identifier)

    async def send(self, ev: Event, wait: bool = True) -> list[dict] | list[Awaitable[dict]]:
        targets = await self._repo.list()
        if len(targets) < 1:
            return []

        if not isinstance(ev.data, (ItemDTO, Item, dict)):
            LOG.debug("Received invalid item type '%s' with event '%s'.", type(ev.data), ev.event)
            return []

        tasks: list[Awaitable[dict]] = []
        apprise_targets: list[Notification] = []

        for target_model in targets:
            target = self.model_to_schema(target_model)
            if not target.enabled:
                continue

            if len(target.on) > 0 and ev.event not in target.on and NotificationEvents.TEST != ev.event:
                continue

            if NotificationEvents.TEST != ev.event and not self._check_preset(target, ev):
                continue

            if not target.request.url.startswith("http"):
                apprise_targets.append(target)
            else:
                tasks.append(self._send(target, ev))

        if len(apprise_targets) > 0:
            tasks.append(self._apprise(apprise_targets, ev))

        if wait:
            return await asyncio.gather(*tasks)

        return tasks

    def emit(self, e: Event, _, **__) -> None:
        if not NotificationEvents.is_valid(e.event):
            return

        self._offload.submit(self.send, e)

    def _normalize(self, item: Notification) -> Notification:
        if item.enabled is not None and not isinstance(item.enabled, bool):
            msg: str = "Enabled must be a boolean."
            raise ValueError(msg)

        item.on = self._filter_events(item.on)
        item.presets = self._filter_presets(item.presets)
        item.request.headers = [
            NotificationRequestHeader(key=header.key, value=header.value)
            for header in item.request.headers
            if header.key and header.value
        ]
        return item

    def _filter_events(self, events: list[str]) -> list[str]:
        if not events:
            return []

        allowed = set(NotificationEvents.get_events().values())
        valid = [event for event in events if event in allowed]
        invalid = [event for event in events if event not in allowed]

        if len(invalid) > 0 and len(valid) < 1:
            msg: str = f"Invalid notification target. Invalid events '{', '.join(invalid)}' found."
            raise ValueError(msg)

        if len(invalid) > 0:
            LOG.warning("Dropping invalid notification events: %s", ", ".join(invalid))

        return valid

    def _filter_presets(self, presets: list[str]) -> list[str]:
        if not presets:
            return []

        all_presets: list[Preset] = Presets.get_instance().get_all()
        allowed = {preset.name for preset in all_presets}
        valid = [preset for preset in presets if preset in allowed]
        invalid = [preset for preset in presets if preset not in allowed]

        if len(invalid) > 0 and len(valid) < 1:
            msg: str = f"Invalid notification target. Invalid presets '{', '.join(invalid)}' found."
            raise ValueError(msg)

        if len(invalid) > 0:
            LOG.warning("Dropping invalid notification presets: %s", ", ".join(invalid))

        return valid

    def model_to_schema(self, model: NotificationModel) -> Notification:
        headers: list[NotificationRequestHeader] = []
        if isinstance(model.request_headers, list):
            for header in model.request_headers:
                if not isinstance(header, dict):
                    continue
                key = str(header.get("key", "")).strip()
                value = str(header.get("value", "")).strip()
                if key and value:
                    headers.append(NotificationRequestHeader(key=key, value=value))

        return Notification(
            id=model.id,
            name=model.name,
            on=list(model.on or []),
            presets=list(model.presets or []),
            enabled=model.enabled,
            request=NotificationRequest.model_validate(
                {
                    "type": model.request_type,
                    "method": model.request_method,
                    "url": model.request_url,
                    "headers": headers,
                    "data_key": model.request_data_key,
                }
            ),
        )

    def _payload_from_schema(self, item: Notification) -> dict[str, Any]:
        return {
            "name": item.name,
            "on": list(item.on),
            "presets": list(item.presets),
            "enabled": item.enabled,
            "request_url": item.request.url,
            "request_method": str(item.request.method),
            "request_type": str(item.request.type),
            "request_data_key": item.request.data_key,
            "request_headers": [header.model_dump() for header in item.request.headers],
        }

    def _check_preset(self, target: Notification, ev: Event) -> bool:
        if len(target.presets) < 1:
            return True

        if not isinstance(ev.data, (Item, ItemDTO, dict)):
            return False

        preset_name: str | None = None

        if isinstance(ev.data, Item):
            preset_name = ev.data.preset

        if isinstance(ev.data, ItemDTO):
            preset_name = ev.data.preset

        if isinstance(ev.data, dict):
            preset_name = ev.data.get("preset", None)

        if not preset_name:
            return False

        return preset_name in target.presets

    async def _apprise(self, targets: list[Notification], ev: Event) -> dict:
        if not targets:
            return {}

        import apprise

        try:
            notify = apprise.Apprise(debug=self._debug)
            apr_config = Path(Config.get_instance().apprise_config)
            if apr_config.exists():
                apprise_file = apprise.AppriseConfig()
                apprise_file.add(str(apr_config))
                notify.add(apprise_file)

            for target in targets:
                notify.add(target.request.url)

            status = await notify.async_notify(
                body=ev.message or self._encoder.encode(ev.serialize()),
                title=ev.title or f"YTPTube Event: {ev.event}",
            )

            if not status:
                msg = "Apprise failed to send notification."
                raise RuntimeError(msg)  # noqa: TRY301
        except Exception as exc:
            LOG.exception(exc)
            LOG.error("Error sending Apprise notification: %s", exc)
            return {"error": str(exc), "event": ev.event, "id": ev.id, "targets": [t.name for t in targets]}

        return {}

    async def _send(self, target: Notification, ev: Event) -> dict:
        try:
            LOG.info("Sending notification event '%s: %s' to '%s'.", ev.event, ev.id, target.name)

            headers: dict[str, str] = {
                "User-Agent": f"YTPTube/{self._version}",
                "X-Event-Id": ev.id,
                "X-Event": ev.event,
                "Content-Type": "application/json"
                if NotificationRequestType.JSON == target.request.type
                else "application/x-www-form-urlencoded",
            }

            if len(target.request.headers) > 0:
                headers.update({h.key: h.value for h in target.request.headers if h.key and h.value})

            payload_data: dict[str, Any] = ev.serialize()

            if "data" != target.request.data_key:
                payload_data[target.request.data_key] = payload_data["data"]
                payload_data.pop("data", None)

            if NotificationRequestType.FORM == target.request.type:
                payload_data[target.request.data_key] = self._encoder.encode(payload_data[target.request.data_key])
                data_payload: dict[str, Any] | None = payload_data
                content_payload: str | None = None
            else:
                data_payload = None
                content_payload = self._encoder.encode(payload_data)

            response = await self._client.request(
                method=str(target.request.method).upper(),
                url=target.request.url,
                headers=headers,
                data=data_payload,
                content=content_payload,
            )

            resp_data: dict[str, Any] = {
                "url": target.request.url,
                "status": response.status_code,
                "text": response.text,
            }

            msg: str = (
                f"Notification target '{target.name}' Responded to event '{ev.event}: {ev.id}' "
                f"with status '{response.status_code}'."
            )
            if self._debug and resp_data.get("text"):
                msg += f" body '{resp_data.get('text', '??')}'."

            LOG.info(msg)

            return resp_data
        except Exception as exc:
            err_msg = str(exc) or type(exc).__name__
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            LOG.error(
                "Error sending notification event '%s: %s' to '%s'. '%s'. %s",
                ev.event,
                ev.id,
                target.name,
                err_msg,
                tb,
            )
            return {"url": target.request.url, "status": 500, "text": str(ev)}
