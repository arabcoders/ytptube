from app.features.conditions.repository import ConditionsRepository


def get_conditions_repo() -> ConditionsRepository:
    return ConditionsRepository.get_instance()
