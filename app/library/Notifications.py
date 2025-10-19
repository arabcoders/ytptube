import asyncio
import json
import logging
import traceback
from collections.abc import Awaitable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from aiohttp import web

from .ag_utils import ag
from .BackgroundWorker import BackgroundWorker
from .config import Config
from .encoder import Encoder
from .Events import Event, EventBus, Events
from .ItemDTO import Item, ItemDTO
from .Presets import Preset, Presets
from .Singleton import Singleton
from .Utils import validate_uuid

LOG = logging.getLogger("notifications")


@dataclass(kw_only=True)
class TargetRequestHeader:
    """Request header details for a notification target."""

    key: str
    value: str

    def serialize(self) -> dict:
        return {"key": self.key, "value": self.value}

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.serialize().get(key, default)


@dataclass(kw_only=True)
class TargetRequest:
    """Request details for a notification target."""

    type: str
    method: str
    url: str
    headers: list[TargetRequestHeader] = field(default_factory=list)
    data_key: str = "data"

    def serialize(self) -> dict:
        return {
            "type": self.type,
            "method": self.method,
            "url": self.url,
            "data_key": self.data_key,
            "headers": [h.serialize() for h in self.headers],
        }

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return ag(self.serialize(), key, default)


@dataclass(kw_only=True)
class Target:
    """Notification target details."""

    id: str
    name: str
    on: list[str] = field(default_factory=list)
    presets: list[str] = field(default_factory=list)
    request: TargetRequest

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "on": self.on,
            "presets": self.presets,
            "request": self.request.serialize(),
        }

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.serialize().get(key, default)


class NotificationEvents:
    TEST: str = Events.TEST

    ITEM_ADDED: str = Events.ITEM_ADDED
    ITEM_COMPLETED: str = Events.ITEM_COMPLETED
    ITEM_CANCELLED: str = Events.ITEM_CANCELLED
    ITEM_DELETED: str = Events.ITEM_DELETED
    ITEM_PAUSED: str = Events.ITEM_PAUSED
    ITEM_RESUMED: str = Events.ITEM_RESUMED
    ITEM_MOVED: str = Events.ITEM_MOVED

    PAUSED: str = Events.PAUSED
    RESUMED: str = Events.RESUMED

    LOG_INFO: str = Events.LOG_INFO
    LOG_SUCCESS: str = Events.LOG_SUCCESS
    LOG_WARNING: str = Events.LOG_WARNING
    LOG_ERROR: str = Events.LOG_ERROR

    TASK_DISPATCHED: str = Events.TASK_DISPATCHED

    @staticmethod
    def get_events() -> dict[str, str]:
        return {k: v for k, v in vars(NotificationEvents).items() if not k.startswith("__") and not callable(v)}

    def events() -> list:
        return [
            getattr(NotificationEvents, ev)
            for ev in dir(NotificationEvents)
            if not ev.startswith("_") and not callable(getattr(NotificationEvents, ev))
        ]

    @staticmethod
    def is_valid(event: str) -> bool:
        return event in NotificationEvents.get_events().values()


