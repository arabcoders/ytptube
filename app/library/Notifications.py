import asyncio
import json
import logging
from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from aiohttp import web

from .ag_utils import ag
from .config import Config
from .encoder import Encoder
from .Events import Event, EventBus, Events
from .ItemDTO import ItemDTO
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
    on: list[str]
    request: TargetRequest

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "on": self.on,
            "request": self.request.serialize(),
        }

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.serialize().get(key, default)


class NotificationEvents:
    ADDED = Events.ADDED
    COMPLETED = Events.COMPLETED
    ERROR = Events.ERROR
    CANCELLED = Events.CANCELLED
    CLEARED = Events.CLEARED
    LOG_INFO = Events.LOG_INFO
    LOG_SUCCESS = Events.LOG_SUCCESS
    LOG_WARNING = Events.LOG_WARNING
    LOG_ERROR = Events.LOG_ERROR
    TEST = Events.TEST

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
    _targets: list[Target] = []
    """Notification targets to send events to."""

    _instance = None
    """The instance of the Notification class."""

    def __init__(
        self,
        file: str | None = None,
        client: httpx.AsyncClient | None = None,
        encoder: Encoder | None = None,
        config: Config | None = None,
    ):
        Notification._instance = self
        config: Config = config or Config.get_instance()

        self._debug = config.debug
        self._file: Path = Path(file) if file else Path(config.config_path).joinpath("notifications.json")
        self._client: httpx.AsyncClient = client or httpx.AsyncClient()
        self._encoder: Encoder = encoder or Encoder()
        self._version = config.app_version

        if self._file.exists() and "600" != self._file.stat().st_mode:
            try:
                self._file.chmod(0o600)
            except Exception:
                pass

    @staticmethod
    def get_instance() -> "Notification":
        if Notification._instance is None:
            Notification._instance = Notification()

        return Notification._instance

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

        targets = []

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

            for e in target["on"]:
                if e not in NotificationEvents.get_events().values():
                    msg = f"Invalid notification target. Invalid event '{e}' found."
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

        for target in self._targets:
            if len(target.on) > 0 and ev.event not in target.on and "test" != ev.event:
                continue

            tasks.append(self._send(target, ev))

        if wait:
            return await asyncio.gather(*tasks)

        return tasks

    async def _send(self, target: Target, ev: Event) -> dict:
        try:
            LOG.info(f"Sending Notification event '{ev.event}: {ev.id}' to '{target.name}'.")

            reqBody = {
                "method": target.request.method.upper(),
                "url": target.request.url,
                "headers": {
                    "User-Agent": f"YTPTube/{self._version}",
                    "X-Event-Id": ev.id,
                    "X-Event": ev.event,
                    "Content-Type": "application/json"
                    if "json" == target.request.type.lower()
                    else "application/x-www-form-urlencoded",
                },
            }

            if len(target.request.headers) > 0:
                for h in target.request.headers:
                    reqBody["headers"][h.key] = h.value

            body_key = "json" if "json" == target.request.type.lower() else "data"
            reqBody[body_key] = self._deep_unpack(ev.serialize())

            if "data" != target.request.data_key:
                reqBody[body_key][target.request.data_key] = reqBody[body_key]["data"]
                reqBody[body_key].pop("data", None)

            if "form" == target.request.type.lower():
                reqBody[body_key][target.request.data_key] = self._encoder.encode(
                    reqBody[body_key][target.request.data_key]
                )

            response = await self._client.request(**reqBody)

            respData = {"url": target.request.url, "status": response.status_code, "text": response.text}

            msg = f"Notification target '{target.name}' Responded to event '{ev.event}: {ev.id}' with status '{response.status_code}'."
            if self._debug and respData.get("text"):
                msg += f" body '{respData.get('text','??')}'."

            LOG.info(msg)

            return respData
        except Exception as e:
            err_msg = str(e)
            if not err_msg:
                err_msg = type(e).__name__
            LOG.error(f"Error sending Notification event '{ev.event}: {ev.id}' to '{target.name}'. '{err_msg!s}'.")
            return {"url": target.request.url, "status": 500, "text": str(ev)}

    def emit(self, e: Event, _, **kwargs):  # noqa: ARG002
        if len(self._targets) < 1 or not NotificationEvents.is_valid(e.event):
            return asyncio.sleep(0)

        return self.send(e)

    def _deep_unpack(self, data: dict) -> dict:
        for k, v in data.items():
            if isinstance(v, dict):
                data[k] = self._deep_unpack(v)
            if isinstance(v, list):
                data[k] = [self._deep_unpack(i) for i in v]
            if isinstance(v, datetime):
                data[k] = v.isoformat()
            if isinstance(v, object) and hasattr(v, "serialize"):
                data[k] = v.serialize()

        return data
