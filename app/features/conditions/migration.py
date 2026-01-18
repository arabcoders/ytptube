from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.features.conditions.models import ConditionModel
from app.features.core.migration import Migration as FeatureMigration
from app.library.config import Config

if TYPE_CHECKING:
    from app.features.conditions.repository import ConditionsRepository

LOG: logging.Logger = logging.getLogger(__name__)


class Migration(FeatureMigration):
    name: str = "conditions"

    def __init__(self, repo: ConditionsRepository, config: Config | None = None):
        self._config: Config = config or Config.get_instance()
        super().__init__(config=self._config)
        self._repo: ConditionsRepository = repo
        self._source_file: Path = Path(self._config.config_path) / "conditions.json"

    async def should_run(self) -> bool:
        return self._source_file.exists()

    async def migrate(self) -> None:
        if await self._repo.count() > 0:
            LOG.warning("Conditions already exist in the database; skipping migration.")
            await self._move_file(self._source_file)
            return

        try:
            items: list[dict] | None = json.loads(self._source_file.read_text())
        except Exception as exc:
            LOG.exception("Failed to read %s: %s. Ignoring", self._source_file, exc)
            await self._move_file(self._source_file)
            return

        if items is None:
            LOG.warning("No conditions found in %s; skipping migration.", self._source_file)
            await self._move_file(self._source_file)
            return

        inserted = 0
        for index, item in enumerate(items):
            if not (normalized := await self._normalize(item, index)):
                continue
            try:
                await self._repo.create(normalized)
                inserted += 1
            except Exception as exc:
                LOG.exception("Failed to insert condition '%s': %s", normalized.name, exc)

        LOG.info("Migrated %s condition(s) from %s.", inserted, self._source_file)
        await self._move_file(self._source_file)

    async def _normalize(self, item: Any, index: int) -> ConditionModel | None:
        if not isinstance(item, dict):
            LOG.warning("Skipping condition at index %s due to invalid type.", index)
            return None

        name: str | None = item.get("name")
        if not name or not isinstance(name, str):
            LOG.warning("Skipping condition at index %s due to missing name.", index)
            return None

        extras: dict[str, Any] = item.get("extras") if isinstance(item.get("extras"), dict) else {}
        filter_value: str | None = item.get("filter")
        if (not filter_value or not isinstance(filter_value, str)) and len(extras) == 0:
            LOG.warning("Skipping condition '%s' due to missing filter.", name)
            return None

        cli: str | None = item.get("cli")
        if not isinstance(cli, str):
            cli = ""

        enabled: bool = item.get("enabled") if isinstance(item.get("enabled"), bool) else True
        priority: int = item.get("priority") if isinstance(item.get("priority"), int) else 0
        if isinstance(priority, bool) or 0 > priority:
            priority = 0

        description: str = item.get("description") if isinstance(item.get("description"), str) else ""

        return ConditionModel(
            id=index,
            name=name,
            filter=filter_value,
            cli=cli,
            extras=extras,
            enabled=bool(enabled),
            priority=priority,
            description=description,
        )
