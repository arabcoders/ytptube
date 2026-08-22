from __future__ import annotations

import math
import re
from datetime import datetime  # noqa: TC003
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.features.core.schemas import Pagination
from app.features.core.utils import parse_int
from app.library.Utils import validate_url

JsonScalar = str | int | float | bool | None
MapKey = Annotated[str, Field(min_length=1, pattern=r"^[^\r\n]+$")]


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
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    type: Literal["css", "xpath", "jsonpath"] = "css"
    selector: str = Field(min_length=1)
    fields: dict[MapKey, ExtractionRule]

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
        if "url" not in self.fields:
            msg = "Container 'fields' must include a 'url' field."
            raise ValueError(msg)
        if "archive_id" in self.fields:
            msg = "Field 'archive_id' is generated internally and cannot be extracted."
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
        """Validate that parse uses either items or direct parsers, never both."""
        if not isinstance(value, dict):
            msg: str = "Parse must be a dict"
            raise ValueError(msg)

        has_items: bool = "items" in value and value["items"] is not None
        direct_parsers: dict[str, Any] = {
            k: v for k, v in value.items() if k not in ("items",) and not k.startswith("_")
        }
        has_direct_parsers: bool = len(direct_parsers) > 0
        has_url_parser: bool = "url" in direct_parsers

        if any(not field_name or "\r" in field_name or "\n" in field_name for field_name in direct_parsers):
            msg: str = "Parse field names must be non-empty single-line strings."
            raise ValueError(msg)

        if has_items and has_direct_parsers:
            msg: str = "Field 'parse' cannot combine 'items' with direct parsers."
            raise ValueError(msg)

        if not has_items and not has_direct_parsers:
            msg: str = "Field 'parse' must contain either 'items' or direct parsers."
            raise ValueError(msg)

        if not has_items and not has_url_parser:
            msg: str = "Missing required 'url' parser definition."
            raise ValueError(msg)

        if "archive_id" in direct_parsers:
            msg = "Field 'archive_id' is generated internally and cannot be extracted."
            raise ValueError(msg)

        for field_name, field_value in direct_parsers.items():
            if not isinstance(field_value, dict):
                msg: str = f"Parse field '{field_name}' must be an object."
                raise ValueError(msg)

        return value


class WaitForSelector(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    type: Literal["css", "xpath"] = "css"
    expression: str = Field(min_length=1)


class HttpEngineOptions(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    impersonate: str = Field(default="chrome", min_length=1)
    curl_default_headers: bool = True
    flaresolverr: bool = False


class BrowserEngineOptions(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    protocol: Literal["cdp"] = "cdp"
    url: str
    wait_for: WaitForSelector | None = None
    wait_timeout: float = Field(default=15, ge=0, le=300)
    page_load_timeout: float = Field(default=60, ge=0, le=300)

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            msg = "Browser URL must be an absolute http(s) URL with a host"
            raise ValueError(msg)
        return value


class EngineConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    type: Literal["http", "browser"] = "http"
    options: HttpEngineOptions | BrowserEngineOptions = Field(default_factory=HttpEngineOptions)

    @model_validator(mode="before")
    @classmethod
    def _select_options(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        engine = value.get("type", "http")
        options = value.get("options", {})
        if engine == "http":
            value["options"] = HttpEngineOptions.model_validate(options)
        elif engine == "browser":
            value["options"] = BrowserEngineOptions.model_validate(options)
        return value

    @model_validator(mode="after")
    def _validate_timeout(self) -> EngineConfig:
        for name in ("wait_timeout", "page_load_timeout"):
            value = getattr(self.options, name, None)
            if value is not None and not math.isfinite(value):
                msg = f"{name} must be finite"
                raise ValueError(msg)
        return self


class FormBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["form"]
    value: dict[MapKey, JsonScalar]


class JsonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["json"]
    value: Any


class RawBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["raw"]
    value: str


RequestBody = Annotated[FormBody | JsonBody | RawBody, Field(discriminator="type")]


class RequestConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, protected_namespaces=(), extra="forbid")
    method: Literal["GET", "POST"] = "GET"
    headers: dict[MapKey, str] = Field(default_factory=dict)
    params: dict[MapKey, JsonScalar] = Field(default_factory=dict)
    body: RequestBody | None = None
    timeout: float | None = Field(default=None, ge=0)
    url: str | None = None

    @model_validator(mode="after")
    def _validate_body(self) -> RequestConfig:
        if self.body is not None and self.method != "POST":
            msg = "Request bodies require the POST method"
            raise ValueError(msg)
        return self


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


class TaskDefinitionInspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    definition_id: int | None = Field(default=None, gt=0)
    document: TaskDefinition | None = None
    url: str = Field(min_length=1)
    preset: str | None = None

    @field_validator("url")
    @classmethod
    def _validate_inspection_url(cls, value: str) -> str:
        validate_url(value)
        return value

    @model_validator(mode="after")
    def _validate_target(self) -> TaskDefinitionInspectRequest:
        if (self.definition_id is None) == (self.document is None):
            msg = "Exactly one of 'definition_id' or 'document' is required."
            raise ValueError(msg)
        return self


class TaskDefinitionPatch(TaskDefinition):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = None
    priority: int | None = None
    match_url: list[str] | None = None
    definition: Definition | None = None
    enabled: bool | None = None


class TaskDefinitionList(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TaskDefinition | TaskDefinitionSummary] = Field(default_factory=list)
    pagination: Pagination
