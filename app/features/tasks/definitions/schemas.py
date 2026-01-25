from __future__ import annotations

import re
from datetime import datetime  # noqa: TC003
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.features.core.schemas import Pagination
from app.features.core.utils import parse_int


class PostFilter(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    filter: str = Field(min_length=1)
    value: str | None = None

    @field_validator("filter")
    @classmethod
    def _validate_filter(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            msg: str = f"Invalid post_filter regex pattern: {exc}"
            raise ValueError(msg) from exc
        return value


class ExtractionRule(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    type: Literal["css", "xpath", "regex", "jsonpath"]
    expression: str = Field(min_length=1)
    attribute: str | None = None
    post_filter: PostFilter | None = None

    def __getitem__(self, key: str) -> Any:
        """Support bracket notation access."""
        if not hasattr(self, key):
            raise KeyError(key)
        return getattr(self, key)


class ParseItems(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    type: Literal["css", "xpath", "jsonpath"] = "css"
    selector: str | None = Field(None, min_length=1)
    expression: str | None = Field(None, min_length=1)
    fields: dict[str, ExtractionRule]

    def get(self, key: str, default: Any = None) -> Any:
        """Get a field value by key, supporting dict-like access."""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        """Support bracket notation access."""
        if not hasattr(self, key):
            raise KeyError(key)
        return getattr(self, key)

    @model_validator(mode="after")
    def _validate_items(self) -> ParseItems:
        if not self.selector and not self.expression:
            msg = "Either 'selector' or 'expression' must be provided."
            raise ValueError(msg)
        if not self.selector:
            self.selector = self.expression
        if "link" not in self.fields:
            msg = "Container 'fields' must include a 'link' field."
            raise ValueError(msg)
        return self


class Parse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")
    items: ParseItems | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """Get a field value by key, supporting dict-like access."""
        return getattr(self, key, default)

    def field_items(self) -> list[tuple[str, Any]]:
        """Return field items like a dict, excluding private fields and 'items'."""
        data: dict[str, Any] = self.model_dump()
        return [(k, v) for k, v in data.items() if k not in ("items",)]

    def __getitem__(self, key: str) -> Any:
        """Support bracket notation access."""
        if not hasattr(self, key):
            raise KeyError(key)
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator."""
        return hasattr(self, key) and not key.startswith("_")

    @model_validator(mode="before")
    @classmethod
    def _validate_parse(cls, value: Any) -> Any:
        """Validate that we have either items or direct parsers with link."""
        if not isinstance(value, dict):
            msg: str = "Parse must be a dict"
            raise ValueError(msg)

        has_items: bool = "items" in value and value["items"] is not None
        direct_parsers: dict[str, Any] = {
            k: v for k, v in value.items() if k not in ("items",) and not k.startswith("_")
        }
        has_direct_parsers: bool = len(direct_parsers) > 0
        has_link_parser: bool = "link" in direct_parsers

        if not has_items and not has_direct_parsers:
            msg: str = "Field 'parse' must contain either 'items' or direct parsers."
            raise ValueError(msg)

        if not has_items and not has_link_parser:
            msg: str = "Missing required 'link' parser definition."
            raise ValueError(msg)

        for field_name, field_value in direct_parsers.items():
            if not isinstance(field_value, dict):
                msg: str = f"Parse field '{field_name}' must be an object."
                raise ValueError(msg)

        return value


class EngineConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    type: Literal["httpx", "selenium"] = "httpx"
    options: dict[str, Any] = Field(default_factory=dict)


class RequestConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, protected_namespaces=())
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] | None = None
    json_data: dict[str, Any] | None = None
    timeout: float | None = None
    url: str | None = None


class ResponseConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    type: Literal["html", "json"] = "html"


class Definition(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    parse: Parse
    engine: EngineConfig = Field(default_factory=EngineConfig)
    request: RequestConfig = Field(default_factory=RequestConfig)
    response: ResponseConfig = Field(default_factory=ResponseConfig)


class TaskDefinitionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)
    id: int | None = None
    name: str = Field(min_length=1)
    priority: int = Field(default=0, ge=0)
    match_url: list[str] = Field(min_length=1)
    enabled: bool = Field(default=True)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskDefinition(TaskDefinitionSummary):
    definition: Definition

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value: Any) -> int:
        if value is None:
            return 0
        return parse_int(value, field="Priority", minimum=0)

    @field_validator("match_url", mode="before")
    @classmethod
    def _validate_match_url(cls, value: Any) -> list[str]:
        """Validate that match_url is a list of strings and validate regex patterns."""
        if not isinstance(value, list):
            msg = "match_url must be a list"
            raise ValueError(msg)

        validated: list[str] = []
        for item in value:
            if not isinstance(item, str):
                msg: str = f"match_url items must be strings, got {type(item).__name__}"
                raise ValueError(msg)

            item: str = item.strip()
            if not item:
                msg = "match_url items cannot be empty"
                raise ValueError(msg)

            if item.startswith("/") and item.endswith("/") and len(item) > 2:
                pattern = item[1:-1]
                try:
                    re.compile(pattern)
                except re.error as exc:
                    msg = f"Invalid regex pattern '{pattern}': {exc}"
                    raise ValueError(msg) from exc

            validated.append(item)

        return validated


class TaskDefinitionPatch(TaskDefinition):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = None
    priority: int | None = None
    match_url: list[str] | None = None
    definition: Definition | None = None
    enabled: bool | None = None


class TaskDefinitionList(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TaskDefinitionSummary | TaskDefinition] = Field(default_factory=list)
    pagination: Pagination
