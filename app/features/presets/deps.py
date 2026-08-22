from app.features.presets.repository import PresetsRepository


def get_presets_repo() -> PresetsRepository:
    return PresetsRepository.get_instance()
