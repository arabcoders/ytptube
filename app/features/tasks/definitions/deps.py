from app.features.tasks.definitions.repository import TaskDefinitionsRepository


def get_task_definitions_repo() -> TaskDefinitionsRepository:
    return TaskDefinitionsRepository.get_instance()
