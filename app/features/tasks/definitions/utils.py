import hashlib
from typing import Any, Literal, overload

from app.features.tasks.definitions.models import TaskDefinitionModel
from app.features.tasks.definitions.schemas import Definition, TaskDefinition, TaskDefinitionSummary

ARCHIVE_ID_TTL = 7 * 24 * 60 * 60
ARCHIVE_LOOKUP_FAILURE_TTL = 10 * 60


def archive_id_cache_key(url: str) -> str:
    """Return shared cache key for an exact item URL."""
    return f"tasks:archive-id:{hashlib.sha256(url.encode('utf-8')).hexdigest()}"


@overload
def model_to_schema(model: TaskDefinitionModel, summary: Literal[False] = False) -> TaskDefinition: ...


@overload
def model_to_schema(model: TaskDefinitionModel, summary: Literal[True]) -> TaskDefinitionSummary: ...


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
    if summary:
        return TaskDefinitionSummary(**dct)
    return TaskDefinition(**dct, definition=Definition.model_validate(model.definition))


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


def split_inspect_metadata(metadata: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Split commonly consumed metadata keys from the rest.

    Args:
        metadata (dict[str, Any]|None): The metadata to split.

    Returns:
        tuple[dict[str, Any], dict[str, Any]]: The primary and extra metadata.

    """
    metadata = dict(metadata or {})
    primary: dict[str, Any] = {}

    for key in ("matched", "handler", "supported"):
        if key in metadata:
            primary[key] = metadata.pop(key)

    return primary, metadata
