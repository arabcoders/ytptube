from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from app.library.config import Config


def args(params: dict[str, Any]) -> dict[str, str]:
    values = (params.get("extractor_args") or {}).get("media") or {}
    result = {}
    for key, value in values.items():
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if not isinstance(value, str) or not value.strip():
            msg = "Media options require a single non-blank value"
            raise ValueError(msg)
        result[key] = value
    return result


def load(name: str, options: dict[str, str]) -> tuple[dict[str, Any], Path]:
    if not (filename := options.get("config")):
        msg = "Media options require a config file"
        raise ValueError(msg)
    path = Path(filename).expanduser()
    if not path.is_absolute():
        path = Path(Config.get_instance().config_path) / path
    try:
        with path.open("rb") as file:
            values = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        msg = f"Unable to read {name} configuration file"
        raise ValueError(msg) from exc
    data = values.get(name)
    if data is None or data == {}:
        msg = f"{name.capitalize()} service is not configured in the selected TOML file"
        raise ValueError(msg)
    if not isinstance(data, dict):
        msg = f"{name} must be a table"
        raise ValueError(msg)
    return data, path
