from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.features.core.migration import Migration as FeatureMigration
from app.features.presets.schemas import Preset
from app.features.presets.utils import preset_name
from app.library.config import Config

if TYPE_CHECKING:
    from app.features.presets.repository import PresetsRepository

LOG: logging.Logger = logging.getLogger(__name__)


class Migration(FeatureMigration):
    name: str = "presets"

    def __init__(self, repo: PresetsRepository, config: Config | None = None) -> None:
        self._config: Config = config or Config.get_instance()
        super().__init__(config=self._config)
        self._repo: PresetsRepository = repo
        self._source_file: Path = Path(self._config.config_path) / "presets.json"

    async def should_run(self) -> bool:
        return self._source_file.exists()

    async def migrate(self) -> None:
        try:
            items: list[dict[str, Any]] | None = json.loads(self._source_file.read_text())
        except Exception as exc:
            LOG.exception("Failed to read %s: %s. Ignoring", self._source_file, exc)
            await self._move_file(self._source_file)
            return

        if not items:
            LOG.warning("No presets found in %s; skipping migration.", self._source_file)
            await self._move_file(self._source_file)
            return

        inserted = 0
        seen_names: dict[str, int] = {preset_name(preset.name): 1 for preset in await self._repo.list()}

        for index, item in enumerate(items):
            if not (normalized := self._normalize(item, index, seen_names)):
                continue
            try:
                await self._repo.create(normalized)
                inserted += 1
            except Exception as exc:
                LOG.exception("Failed to insert preset '%s': %s", normalized["name"], exc)

        LOG.info("Migrated %s preset(s) from %s.", inserted, self._source_file)
        await self._move_file(self._source_file)

    def _normalize(self, item: Any, index: int, seen_names: dict[str, int]) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            LOG.warning("Skipping preset at index %s due to invalid type.", index)
            return None

        name: str | None = item.get("name")
        if not name or not isinstance(name, str):
            LOG.warning("Skipping preset at index %s due to missing name.", index)
            return None

        if not (name := preset_name(name)):
            LOG.warning("Skipping preset at index %s due to empty name.", index)
            return None

        name = self._unique_name(name, seen_names)

        description: str = item.get("description") if isinstance(item.get("description"), str) else ""
        folder: str = item.get("folder") if isinstance(item.get("folder"), str) else ""
        template: str = item.get("template") if isinstance(item.get("template"), str) else ""
        cookies: str = item.get("cookies") if isinstance(item.get("cookies"), str) else ""
        cli: str = item.get("cli") if isinstance(item.get("cli"), str) else ""
        priority = 0
        if isinstance(item.get("priority"), int) and not isinstance(item.get("priority"), bool):
            priority = int(item.get("priority"))

        if not cli and isinstance(item.get("format"), str):
            cli = f"--format {item.get('format')}"

        if cli:
            try:
                from app.features.ytdlp.utils import arg_converter

                arg_converter(args=cli, level=True)
            except Exception as exc:
                LOG.warning("Skipping preset '%s' due to invalid CLI: %s", name, exc)
                return None

        payload = {
            "name": name,
            "description": description,
            "folder": folder,
            "template": template,
            "cookies": cookies,
            "cli": cli,
            "default": False,
            "priority": priority,
        }

        try:
            Preset.model_validate(payload)
        except Exception as exc:
            LOG.warning("Skipping preset '%s' due to validation error: %s", name, exc)
            return None

        return payload
