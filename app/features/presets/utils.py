import logging
import re
from datetime import UTC, datetime

NAME_WHITESPACE_PATTERN = re.compile(r"\s+")

LOG: logging.Logger = logging.getLogger(__name__)


async def seed_defaults(repo) -> None:
    from .defaults import DEFAULT_PRESETS

    for preset in DEFAULT_PRESETS:
        try:
            name = preset.get("name")
            if not name or not isinstance(name, str):
                LOG.warning("Skipping default preset with invalid name: %s", preset)
                continue

            if not (name := preset_name(name)):
                LOG.warning("Skipping default preset with empty normalized name: %s", name)
                continue

            payload = {**preset}
            payload.pop("id", None)
            payload["default"] = True
            payload["name"] = name

            updated_at_value: datetime | None = None
            updated_at_raw = payload.get("updated_at")
            if isinstance(updated_at_raw, str):
                updated_at_value = datetime.fromisoformat(updated_at_raw)
            elif isinstance(updated_at_raw, datetime):
                updated_at_value = updated_at_raw
            if isinstance(updated_at_value, datetime) and updated_at_value.tzinfo is None:
                updated_at_value = updated_at_value.replace(tzinfo=UTC)
            payload["updated_at"] = updated_at_value

            existing = await repo.get_by_name(name)
            if None is existing:
                await repo.create(payload)
                continue

            if existing.updated_at and updated_at_value and existing.updated_at >= updated_at_value:
                if False is existing.default:
                    await repo.update(existing.id, {"default": True})
                continue

            await repo.update(existing.id, payload)
        except Exception as exc:
            LOG.exception("Failed to seed default preset '%s': %s", preset.get("name"), exc)


def preset_name(value: str) -> str:
    return NAME_WHITESPACE_PATTERN.sub("_", value.strip().lower())
