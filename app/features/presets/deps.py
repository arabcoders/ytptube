from app.features.presets.repository import PresetsRepository
from app.features.presets.service import Presets


def get_presets_repo() -> PresetsRepository:
    return PresetsRepository.get_instance()


def get_presets_service() -> Presets:
    return Presets.get_instance()
