import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiohttp import web
from jsonschema import Draft7Validator, SchemaError, ValidationError

from .config import Config
from .encoder import Encoder
from .Services import Services
from .Singleton import Singleton

LOG: logging.Logger = logging.getLogger("task_definitions")


@dataclass(slots=True)
class TaskDefinitionRecord:
    identifier: str
    """UUID identifier of the task definition."""
    filename: str
    """Filename of the task definition JSON file."""
    name: str
    """Human-readable name of the task definition."""
    priority: int
    """Priority of the task definition."""
    path: Path
    """Path to the task definition JSON file."""
    data: dict[str, Any]
    """The task definition data."""
    updated_at: float
    """Last modified timestamp of the task definition file."""

    def serialize(self, *, include_definition: bool = False) -> dict[str, Any]:
        """
        Serialize the task definition record to a dictionary.

        Args:
            include_definition (bool): Whether to include the full task definition data.

        Returns:
            dict[str, Any]: The serialized task definition record.

        """
        payload: dict[str, Any] = {
            "id": self.identifier,
            "name": self.name,
            "priority": self.priority,
            "updated_at": self.updated_at,
        }

        if include_definition:
            payload["definition"] = self.data

        return payload

    def json(self, *, include_definition: bool = False) -> str:
        """
        Serialize the task definition record to a JSON string.

        Args:
            include_definition (bool): Whether to include the full task definition data.

        Returns:
            str: The JSON string representation of the task definition record.

        """
        return Encoder().encode(self.serialize(include_definition=include_definition))


