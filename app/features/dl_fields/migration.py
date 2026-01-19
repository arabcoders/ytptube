from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.features.core.migration import Migration as FeatureMigration
from app.features.dl_fields.schemas import DLField
from app.library.config import Config

if TYPE_CHECKING:
    from app.features.dl_fields.repository import DLFieldsRepository

LOG: logging.Logger = logging.getLogger(__name__)


class Migration(FeatureMigration):
    name: str = "dl_fields"

    def __init__(self, repo: DLFieldsRepository, config: Config | None = None):
        self._config: Config = config or Config.get_instance()
        super().__init__(config=self._config)
        self._repo: DLFieldsRepository = repo
        self._source_file: Path = Path(self._config.config_path) / "dl_fields.json"

    async def should_run(self) -> bool:
        return self._source_file.exists()

    async def migrate(self) -> None:
        if await self._repo.count() > 0:
            LOG.warning("DL fields already exist in the database; skipping migration.")
            await self._move_file(self._source_file)
            return

        try:
            items: list[dict[str, Any]] | None = json.loads(self._source_file.read_text())
        except Exception as exc:
            LOG.exception("Failed to read %s: %s. Ignoring", self._source_file, exc)
            await self._move_file(self._source_file)
            return

        if items is None:
            LOG.warning("No dl fields found in %s; skipping migration.", self._source_file)
            await self._move_file(self._source_file)
            return

        inserted = 0
        for index, item in enumerate(items):
            if not (normalized := self._normalize(item, index)):
                continue
            try:
                await self._repo.create(normalized)
                inserted += 1
            except Exception as exc:
                LOG.exception("Failed to insert dl field '%s': %s", normalized["name"], exc)

        LOG.info("Migrated %s dl field(s) from %s.", inserted, self._source_file)
        await self._move_file(self._source_file)

    def _normalize(self, item: Any, index: int) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            LOG.warning("Skipping dl field at index %s due to invalid type.", index)
            return None

        name: str | None = item.get("name")
        if not name or not isinstance(name, str):
            LOG.warning("Skipping dl field at index %s due to missing name.", index)
            return None

        description: str = item.get("description") if isinstance(item.get("description"), str) else ""
        field_value: str | None = item.get("field")
        if not field_value or not isinstance(field_value, str):
            LOG.warning("Skipping dl field '%s' due to missing field value.", name)
            return None

        kind: str = item.get("kind") if isinstance(item.get("kind"), str) else "text"
        icon: str = item.get("icon") if isinstance(item.get("icon"), str) else ""
        value: str = item.get("value") if isinstance(item.get("value"), str) else ""
        extras: dict[str, Any] = item.get("extras") if isinstance(item.get("extras"), dict) else {}

        order_value: int = 0
        if isinstance(item.get("order"), int) and not isinstance(item.get("order"), bool):
            order_value = item.get("order", 0)

        payload = {
            "name": name,
            "description": description,
            "field": field_value,
            "kind": kind,
            "icon": icon,
            "order": order_value,
            "value": value,
            "extras": extras,
        }

        try:
            DLField.model_validate(payload)
        except Exception as exc:
            LOG.warning("Skipping dl field '%s' due to validation error: %s", name, exc)
            return None

        return payload
