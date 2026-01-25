from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.features.core.migration import Migration as FeatureMigration
from app.library.config import Config

if TYPE_CHECKING:
    from app.features.tasks.definitions.repository import TaskDefinitionsRepository

LOG: logging.Logger = logging.getLogger(__name__)


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
                LOG.exception("Failed to insert task definition '%s': %s", normalized.get("name"), exc)
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
            LOG.error("Failed to read task definition '%s': %s", path, exc)
            return None

        try:
            payload = json.loads(content)
        except Exception as exc:
            LOG.error("Failed to parse JSON for '%s': %s", path, exc)
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

        # Rename request.json to request.json_data
        if "request" in payload and isinstance(payload["request"], dict) and "json" in payload["request"]:
            payload["request"]["json_data"] = payload["request"].pop("json")

        if "definition" not in payload:
            definition_fields = {}
            for field in ["parse", "engine", "request", "response"]:
                if field in payload:
                    definition_fields[field] = payload.pop(field)

            if definition_fields:
                payload["definition"] = definition_fields
        # Also handle nested definition.request.json
        elif isinstance(payload["definition"], dict):
            if (
                "request" in payload["definition"]
                and isinstance(payload["definition"]["request"], dict)
                and "json" in payload["definition"]["request"]
            ):
                payload["definition"]["request"]["json_data"] = payload["definition"]["request"].pop("json")

        name_value = payload.get("name")
        if not isinstance(name_value, str) or not name_value.strip():
            LOG.error("Task definition in '%s' missing a valid name.", path)
            return None

        name = self._unique_name(name_value.strip(), seen_names)
        payload["name"] = name

        # Repository will handle validation and field extraction
        return payload
