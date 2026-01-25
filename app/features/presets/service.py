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
        self._cache: list[tuple[int, str, Preset]] = []
        Services.get_instance().add(__class__.__name__, self)

    @staticmethod
    def get_instance() -> Presets:
        return Presets()

    async def refresh_cache(self, items: list[PresetModel]) -> None:
        presets = [Preset.model_validate(item) for item in items]
        self._cache = [(preset.id if preset.id is not None else -1, preset.name, preset) for preset in presets]

    def get_all(self) -> list[Preset]:
        return [preset for _, _, preset in self._cache]

    def get(self, identifier: int | str) -> Preset | None:
        if not identifier:
            return None

        if isinstance(identifier, str) and not (identifier := preset_name(identifier)):
            return None

        for id, name, preset in self._cache:
            if isinstance(identifier, int) and id == identifier:
                return preset
            if isinstance(identifier, str) and name == identifier:
                return preset

        return None

    def has(self, identifier: int | str) -> bool:
        return self.get(identifier) is not None
