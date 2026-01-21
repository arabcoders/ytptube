from __future__ import annotations

import abc
import logging
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.library.config import Config

LOG: logging.Logger = logging.getLogger(__name__)


class Migration(abc.ABC):
    name: str = ""

    def __init__(self, config: Config):
        self._migrated_dir: Path = Path(config.config_path) / "migrated"

    async def run(self) -> bool:
        if not await self.should_run():
            return False

        self._migrated_dir.mkdir(parents=True, exist_ok=True)
        try:
            await self.migrate()
        except Exception as exc:
            LOG.exception("Feature migration '%s' failed: %s", self.name, exc)
            return False

        return True

    @abc.abstractmethod
    async def should_run(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def migrate(self) -> None:
        raise NotImplementedError

    async def _move_file(self, source: Path) -> Path:
        destination: Path = self._migrated_dir / source.name
        if destination.exists():
            timestamp = int(time.time())
            destination: Path = self._migrated_dir / f"{source.stem}_{timestamp}{source.suffix}"

        shutil.move(str(source), str(destination))
        return destination

    def _unique_name(self, name: str, seen_names: dict[str, int]) -> str:
        base = name
        count = seen_names.get(base, 0)
        if count == 0:
            seen_names[base] = 1
            return base

        suffix = count + 1
        new_name = f"{base} ({suffix})"
        while new_name in seen_names:
            suffix += 1
            new_name = f"{base} ({suffix})"

        seen_names[base] = suffix
        seen_names[new_name] = 1
        return new_name
