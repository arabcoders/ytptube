from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.features.core.migration import Migration as FeatureMigration
from app.features.notifications.schemas import NotificationEvents
from app.library.config import Config
from app.library.Presets import Presets

if TYPE_CHECKING:
    from app.features.notifications.repository import NotificationsRepository

LOG: logging.Logger = logging.getLogger(__name__)


class Migration(FeatureMigration):
    name: str = "notifications"

    def __init__(self, repo: NotificationsRepository, config: Config | None = None):
        self._config: Config = config or Config.get_instance()
        super().__init__(config=self._config)
        self._repo: NotificationsRepository = repo
        self._source_file: Path = Path(self._config.config_path) / "notifications.json"

    async def should_run(self) -> bool:
        return self._source_file.exists()

    async def migrate(self) -> None:
        if await self._repo.count() > 0:
            LOG.warning("Notification targets already exist in the database; skipping migration.")
            await self._move_file(self._source_file)
            return

        try:
            items: list[dict] | None = json.loads(self._source_file.read_text())
        except Exception as exc:
            LOG.exception("Failed to read %s: %s. Ignoring", self._source_file, exc)
            await self._move_file(self._source_file)
            return

        if items is None:
            LOG.warning("No notification targets found in %s; skipping migration.", self._source_file)
            await self._move_file(self._source_file)
            return

        inserted = 0
        for index, item in enumerate(items):
            normalized = self._normalize(item, index)
            if not normalized:
                continue
            try:
                await self._repo.create(normalized)
                inserted += 1
            except Exception as exc:
                LOG.exception("Failed to insert notification '%s': %s", normalized.get("name"), exc)

        LOG.info("Migrated %s notification target(s) from %s.", inserted, self._source_file)
        await self._move_file(self._source_file)

    def _normalize(self, item: Any, index: int) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            LOG.warning("Skipping notification at index %s due to invalid type.", index)
            return None

        name: str | None = item.get("name")
        if not name or not isinstance(name, str):
            LOG.warning("Skipping notification at index %s due to missing name.", index)
            return None

        request = item.get("request") if isinstance(item.get("request"), dict) else {}
        url: str | None = request.get("url")
        if not url or not isinstance(url, str):
            LOG.warning("Skipping notification '%s' due to missing request url.", name)
            return None

        method = request.get("method") if isinstance(request.get("method"), str) else "POST"
        method = method.upper()
        if method not in {"POST", "PUT"}:
            LOG.warning("Skipping notification '%s' due to invalid method '%s'.", name, method)
            return None

        req_type = request.get("type") if isinstance(request.get("type"), str) else "json"
        req_type = req_type.lower()
        if req_type not in {"json", "form"}:
            LOG.warning("Skipping notification '%s' due to invalid type '%s'.", name, req_type)
            return None

        data_key = request.get("data_key") if isinstance(request.get("data_key"), str) else "data"
        if not data_key:
            data_key = "data"

        headers = self._normalize_headers(request.get("headers"))

        enabled: bool = item.get("enabled") if isinstance(item.get("enabled"), bool) else True
        events = self._normalize_events(item.get("on"))
        if events is None:
            LOG.warning("Skipping notification '%s' due to invalid events.", name)
            return None

        presets = self._normalize_presets(item.get("presets"))
        if presets is None:
            LOG.warning("Skipping notification '%s' due to invalid presets.", name)
            return None

        return {
            "name": name,
            "on": events,
            "presets": presets,
            "enabled": enabled,
            "request_url": url,
            "request_method": method,
            "request_type": req_type,
            "request_data_key": data_key,
            "request_headers": headers,
        }

    def _normalize_events(self, events: Any) -> list[str] | None:
        if events is None:
            return []
        if not isinstance(events, list):
            return []

        allowed = set(NotificationEvents.get_events().values())
        valid = [event for event in events if event in allowed]
        invalid = [event for event in events if event not in allowed]

        if len(invalid) > 0 and len(valid) < 1:
            return None

        if len(invalid) > 0:
            LOG.warning("Dropping invalid notification events: %s", ", ".join(invalid))

        return valid

    def _normalize_presets(self, presets: Any) -> list[str] | None:
        if presets is None:
            return []
        if not isinstance(presets, list):
            return []

        allowed = {preset.name for preset in Presets.get_instance().get_all()}
        valid = [preset for preset in presets if preset in allowed]
        invalid = [preset for preset in presets if preset not in allowed]

        if len(invalid) > 0 and len(valid) < 1:
            return None

        if len(invalid) > 0:
            LOG.warning("Dropping invalid notification presets: %s", ", ".join(invalid))

        return valid

    def _normalize_headers(self, headers: Any) -> list[dict[str, str]]:
        if not isinstance(headers, list):
            return []

        normalized: list[dict[str, str]] = []
        for header in headers:
            if not isinstance(header, dict):
                continue
            key = str(header.get("key", "")).strip()
            value = str(header.get("value", "")).strip()
            if key and value:
                normalized.append({"key": key, "value": value})
        return normalized
