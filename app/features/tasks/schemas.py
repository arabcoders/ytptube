from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.core.schemas import Pagination


class Task(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: int | None = None
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    folder: str = ""
    preset: str = ""
    timer: str = ""
    template: str = ""
    cli: str = ""
    auto_start: bool = True
    handler_enabled: bool = True
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> str:
        if not isinstance(value, str):
            msg: str = "Name must be a string."
            raise ValueError(msg)
        value = value.strip()
        if not value:
            msg = "Name cannot be empty."
            raise ValueError(msg)
        return value

    @field_validator("url", mode="before")
    @classmethod
    def _normalize_url(cls, value: Any) -> str:
        if not isinstance(value, str):
            msg: str = "URL must be a string."
            raise ValueError(msg)
        value = value.strip()
        if not value:
            msg = "URL cannot be empty."
            raise ValueError(msg)

        from app.library.Utils import validate_url

        try:
            validate_url(value, allow_internal=True)
        except ValueError as e:
            msg = f"Invalid URL format: {e!s}"
            raise ValueError(msg) from e

        return value

    @field_validator("timer", mode="before")
    @classmethod
    def _validate_timer(cls, value: Any) -> str:
        if not value:
            return ""

        if not isinstance(value, str):
            msg: str = "Timer must be a string."
            raise ValueError(msg)

        value = value.strip()
        if not value:
            return ""

        from datetime import UTC, datetime

        try:
            from cronsim import CronSim

            CronSim(value, datetime.now(UTC))
        except Exception as e:
            msg = f"Invalid timer format: {e!s}"
            raise ValueError(msg) from e

        return value

    @field_validator("cli", mode="before")
    @classmethod
    def _validate_cli(cls, value: Any) -> str:
        if not value:
            return ""

        if not isinstance(value, str):
            msg: str = "CLI must be a string."
            raise ValueError(msg)

        value = value.strip()
        if not value:
            return ""

        from app.library.Utils import arg_converter

        try:
            arg_converter(args=value)
        except Exception as e:
            msg = f"Invalid command options for yt-dlp: {e!s}"
            raise ValueError(msg) from e

        return value


class TaskPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = None
    url: str | None = None
    folder: str | None = None
    preset: str | None = None
    timer: str | None = None
    template: str | None = None
    cli: str | None = None
    auto_start: bool | None = None
    handler_enabled: bool | None = None
    enabled: bool | None = None


class TaskList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[Task] = Field(default_factory=list)
    pagination: Pagination
