from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from app.features.core.schemas import Pagination
from app.features.core.utils import parse_int
from app.features.presets.utils import preset_name
from app.library.config import Config
from app.library.Utils import arg_converter, create_cookies_file


class Preset(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    id: int | None = None
    name: str = Field(min_length=1)
    description: str = ""
    folder: str = ""
    template: str = ""
    cookies: str = ""
    cli: str = ""
    default: bool = False
    priority: int = 0

    _cookies_file: Path | None = PrivateAttr(default=None)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> str:
        if not isinstance(value, str):
            msg: str = "Name must be a string."
            raise ValueError(msg)

        if not (value := preset_name(value)):
            msg = "Name cannot be empty."
            raise ValueError(msg)
        return value

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value: Any) -> int:
        return parse_int(value, field="Priority", minimum=0)

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

        try:
            arg_converter(args=value, level=True)
        except Exception as e:
            msg = f"Invalid command options for yt-dlp: {e!s}"
            raise ValueError(msg) from e
        return value

    def get_cookies_file(self, config: Config | None = None) -> Path | None:
        if None is not self._cookies_file:
            return self._cookies_file

        if not self.cookies or self.id is None:
            return None

        config = config or Config.get_instance()
        self._cookies_file = create_cookies_file(self.cookies, Path(config.config_path) / "cookies" / f"{self.id}.txt")
        return self._cookies_file


class PresetPatch(Preset):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    name: str | None = None
    description: str | None = None
    folder: str | None = None
    template: str | None = None
    cookies: str | None = None
    cli: str | None = None
    priority: int | None = None


class PresetList(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[Preset] = Field(default_factory=list)
    pagination: Pagination
