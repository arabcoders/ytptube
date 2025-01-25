import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from typing import List, TypedDict
import uuid

import httpx

from .config import Config
from .ItemDTO import ItemDTO
from .Singleton import Singleton
from .Utils import ag, validateUUID
from .version import APP_VERSION
from .encoder import Encoder

LOG = logging.getLogger("notifications")


class targetRequestHeader(TypedDict):
    """Request header details for a notification target."""

    key: str
    value: str


class targetRequest(TypedDict):
    """Request details for a notification target."""

    type: str
    method: str
    url: str
    headers: list[targetRequestHeader] = []


class Target(TypedDict):
    """Notification target details."""

    id: str
    name: str
    on: List[str]
    request: targetRequest


class Notification(metaclass=Singleton):
    targets: list[Target] = []
    """Notification targets to send events to."""

    allowed_events: tuple = (
        "added",
        "completed",
        "error",
        "not_live",
        "canceled",
        "cleared",
        "log_info",
        "log_success",
    )
    """Events that can be sent to the targets."""

    _instance = None

    def __init__(self):
        Notification._instance = self

        config = Config.get_instance()

        self._debug = config.debug
        self.file: str = os.path.join(config.config_path, "notifications.json")
        self._client: httpx.AsyncClient = httpx.AsyncClient()
        self._encoder: Encoder = Encoder()

        if os.path.exists(self.file) and os.path.getsize(self.file) > 10:
            self.load()

    @staticmethod
    def get_instance() -> "Notification":
        if Notification._instance is None:
            Notification._instance = Notification()

        return Notification._instance

    def getTargets(self) -> list[Target]:
        """Get the list of notification targets."""
        return self.targets

    def clearTargets(self) -> "Notification":
        """Clear the list of notification targets."""
        self.targets.clear()
        return self

    def save(self, targets: list[Target] | None = None) -> "Notification":
        """
        Save notification targets to the file.

        Args:
            targets (list[Target]|None): The list of targets to save.

        Returns:
            Notification: The Notification instance.
        """
        LOG.info(f"Saving notification targets to '{self.file}'.")
        try:
            with open(self.file, "w") as f:
                f.write(json.dumps(targets or self.targets, indent=4))
        except Exception as e:
            LOG.error(f"Error saving notification targets to '{self.file}'. '{e}'")
            pass

        return self

    def load(self):
        """Load or reload notification targets from the file."""
        if len(self.targets) > 0:
            LOG.info("Clearing existing notification targets.")
            self.targets.clear()

        modified = False

        targets = []

        if not os.path.exists(self.file) or os.path.getsize(self.file) < 10:
            return

        LOG.info(f"Loading notification targets from '{self.file}'.")

        try:
            with open(self.file, "r") as f:
                targets = json.load(f)
        except Exception as e:
            LOG.error(f"Error loading notification targets from '{self.file}'. '{e}'")
            pass

        for target in targets:
            try:
                try:
                    Notification.validate(target)
                except ValueError as e:
                    LOG.error(f"Invalid notification target '{target}'. '{e}'")
                    continue

                if "on" not in target:
                    target["on"] = []
                    modified = True

                if "type" not in target["request"]:
                    target["request"]["type"] = "json"
                    modified = True

                if "method" not in target["request"]:
                    target["request"]["method"] = "POST"
                    modified = True

                if "id" not in target or validateUUID(target["id"], version=4) is False:
                    target["id"] = str(uuid.uuid4())
                    modified = True

                target = Target(
                    id=target.get("id"),
                    name=target.get("name"),
                    on=target.get("on", []),
                    request=targetRequest(
                        type=target.get("request", {}).get("type", "json"),
                        method=target.get("request", {}).get("method", "POST"),
                        url=target.get("request", {}).get("url"),
                        headers=[
                            targetRequestHeader(key=h.get("key"), value=h.get("value"))
                            for h in target.get("request", {}).get("headers", [])
                        ],
                    ),
                )

                self.targets.append(target)

                LOG.info(
                    f"Will send '{target['on'] if len(target['on']) > 0 else 'all'}' as {target['request']['type']} notification events to '{target['name']}'."
                )
            except Exception as e:
                LOG.error(f"Error loading notification target '{target}'. '{e}'")
                pass

        if modified:
            self.save()

    @staticmethod
    def validate(target: Target | dict) -> bool:
        """
        Validate a notification target.

        Args:
            target (Target|dict): The target to validate.

        Returns:
            bool: True if the target is valid, False otherwise.
        """

        if "id" not in target or validateUUID(target["id"], version=4) is False:
            raise ValueError("Invalid notification target. No ID found.")

        if "name" not in target:
            raise ValueError("Invalid notification target. No name found.")

        if "request" not in target:
            raise ValueError("Invalid notification target. No request details found.")

        if "url" not in target["request"]:
            raise ValueError("Invalid notification target. No URL found.")

        if "method" in target["request"] and target["request"]["method"].upper() not in ["POST", "PUT"]:
            raise ValueError("Invalid notification target. Invalid method found.")

        if "type" in target["request"] and target["request"]["type"].lower() not in ["json", "form"]:
            raise ValueError("Invalid notification target. Invalid type found.")

        if "on" in target:
            if not isinstance(target["on"], list):
                raise ValueError("Invalid notification target. Invalid 'on' event list found.")

            for e in target["on"]:
                if e not in Notification.allowed_events:
                    raise ValueError(f"Invalid notification target. Invalid event '{e}' found.")

        if "headers" in target["request"]:
            if not isinstance(target["request"]["headers"], list):
                raise ValueError("Invalid notification target. Invalid headers list found.")

            for h in target["request"]["headers"]:
                if "key" not in h:
                    raise ValueError("Invalid notification target. No header key found.")
                if "value" not in h:
                    raise ValueError("Invalid notification target. No header value found.")

        return True

    async def send(self, event: str, item: ItemDTO | dict) -> list[dict]:
        if len(self.targets) < 1:
            return []

        if not isinstance(item, ItemDTO) and not isinstance(item, dict):
            LOG.debug(f"Received invalid item type '{type(item)}' with event '{event}'.")
            return []

        tasks = []

        for target in self.targets:
            if len(target["on"]) > 0 and event not in target["on"] and "test" != event:
                continue

            tasks.append(self._send(event, target, item))

        return await asyncio.gather(*tasks)

    async def _send(self, event: str, target: Target, item: ItemDTO | dict) -> dict:
        req: targetRequest = target["request"]

        try:
            itemId = ag(item, ["id", "_id"], "??")
        except Exception:
            itemId = "??"

        try:
            LOG.info(f"Sending Notification event '{event}' id '{itemId}' to '{target.get('name')}'.")
            reqBody = {
                "method": req["method"].upper(),
                "url": req["url"],
                "headers": {
                    "User-Agent": f"YTPTube/{APP_VERSION}",
                    "Content-Type": "application/json"
                    if "json" == req["type"].lower()
                    else "application/x-www-form-urlencoded",
                },
            }

            if len(req["headers"]) > 0:
                for h in req["headers"]:
                    reqBody["headers"][h["key"]] = h["value"]

            reqBody["json" if "json" == req["type"].lower() else "data"] = {
                "event": event,
                "created_at": datetime.now(tz=timezone.utc).isoformat(),
                "payload": item.__dict__ if isinstance(item, ItemDTO) else item,
            }

            if "form" == req["type"].lower():
                reqBody["data"]["payload"] = self._encoder.encode(reqBody["data"]["payload"])

            response = await self._client.request(**reqBody)

            respData = {"url": req["url"], "status": response.status_code, "text": response.text}

            msg = f"Notification target '{target['name']}' Responded to event '{event}' id '{itemId}' with status '{response.status_code}'."
            if self._debug and respData.get("text"):
                msg += f" body '{respData.get('text','??')}'."

            LOG.info(msg)

            return respData
        except Exception as e:
            LOG.error(f"Error sending Notification event '{event}' id '{itemId}' to '{target['name']}'. '{e}'.")
            return {"url": req["url"], "status": 500, "text": str(e)}

    def emit(self, event, data, **kwargs):
        if len(self.targets) < 1:
            return False

        if event not in self.allowed_events and "test" != event:
            return False

        return self.send(event, data)
