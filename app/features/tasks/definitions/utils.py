from typing import Any

from app.features.tasks.definitions.models import TaskDefinitionModel
from app.features.tasks.definitions.schemas import Definition, TaskDefinition, TaskDefinitionSummary


def model_to_schema(model: TaskDefinitionModel, summary: bool = False) -> TaskDefinition | TaskDefinitionSummary:
    """
    Convert a TaskDefinitionModel to a TaskDefinition or TaskDefinitionSummary schema.

    Args:
        model (TaskDefinitionModel): The model instance to convert.
        summary (bool): Whether to return a summary schema.

    Returns:
        TaskDefinition | TaskDefinitionSummary: The corresponding schema instance.

    """
    dct = {
        "id": model.id,
        "name": model.name,
        "priority": model.priority,
        "match_url": model.match_url,
        "enabled": model.enabled,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }
    return TaskDefinitionSummary(**dct) if summary else TaskDefinition(**dct, definition=Definition(**model.definition))


def schema_to_payload(item: TaskDefinition) -> dict[str, Any]:
    """
    Convert a TaskDefinition schema to a dictionary payload for database operations.

    Args:
        item (TaskDefinition): The schema instance to convert.

    Returns:
        dict[str, Any]: The corresponding dictionary payload.

    """
    return {
        "name": item.name,
        "priority": item.priority,
        "match_url": item.match_url,
        "enabled": item.enabled,
        "definition": item.definition.model_dump(exclude_unset=True, exclude_none=True),
    }
