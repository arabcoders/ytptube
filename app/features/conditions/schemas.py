from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.features.core.schemas import Pagination
from app.features.core.utils import parse_int
from app.library.mini_filter import match_str
from app.library.Utils import arg_converter


class Condition(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    id: int | None = None
    name: str = Field(min_length=1)
    filter: str = ""
    cli: str = ""
    extras: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    priority: int = 0
    description: str = ""

    @field_validator("filter")
    @classmethod
    def _validate_filter(cls, value: str) -> str:
        try:
            match_str(value, {})
        except Exception as exc:
            msg: str = f"Invalid filter. '{exc!s}'."
            raise ValueError(msg) from exc
        return value

    @field_validator("cli")
    @classmethod
    def _validate_cli(cls, value: str) -> str:
        if not value:
            return ""
        try:
            arg_converter(args=value)
        except ModuleNotFoundError:
            return value
        except Exception as exc:
            msg: str = f"Invalid command options for yt-dlp. '{exc!s}'."
            raise ValueError(msg) from exc
        return value

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value: Any) -> int:
        return parse_int(value, field="Priority", minimum=0)

    @field_validator("enabled", mode="before")
    @classmethod
    def _validate_enabled(cls, value: Any) -> bool:
        if not isinstance(value, bool):
            msg: str = "Enabled must be a boolean."
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_cli_or_extras(self) -> Condition:
        if not self.cli and not self.extras:
            msg: str = "Either cli or extras must be set."
            raise ValueError(msg)
        return self


class ConditionPatch(Condition):
    """
    Model for patching Condition fields. All fields are optional.
    """

    name: str | None = None
    filter: str | None = None
    cli: str | None = None
    extras: dict[str, Any] | None = None
    enabled: bool | None = None
    priority: int | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _validate_cli_or_extras(self) -> ConditionPatch:
        return self


class ConditionList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[Condition] = Field(default_factory=list)
    pagination: Pagination
