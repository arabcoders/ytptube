from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from app.features.core.migration import Migration as FeatureMigration
from app.library.config import Config
from app.library.logging import get_logger

if TYPE_CHECKING:
    from app.features.tasks.definitions.repository import TaskDefinitionsRepository

LOG = get_logger()
DEFAULT_SELENIUM_URL = "http://localhost:4444/wd/hub"


def normalize_definition(definition: object) -> object:
    if not isinstance(definition, dict):
        return definition
    engine = definition.get("engine")
    if isinstance(engine, dict):
        if engine.get("type") == "httpx":
            engine["type"] = "http"
            engine["options"] = {}
        elif engine.get("type") == "selenium":
            old_options = engine.get("options") if isinstance(engine.get("options"), dict) else {}
            url = old_options.get("url")
            try:
                parsed = urlsplit(url) if isinstance(url, str) else None
            except ValueError:
                parsed = None
            options: dict[str, object] = {
                "protocol": "cdp",
                "url": url
                if parsed and parsed.scheme in {"http", "https"} and parsed.hostname
                else DEFAULT_SELENIUM_URL,
            }
            wait_for = old_options.get("wait_for")
            if isinstance(wait_for, dict):
                expression = wait_for.get("expression", wait_for.get("value"))
                wait_type = wait_for.get("type", "css")
                if isinstance(expression, str) and expression and wait_type in {"css", "xpath"}:
                    options["wait_for"] = {"type": wait_type, "expression": expression}
            for key in ("wait_timeout", "page_load_timeout"):
                value = old_options.get(key)
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    and 0 <= value <= 300
                ):
                    options[key] = value
            engine["type"] = "browser"
            engine["options"] = options

    request = definition.get("request")
    if isinstance(request, dict):
        created_body = False
        if "body" not in request:
            if request.get("json_data") is not None:
                request["body"] = {"type": "json", "value": request["json_data"]}
                created_body = True
            elif request.get("data") is not None:
                request["body"] = {"type": "form", "value": request["data"]}
                created_body = True
        request.pop("data", None)
        request.pop("json_data", None)
        if created_body:
            request["method"] = "POST"

    parse = definition.get("parse")
    if isinstance(parse, dict):
        if "link" in parse:
            parse["url"] = parse.pop("link")
        items = parse.get("items")
        direct_keys = [key for key in parse if key != "items" and not key.startswith("_")]
        if items:
            for key in list(parse):
                if key != "items" and not key.startswith("_"):
                    parse.pop(key)
        elif direct_keys:
            parse.pop("items", None)
        if isinstance(items, dict):
            fields = items.get("fields")
            if isinstance(fields, dict) and "link" in fields:
                fields["url"] = fields.pop("link")
            selector = items.get("selector")
            expression = items.get("expression")
            if (
                (not isinstance(selector, str) or not selector.strip())
                and isinstance(expression, str)
                and expression.strip()
            ):
                items["selector"] = expression.strip()
            items.pop("expression", None)
    return definition


class Migration(FeatureMigration):
    name: str = "task_definitions"

    def __init__(self, repo: TaskDefinitionsRepository, config: Config | None = None) -> None:
        self._config: Config = config or Config.get_instance()
        super().__init__(config=self._config)
        self._repo: TaskDefinitionsRepository = repo
        self._source_dir: Path = Path(self._config.config_path) / "tasks"

    async def should_run(self) -> bool:
        if not self._source_dir.exists():
            return False

        return any(self._source_dir.glob("*.json"))

    async def migrate(self) -> None:
        if await self._repo.count() > 0:
            LOG.warning("Task definitions already exist in the database; skipping migration.")
            await self._archive_sources()
            return

        inserted = 0
        seen_names: dict[str, int] = {}

        for path in sorted(self._source_dir.glob("*.json")):
            normalized = await self._normalize(path, seen_names)
            if not normalized:
                await self._move_file(path)
                continue

            try:
                await self._repo.create(normalized)
                inserted += 1
            except Exception as exc:
                LOG.exception(
                    "Failed to insert task definition '%s'.",
                    normalized.get("name"),
                    extra={"definition": normalized.get("name"), "exception_type": type(exc).__name__},
                )
            finally:
                await self._move_file(path)

        LOG.info("Migrated %s task definition(s) from %s.", inserted, self._source_dir)

    async def _archive_sources(self) -> None:
        for path in self._source_dir.glob("*.json"):
            await self._move_file(path)

    async def _normalize(self, path: Path, seen_names: dict[str, int]) -> dict[str, Any] | None:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            LOG.exception(
                "Failed to read task definition '%s'.",
                path,
                extra={"path": str(path), "exception_type": type(exc).__name__},
            )
            return None

        try:
            payload = json.loads(content)
        except Exception as exc:
            LOG.exception(
                "Failed to parse JSON for task definition '%s'.",
                path,
                extra={"path": str(path), "exception_type": type(exc).__name__},
            )
            return None

        if not isinstance(payload, dict):
            LOG.error("Task definition in '%s' must be a JSON object.", path)
            return None

        if "match" in payload and "match_url" not in payload:
            payload["match_url"] = payload.pop("match")

        # Normalize match_url from old object format to new string format
        if "match_url" in payload and isinstance(payload["match_url"], list):
            normalized_match: list[str] = []
            for item in payload["match_url"]:
                if isinstance(item, str):
                    normalized_match.append(item)
                elif isinstance(item, dict):
                    if "regex" in item and isinstance(item["regex"], str):
                        # Convert {regex: "pattern"} to /pattern/
                        normalized_match.append(f"/{item['regex']}/")
                    elif "glob" in item and isinstance(item["glob"], str):
                        # Convert {glob: "pattern"} to pattern
                        normalized_match.append(item["glob"])
            payload["match_url"] = normalized_match

        if "definition" not in payload:
            definition_fields = {}
            for field in ["parse", "engine", "request", "response"]:
                if field in payload:
                    definition_fields[field] = payload.pop(field)

            if definition_fields:
                payload["definition"] = definition_fields
        if isinstance(payload.get("definition"), dict):
            normalize_definition(payload["definition"])

        name_value = payload.get("name")
        if not isinstance(name_value, str) or not name_value.strip():
            LOG.error("Task definition in '%s' missing a valid name.", path)
            return None

        name = self._unique_name(name_value.strip(), seen_names)
        payload["name"] = name

        # Repository will handle validation and field extraction
        return payload
