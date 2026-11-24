from __future__ import annotations

from app.features.presets.models import PresetModel
from app.features.presets.repository import PresetsRepository
from app.features.presets.schemas import Preset
from app.features.presets.utils import preset_name
from app.library.Services import Services
from app.library.Singleton import Singleton


class Presets(metaclass=Singleton):
    def __init__(self, repo: PresetsRepository | None = None) -> None:
        self._repo: PresetsRepository = repo or PresetsRepository.get_instance()
        self._by_name: dict[str, Preset] = {}
        self._by_id: dict[int, Preset] = {}
        Services.get_instance().add(type(self).__name__, self)

    @staticmethod
    def get_instance() -> Presets:
        return Presets()

    async def refresh_cache(self, items: list[PresetModel]) -> None:
        presets = [Preset.model_validate(item) for item in items]
        self._by_name = {preset.name: preset for preset in presets}
        self._by_id = {preset.id: preset for preset in presets if preset.id is not None}

    def get_all(self) -> list[Preset]:
        return list(self._by_name.values())

    def get(self, identifier: int | str) -> Preset | None:
        if not identifier:
            return None

        if isinstance(identifier, str):
            return self._by_name.get(identifier) or self._by_name.get(preset_name(identifier))
        return self._by_id.get(identifier)

    def has(self, identifier: int | str) -> bool:
        return self.get(identifier) is not None
