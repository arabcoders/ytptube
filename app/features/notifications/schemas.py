from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.core.schemas import Pagination
from app.library.Events import Events


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

    @staticmethod
    def events() -> list[str]:
        return [
            getattr(NotificationEvents, ev)
            for ev in dir(NotificationEvents)
            if not ev.startswith("_") and not callable(getattr(NotificationEvents, ev))
        ]

    @staticmethod
    def is_valid(event: str) -> bool:
        return event in NotificationEvents.get_events().values()


class NotificationRequestType(str, Enum):
    JSON = "json"
    FORM = "form"

    def __str__(self) -> str:
        return self.value


class NotificationRequestMethod(str, Enum):
    POST = "POST"
    PUT = "PUT"

    def __str__(self) -> str:
        return self.value


class NotificationRequestHeader(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    key: str = Field(min_length=1)
    value: str = Field(min_length=1)


class NotificationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    type: NotificationRequestType = NotificationRequestType.JSON
    method: NotificationRequestMethod = NotificationRequestMethod.POST
    url: str = Field(min_length=1)
    headers: list[NotificationRequestHeader] = Field(default_factory=list)
    data_key: str = Field(default="data", min_length=1)

    @field_validator("method", mode="before")
    @classmethod
    def _normalize_method(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, NotificationRequestMethod):
            return value
        return str(value).upper()

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, NotificationRequestType):
            return value
        return str(value).lower()


class NotificationRequestPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    type: NotificationRequestType | None = None
    method: NotificationRequestMethod | None = None
    url: str | None = None
    headers: list[NotificationRequestHeader] | None = None
    data_key: str | None = None


class Notification(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    id: int | None = None
    name: str = Field(min_length=1)
    on: list[str] = Field(default_factory=list)
    presets: list[str] = Field(default_factory=list)
    enabled: bool = True
    request: NotificationRequest

    @field_validator("on", "presets", mode="before")
    @classmethod
    def _normalize_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]


class NotificationPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    name: str | None = None
    on: list[str] | None = None
    presets: list[str] | None = None
    enabled: bool | None = None
    request: NotificationRequestPatch | None = None


class NotificationList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[Notification] = Field(default_factory=list)
    pagination: Pagination
