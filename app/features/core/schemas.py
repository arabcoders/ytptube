from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Pagination(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class CEFeature(str, Enum):
    PRESETS = "presets"
    DL_FIELDS = "dl_fields"
    CONDITIONS = "conditions"
    NOTIFICATIONS = "notifications"
    TASKS_DEFINITIONS = "tasks_definitions"

    def __str__(self) -> str:
        return self.value


class CEAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"

    def __str__(self) -> str:
        return self.value


class ConfigEvent(BaseModel):
    feature: CEFeature
    action: CEAction
    data: dict[str, Any] | list[dict[str, Any]]
    extras: dict[str, Any] = Field(default_factory=dict)
