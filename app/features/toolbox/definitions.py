from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    computed_field,
    create_model,
    model_validator,
)

ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
INPUT = "TB_IN"
OUTPUT = "TB_OUT"


class Param(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    default: str | bool | int | float
    min: int | float | None = None
    max: int | float | None = None
    choices: list[str] | None = None

    @model_validator(mode="after")
    def check(self) -> Self:
        default = self.default
        if isinstance(default, str):
            if (
                not self.choices
                or default not in self.choices
                or any("\0" in item for item in self.choices)
                or len(self.choices) != len(set(self.choices))
            ):
                msg = "String parameters need distinct choices that include the default."
                raise ValueError(msg)
        elif self.choices is not None:
            msg = "Only string parameters support choices."
            raise ValueError(msg)

        if self.min is not None or self.max is not None:
            if isinstance(default, (str, bool)) or (
                isinstance(default, int) and any(isinstance(bound, float) for bound in (self.min, self.max))
            ):
                msg = "Use numeric limits that match the parameter type."
                raise ValueError(msg)
            if (self.min is not None and default < self.min) or (self.max is not None and default > self.max):
                msg = "The default must be within the parameter limits."
                raise ValueError(msg)
        return self

    def choice(self, value: str) -> str:
        if self.choices is None or value not in self.choices:
            msg = "Select one of the configured choices."
            raise ValueError(msg)
        return value


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    name: str = Field(min_length=1)
    description: str = ""
    output_extension: str
    supports_overwrite: bool = False
    command: list[str] = Field(min_length=1)
    env: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Param] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check(self) -> Self:
        extension = self.output_extension
        if (
            not self.name.strip()
            or not extension.startswith(".")
            or extension == ".."
            or Path(extension).parts != (extension,)
            or "\0" in extension
        ):
            msg = "A tool needs a name and a file extension such as .flac."
            raise ValueError(msg)
        if not self.command[0].strip() or any("\0" in arg for arg in self.command):
            msg = "The command must start with an executable and contain valid arguments."
            raise ValueError(msg)
        names = (*self.env, *self.params)
        keys = {key.upper() for key in names}
        if (
            not all(ENV_KEY.fullmatch(key) for key in names)
            or any("\0" in value for value in self.env.values())
            or len(keys) != len(names)
            or {INPUT, OUTPUT}.intersection(keys)
        ):
            msg = "Use distinct environment and parameter names. Input and Output names are reserved."
            raise ValueError(msg)
        return self

    def options(self) -> type[BaseModel]:
        fields: dict[str, Any] = {}
        for name, param in self.params.items():
            title = name.replace("_", " ").capitalize()
            key = f"param_{name}"
            if param.choices is not None:
                choices: list[JsonValue] = [*param.choices]
                fields[key] = (
                    Annotated[str, AfterValidator(param.choice)],
                    Field(default=param.default, alias=name, title=title, json_schema_extra={"enum": choices}),
                )
            else:
                fields[key] = (
                    type(param.default),
                    Field(default=param.default, alias=name, title=title, ge=param.min, le=param.max),
                )
        return create_model(
            "ToolboxOptions",
            __config__=ConfigDict(extra="forbid", strict=True, allow_inf_nan=False),
            **fields,
        )


class ShippedDefinition(Definition):
    default_key: str = Field(exclude=True)


class SavedDefinition(Definition):
    id: int
    default_key: str | None = Field(exclude=True)

    @computed_field
    @property
    def default(self) -> bool:
        return self.default_key is not None