class Notification(metaclass=Singleton):
    def __init__(
        self,
        file: str | None = None,
        client: httpx.AsyncClient | None = None,
        encoder: Encoder | None = None,
        config: Config | None = None,
        background_worker: BackgroundWorker | None = None,
    ):
        self._targets: list[Target] = []
        "Notification targets to send events to."

        config: Config = config or Config.get_instance()

        self._debug: bool = config.debug
        "Debug mode."
        self._file: Path = Path(file) if file else Path(config.config_path).joinpath("notifications.json")
        "File to store notification targets."
        self._client: httpx.AsyncClient = client or httpx.AsyncClient()
        "HTTP client to send requests."
        self._encoder: Encoder = encoder or Encoder()
        "Encoder to encode data."
        self._version: str = config.app_version
        "Application version."
        self._offload: BackgroundWorker = background_worker or BackgroundWorker.get_instance()
        "Background worker to offload tasks to."

        if self._file.exists() and "600" != self._file.stat().st_mode:
            try:
                self._file.chmod(0o600)
            except Exception:
                pass

    @staticmethod
    def get_instance(
        file: str | None = None,
        client: httpx.AsyncClient | None = None,
        encoder: Encoder | None = None,
        config: Config | None = None,
        background_worker: BackgroundWorker | None = None,
    ) -> "Notification":
        """
        Get the instance of the class.
        """
        return Notification(
            file=file, client=client, encoder=encoder, config=config, background_worker=background_worker
        )

    def attach(self, _: web.Application):
        """
        Attach the class to the application.

        Args:
            _ (web.Application): The aiohttp application.

        """
        self.load()
        EventBus.get_instance().subscribe(NotificationEvents.events(), self.emit, f"{__class__.__name__}.emit")

    def get_targets(self) -> list[Target]:
        """Get the list of notification targets."""
        return self._targets

    def clear(self) -> "Notification":
        """Clear the list of notification targets."""
        self._targets.clear()
        return self

    def save(self, targets: list[Target]) -> "Notification":
        """
        Save notification targets to the file.

        Args:
            targets (list[Target]|None): The list of targets to save.

        Returns:
            Notification: The Notification instance.

        """
        try:
            self._file.write_text(json.dumps([t.serialize() for t in targets], indent=4))
            LOG.info(f"Updated '{self._file}'.")
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Error saving '{self._file}'. '{e!s}'")

        return self

    def load(self) -> "Notification":
        """Load or reload notification targets from the file."""
        if len(self._targets) > 0:
            self.clear()

        if not self._file.exists() or self._file.stat().st_size < 1:
            return self

        targets: list = []

        try:
            LOG.info(f"Loading '{self._file}'.")
            targets = json.loads(self._file.read_text())
        except Exception as e:
            LOG.error(f"Error loading '{self._file}'. '{e!s}'")

        for target in targets:
            try:
                try:
                    Notification.validate(target)
                    target: Target = self.make_target(target)
                except ValueError as e:
                    name = target.get("name") or target.get("id") or target.get("request", {}).get("url") or "unknown"
                    LOG.error(f"Invalid notification target '{name}'. '{e!s}'")
                    continue

                self._targets.append(target)

                LOG.info(
                    f"Send '{target.request.type}' request on '{', '.join(target.on) if len(target.on) > 0 else 'all events'}' to '{target.name}'."
                )
            except Exception as e:
                LOG.error(f"Error loading notification target '{target}'. '{e!s}'")

        return self

    def make_target(self, target: dict) -> Target:
        """
        Make a notification target from a dictionary.

        Args:
            target (dict): The target details.

        Returns:
            Target: The notification target.

        """
        return Target(
            id=target.get("id"),
            name=target.get("name"),
            on=target.get("on", []),
            presets=target.get("presets", []),
            request=TargetRequest(
                type=target.get("request", {}).get("type", "json"),
                method=target.get("request", {}).get("method", "POST"),
                url=target.get("request", {}).get("url"),
                data_key=target.get("request", {}).get("data_key", "data"),
                headers=[
                    TargetRequestHeader(
                        key=str(h.get("key", "")).strip(),
                        value=str(h.get("value", "")).strip(),
                    )
                    for h in target.get("request", {}).get("headers", [])
                ],
            ),
        )

    @staticmethod
    def validate(target: Target | dict) -> bool:
        """
        Validate a notification target.

        Args:
            target (Target|dict): The target to validate.

        Returns:
            bool: True if the target is valid, False otherwise.

        """
        if not isinstance(target, dict):
            target = target.serialize()

        if "id" not in target or validate_uuid(target["id"], version=4) is False:
            msg = "Invalid notification target. No ID found."
            raise ValueError(msg)

        if "name" not in target:
            msg = "Invalid notification target. No name found."
            raise ValueError(msg)

        if "request" not in target:
            msg = "Invalid notification target. No request details found."
            raise ValueError(msg)

        if "url" not in target["request"]:
            msg = "Invalid notification target. No URL found."
            raise ValueError(msg)

        if "data_key" not in target["request"]:
            target["request"]["data_key"] = "data"

        if "method" in target["request"] and target["request"]["method"].upper() not in ["POST", "PUT"]:
            msg = "Invalid notification target. Invalid method found."
            raise ValueError(msg)

        if "type" in target["request"] and target["request"]["type"].lower() not in ["json", "form"]:
            msg = "Invalid notification target. Invalid type found."
            raise ValueError(msg)

        if "on" in target:
            if not isinstance(target["on"], list):
                msg = "Invalid notification target. Invalid 'on' event list found."
                raise ValueError(msg)

            removed_events: list = []
            all_events: dict[str, str] = NotificationEvents.get_events().values()
            for e in target["on"]:
                if e not in all_events:
                    removed_events.append(e)
                    target["on"].remove(e)
                    continue

            if len(removed_events) > 0 and len(target["on"]) < 1:
                msg: str = f"Invalid notification target. Invalid events '{', '.join(removed_events)}' found."
                raise ValueError(msg)

        if "presets" in target:
            if not isinstance(target["presets"], list):
                msg = "Invalid notification target. Invalid 'presets' list found."
                raise ValueError(msg)

            removed_presets: list = []
            all_presets: list[Preset] = Presets.get_instance().get_all()

            for p in target["presets"]:
                if p not in [ap.name for ap in all_presets]:
                    removed_presets.append(p)
                    target["presets"].remove(p)
                    continue

            if len(removed_presets) > 0 and len(target["presets"]) < 1:
                msg: str = f"Invalid notification target. Invalid presets '{', '.join(removed_presets)}' found."
                raise ValueError(msg)

        if "headers" in target["request"]:
            if not isinstance(target["request"]["headers"], list):
                msg = "Invalid notification target. Invalid headers list found."
                raise ValueError(msg)

            for h in target["request"]["headers"]:
                if "key" not in h:
                    msg = "Invalid notification target. No header key found."
                    raise ValueError(msg)
                if "value" not in h:
                    msg = "Invalid notification target. No header value found."
                    raise ValueError(msg)

        return True

    async def send(self, ev: Event, wait: bool = True) -> list[dict] | Awaitable[list[dict]]:
        if len(self._targets) < 1:
            return []

        if not isinstance(ev.data, ItemDTO) and not isinstance(ev.data, dict):
            LOG.debug(f"Received invalid item type '{type(ev.data)}' with event '{ev.event}'.")
            return []

        tasks = []

        apprise_targets: list[Target] = []

        for target in self._targets:
            if len(target.on) > 0 and ev.event not in target.on and "test" != ev.event:
                continue

            if "test" != ev.event and not self._check_preset(target, ev):
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

    def _check_preset(self, target: Target, ev: Event) -> bool:
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

    async def _apprise(self, target: list[Target], ev: Event) -> dict:
        if not target or not isinstance(target, list):
            return {}

        import apprise

        try:
            notify = apprise.Apprise(debug=self._debug)
            apr_config = Path(Config.get_instance().apprise_config)
            if apr_config.exists():
                apprise_config = notify.AppriseConfig()
                apprise_config.add(apr_config)
                notify.add(apprise_config)

            for t in target:
                notify.add(t.request.url)

            status = await notify.async_notify(
                body=ev.message or json.dumps(ev.serialize(), sort_keys=False, ensure_ascii=False),
                title=ev.title or f"YTPTube Event: {ev.event}",
            )

            if not status:
                msg = "Apprise failed to send notification."
                raise RuntimeError(msg)  # noqa: TRY301
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Error sending Apprise notification: {e!s}")
            return {"error": str(e), "event": ev.event, "id": ev.id, "targets": [t.name for t in target]}

        return {}

    async def _send(self, target: Target, ev: Event) -> dict:
        try:
            LOG.info(f"Sending Notification event '{ev.event}: {ev.id}' to '{target.name}'.")

            headers: dict[str, str] = {
                "User-Agent": f"YTPTube/{self._version}",
                "X-Event-Id": ev.id,
                "X-Event": ev.event,
                "Content-Type": "application/json"
                if "json" == target.request.type.lower()
                else "application/x-www-form-urlencoded",
            }

            if len(target.request.headers) > 0:
                headers.update({h.key: h.value for h in target.request.headers if h.key and h.value})

            payload: dict = ev.serialize()

            if "data" != target.request.data_key:
                payload[target.request.data_key] = payload["data"]
                payload.pop("data", None)

            if "form" == target.request.type.lower():
                payload[target.request.data_key] = self._encoder.encode(payload[target.request.data_key])
            else:
                payload = self._encoder.encode(payload)

            response = await self._client.request(
                method=target.request.method.upper(),
                url=target.request.url,
                headers=headers,
                data=payload if "form" == target.request.type.lower() else None,
                content=payload if "json" == target.request.type.lower() else None,
            )

            respData: dict[str, Any] = {
                "url": target.request.url,
                "status": response.status_code,
                "text": response.text,
            }

            msg: str = f"Notification target '{target.name}' Responded to event '{ev.event}: {ev.id}' with status '{response.status_code}'."
            if self._debug and respData.get("text"):
                msg += f" body '{respData.get('text', '??')}'."

            LOG.info(msg)

            return respData
        except Exception as e:
            err_msg = str(e)
            if not err_msg:
                err_msg: str = type(e).__name__

            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            LOG.error(f"Error sending Notification event '{ev.event}: {ev.id}' to '{target.name}'. '{err_msg!s}'. {tb}")
            return {"url": target.request.url, "status": 500, "text": str(ev)}

    def emit(self, e: Event, _, **__) -> None:
        if len(self._targets) < 1 or not NotificationEvents.is_valid(e.event):
            return

        self._offload.submit(self.send, e)
        return

    async def noop(self) -> None:
        return None