class TaskDefinitions(metaclass=Singleton):
    def __init__(
        self,
        directory: str | Path | None = None,
        config: Config | None = None,
        validator: Draft7Validator | None = None,
    ):
        self._config: Config = config or Config.get_instance()
        "Instance of Config to use."
        self._directory: Path = Path(directory) if directory else Path(self._config.config_path) / "tasks"
        "Directory where task definition files are stored."
        self._validator: Draft7Validator | None = validator
        "JSON schema validator instance."
        self._items: dict[str, TaskDefinitionRecord] = {}
        "Mapping of task definition ID to TaskDefinitionRecord."
        self._schema: Path = Path(self._config.app_path) / "schema" / "task_definition.json"
        "Path to the JSON schema file for task definitions."

        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            LOG.error(f"Failed to create tasks directory '{self._directory}': {e}")

        self.load()

    @staticmethod
    def get_instance(
        directory: str | Path | None = None,
        config: Config | None = None,
        validator: Draft7Validator | None = None,
    ) -> "TaskDefinitions":
        """
        Get the singleton instance of TaskDefinitions.

        Args:
            directory (str | Path | None): Optional directory to store task definitions.
            config (Config | None): Optional Config instance to use.
            validator (Draft7Validator | None): Optional JSON schema validator to use.

        Returns:
            TaskDefinitions: The singleton instance of TaskDefinitions.

        """
        return TaskDefinitions(directory=directory, config=config, validator=validator)

    def attach(self, _: web.Application) -> None:
        """
        Attach the TaskDefinitions service to the application.

        Args:
            _ (web.Application): The aiohttp web application instance.

        """
        Services.get_instance().add("task_definitions", self)

    async def on_shutdown(self, _: web.Application) -> None:
        """
        Handle application shutdown event.

        Args:
            _ (web.Application): The aiohttp web application instance.

        """
        return

    def _get_validator(self) -> Draft7Validator:
        """
        Get or create the JSON schema validator for task definitions.

        Returns:
            Draft7Validator: The JSON schema validator instance.

        """
        if self._validator:
            return self._validator

        try:
            contents: str = self._schema.read_text(encoding="utf-8")
            schema = json.loads(contents)
        except Exception as e:
            LOG.error(f"Failed to read task definition schema '{self._schema}': {e}")
            raise

        try:
            self._validator = Draft7Validator(schema)
        except SchemaError as e:
            LOG.error(f"Invalid task definition schema '{self._schema}': {e}")
            raise

        return self._validator

    def validate(self, definition: dict[str, Any]) -> None:
        """
        Validate a task definition against the JSON schema.

        Args:
            definition (dict[str, Any]): The task definition to validate.

        Raises:
            ValueError: If the task definition is invalid.

        """
        try:
            self._get_validator().validate(definition)
        except ValidationError as e:
            path: str = " ".join(str(part) for part in e.path)
            error_path: str = f" ({path})" if path else ""
            message: str = f"Task definition validation failed{error_path}: {e.message}"
            raise ValueError(message) from e

    def load(self) -> "TaskDefinitions":
        """
        Load all task definitions from the directory.

        Returns:
            TaskDefinitions: The current instance for chaining.

        """
        self._items.clear()

        if not self._directory.exists():
            return self

        for file_path in sorted(self._directory.glob("*.json")):
            stem: str = file_path.stem

            try:
                identifier_uuid = uuid.UUID(stem)
            except ValueError:
                LOG.warning(f"Skipping task definition with invalid UUID filename '{file_path.name}'.")
                continue

            if 4 != identifier_uuid.version:
                LOG.warning(f"Skipping task definition '{file_path.name}', Name is not UUIDv4.")
                continue

            try:
                contents: str = file_path.read_text(encoding="utf-8")
            except Exception as e:
                LOG.error(f"Failed to load task definition '{file_path}': {e!s}")
                continue

            try:
                parsed = json.loads(contents)
            except Exception as e:
                LOG.error(f"Failed to parse task definition '{file_path}': {e!s}")
                continue

            if not isinstance(parsed, dict):
                LOG.error(f"Invalid task definition file '{file_path}': must be a JSON object.")
                continue

            data: dict[str, Any] = parsed

            identifier: str = str(identifier_uuid)

            name_value: str = str(data.get("name") or identifier)
            priority: int = self._normalize_priority(data.get("priority", 0))
            data["priority"] = priority

            record = TaskDefinitionRecord(
                identifier=identifier,
                filename=file_path.name,
                name=name_value,
                priority=priority,
                path=file_path,
                data=data,
                updated_at=file_path.stat().st_mtime,
            )
            self._items[record.identifier] = record

        return self

    def list(self) -> list[TaskDefinitionRecord]:
        """
        List all task definitions, sorted by priority and name.

        Returns:
            list[TaskDefinitionRecord]: List of task definitions sorted by priority and name.

        """
        return sorted(
            self._items.values(),
            key=lambda record: (record.priority, record.name.lower()),
        )

    def get(self, identifier: str) -> TaskDefinitionRecord | None:
        """
        Get a task definition by its identifier.

        Args:
            identifier (str): The UUID identifier of the task definition.

        Returns:
            TaskDefinitionRecord | None: The task definition record, or None if not found.

        """
        return self._items.get(identifier)

    def _path_for(self, identifier: str) -> Path:
        """
        Get the file path for a given task definition identifier.

        Args:
            identifier (str): The UUID identifier of the task definition.

        Returns:
            Path: The file path for the task definition JSON file.

        """
        return self._directory / f"{identifier}.json"

    def _write_file(self, path: Path, payload: dict[str, Any]) -> None:
        """
        Write a task definition to a file.

        Args:
            path (Path): The file path to write to.
            payload (dict[str, Any]): The task definition data to write.

        Raises:
            Exception: If writing to the file fails.

        """
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        try:
            path.chmod(0o600)
        except Exception:
            pass

    def _normalize_priority(self, value: Any) -> int:
        """
        Normalize the priority value to an integer.

        Args:
            value (Any): The priority value to normalize.

        Returns:
            int: The normalized priority value.

        """
        try:
            priority = int(value)
        except Exception:
            priority = 0

        return priority

    def _refresh_generic_handler(self) -> None:
        """
        Refresh the generic task handler definitions.
        """
        try:
            from .task_handlers.generic import GenericTaskHandler

            GenericTaskHandler.refresh_definitions(force=True)
        except Exception as e:
            LOG.error(f"Failed to refresh generic task handler: {e}")

    def create(self, definition: dict[str, Any]) -> TaskDefinitionRecord:
        """
        Create a new task definition.

        Args:
            definition (dict[str, Any]): The task definition data.

        Returns:
            TaskDefinitionRecord: The created task definition record.

        """
        self.validate(definition)

        identifier: str = str(uuid.uuid4())
        path: Path = self._path_for(identifier)

        while path.exists():
            identifier = str(uuid.uuid4())
            path = self._path_for(identifier)

        priority: int = self._normalize_priority(definition.get("priority", 0))
        definition["priority"] = priority

        self._write_file(path, definition)

        record = TaskDefinitionRecord(
            identifier=identifier,
            filename=path.name,
            name=str(definition.get("name", identifier)),
            priority=priority,
            path=path,
            data=definition,
            updated_at=path.stat().st_mtime,
        )

        self._items[identifier] = record
        self._refresh_generic_handler()
        return record

    def update(self, identifier: str, definition: dict[str, Any]) -> TaskDefinitionRecord:
        """
        Update an existing task definition.

        Args:
            identifier (str): The UUID identifier of the task definition to update.
            definition (dict[str, Any]): The updated task definition data.

        Returns:
            TaskDefinitionRecord: The updated task definition record.

        Raises:
            ValueError: If the task definition does not exist or is invalid.

        """
        record: TaskDefinitionRecord | None = self.get(identifier)
        if not record:
            message: str = f"Task definition '{identifier}' does not exist."
            raise ValueError(message)

        self.validate(definition)
        priority: int = self._normalize_priority(definition.get("priority", record.priority))
        definition["priority"] = priority
        self._write_file(record.path, definition)

        updated_record = TaskDefinitionRecord(
            identifier=identifier,
            filename=record.filename,
            name=str(definition.get("name", identifier)),
            priority=priority,
            path=record.path,
            data=definition,
            updated_at=record.path.stat().st_mtime,
        )

        self._items[identifier] = updated_record
        self._refresh_generic_handler()
        return updated_record

    def delete(self, identifier: str) -> None:
        """
        Delete a task definition.

        Args:
            identifier (str): The UUID identifier of the task definition to delete.

        Raises:
            ValueError: If the task definition does not exist.

        """
        record: TaskDefinitionRecord | None = self.get(identifier)
        if not record:
            message: str = f"Task definition '{identifier}' does not exist."
            raise ValueError(message)

        try:
            record.path.unlink(missing_ok=False)
        except FileNotFoundError:
            LOG.warning(f"Task definition file '{record.path}' already removed.")
        except Exception as exc:
            LOG.error(f"Failed to delete task definition '{identifier}': {exc}")
            raise

        self._items.pop(identifier, None)
        self._refresh_generic_handler()
