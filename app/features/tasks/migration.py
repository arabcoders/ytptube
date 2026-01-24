from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.features.core.migration import Migration as FeatureMigration
from app.features.tasks.schemas import Task
from app.library.config import Config

if TYPE_CHECKING:
    from app.features.tasks.repository import TasksRepository

LOG: logging.Logger = logging.getLogger(__name__)


class Migration(FeatureMigration):
    name: str = "tasks"

    def __init__(self, repo: TasksRepository, config: Config | None = None):
        self._config: Config = config or Config.get_instance()
        super().__init__(config=self._config)
        self._repo: TasksRepository = repo
        self._source_file: Path = Path(self._config.config_path) / "tasks.json"

    async def should_run(self) -> bool:
        return self._source_file.exists()

    async def migrate(self) -> None:
        if await self._repo.count() > 0:
            LOG.warning("Tasks already exist in the database; skipping migration.")
            await self._move_file(self._source_file)
            return

        try:
            items: list[dict[str, Any]] | None = json.loads(self._source_file.read_text())
        except Exception as exc:
            LOG.exception("Failed to read %s: %s. Ignoring", self._source_file, exc)
            await self._move_file(self._source_file)
            return

        if items is None:
            LOG.warning("No tasks found in %s; skipping migration.", self._source_file)
            await self._move_file(self._source_file)
            return

        inserted = 0
        seen_names: dict[str, int] = {}
        for index, item in enumerate(items):
            if not (normalized := self._normalize(item, index, seen_names)):
                continue
            try:
                await self._repo.create(normalized)
                inserted += 1
            except Exception as exc:
                LOG.exception("Failed to insert task '%s': %s", normalized["name"], exc)

        LOG.info("Migrated %s task(s) from %s.", inserted, self._source_file)
        await self._move_file(self._source_file)

    def _normalize(self, item: Any, index: int, seen_names: dict[str, int]) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            LOG.warning("Skipping task at index %s due to invalid type.", index)
            return None

        assert isinstance(item, dict)

        name: str | None = item.get("name")
        if not name or not isinstance(name, str):
            LOG.warning("Skipping task at index %s due to missing name.", index)
            return None

        normalized_name = name.strip()
        if not normalized_name:
            LOG.warning("Skipping task at index %s due to empty name.", index)
            return None

        name = self._unique_name(normalized_name, seen_names)

        url: str | None = item.get("url")
        if not url or not isinstance(url, str):
            LOG.warning("Skipping task '%s' at index %s due to missing URL.", name, index)
            return None

        url = url.strip()
        if not url:
            LOG.warning("Skipping task '%s' at index %s due to empty URL.", name, index)
            return None

        folder: str = item.get("folder") if isinstance(item.get("folder"), str) else ""
        preset: str = item.get("preset") if isinstance(item.get("preset"), str) else ""
        timer: str = item.get("timer") if isinstance(item.get("timer"), str) else ""
        template: str = item.get("template") if isinstance(item.get("template"), str) else ""
        cli: str = item.get("cli") if isinstance(item.get("cli"), str) else ""
        auto_start: bool = item.get("auto_start") if isinstance(item.get("auto_start"), bool) else True
        handler_enabled: bool = item.get("handler_enabled") if isinstance(item.get("handler_enabled"), bool) else True
        enabled: bool = item.get("enabled") if isinstance(item.get("enabled"), bool) else True

        try:
            validated = Task(
                name=name,
                url=url,
                folder=folder,
                preset=preset,
                timer=timer,
                template=template,
                cli=cli,
                auto_start=auto_start,
                handler_enabled=handler_enabled,
                enabled=enabled,
            )
            return validated.model_dump()
        except Exception as e:
            LOG.warning("Skipping task '%s' at index %s due to validation error: %s", name, index, e)
            return None
