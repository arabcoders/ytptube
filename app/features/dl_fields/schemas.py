from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.features.core.schemas import Pagination
from app.features.core.utils import parse_int


class FieldType(str, Enum):
    STRING = "string"
    TEXT = "text"
    BOOL = "bool"


class DLField(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    id: int | None = None
    name: str = Field(min_length=1)
    description: str = ""
    field: str = Field(min_length=1)
    kind: FieldType = FieldType.TEXT
    icon: str = ""
    order: int = 0
    value: str = ""
    extras: dict[str, Any] = Field(default_factory=dict)

    @field_validator("field")
    @classmethod
    def _validate_field(cls, value: str) -> str:
        if not value.startswith("--"):
            msg: str = "Field must start with '--'."
            raise ValueError(msg)
        if " " in value:
            msg = "Field must not contain spaces."
            raise ValueError(msg)
        return value

    @field_validator("order", mode="before")
    @classmethod
    def _normalize_order(cls, value: Any) -> int:
        return parse_int(value, field="Order", minimum=0)

    @model_validator(mode="after")
    def _normalize_extras(self) -> DLField:
        if not isinstance(self.extras, dict):
            msg: str = "Extras must be a dictionary."
            raise ValueError(msg)
        return self


class DLFieldPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    name: str | None = None
    description: str | None = None
    field: str | None = None
    kind: FieldType | None = None
    icon: str | None = None
    order: int | None = None
    value: str | None = None
    extras: dict[str, Any] | None = None

    @field_validator("field")
    @classmethod
    def _validate_field(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.startswith("--"):
            msg: str = "Field must start with '--'."
            raise ValueError(msg)
        if " " in value:
            msg = "Field must not contain spaces."
            raise ValueError(msg)
        return value

    @field_validator("order", mode="before")
    @classmethod
    def _normalize_order(cls, value: Any) -> int | None:
        if value is None:
            return None
        return parse_int(value, field="Order", minimum=0)

    @model_validator(mode="after")
    def _normalize_extras(self) -> DLFieldPatch:
        if self.extras is None:
            return self
        if not isinstance(self.extras, dict):
            msg: str = "Extras must be a dictionary."
            raise ValueError(msg)
        return self


class DLFieldList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[DLField] = Field(default_factory=list)
    pagination: Pagination
