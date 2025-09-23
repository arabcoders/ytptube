import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiohttp import web
from aiohttp.web import Request
from jsonschema import Draft7Validator

from app.library.encoder import Encoder
from app.library.TaskDefinitions import TaskDefinitionRecord, TaskDefinitions
from app.routes.api import task_definitions as api


def _load_validator() -> Draft7Validator:
    schema_path = Path(__file__).resolve().parent.parent / "schema" / "task_definition.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft7Validator(schema)


def _sample_definition(name: str = "example", *, priority: int = 0) -> dict[str, Any]:
    return {
        "name": name,
        "match": ["https://example.com/*"],
        "priority": priority,
        "parse": {
            "items": {
                "type": "css",
                "selector": ".card",
                "fields": {
                    "link": {"type": "css", "expression": "a", "attribute": "href"},
                    "title": {"type": "css", "expression": "a", "attribute": "text"},
                },
            }
        },
    }


class TestTaskDefinitionsManager:
    def setup_method(self) -> None:
        TaskDefinitions._reset_singleton()

    def teardown_method(self) -> None:
        TaskDefinitions._reset_singleton()

    def test_load_populates_records(self, tmp_path: Path) -> None:
        validator = _load_validator()
        config = Mock(config_path=str(tmp_path), app_path=str(tmp_path))

        first_identifier = "b5c6ad5f-4745-4c05-88c8-dde1deae3b51"
        second_identifier = "ae38a6b0-2c22-4763-ba60-801ae8ce1218"

        first = tmp_path / f"{first_identifier}.json"
        second = tmp_path / f"{second_identifier}.json"

        first.write_text(json.dumps(_sample_definition("First", priority=5)), encoding="utf-8")
        second.write_text(json.dumps(_sample_definition("Second", priority=1)), encoding="utf-8")

        (tmp_path / "not-a-uuid.json").write_text(json.dumps(_sample_definition("Ignored")), encoding="utf-8")
        (tmp_path / "0f9184de-5d3c-2111-8c21-6d3f0be1bd3d.json").write_text(
            json.dumps(_sample_definition("Ignored2")),
            encoding="utf-8",
        )

        manager = TaskDefinitions.get_instance(directory=tmp_path, config=config, validator=validator)

        records = manager.list()
        assert len(records) == 2
        assert [record.name for record in records] == ["Second", "First"]
        assert [record.priority for record in records] == [1, 5]

    def test_create_writes_file_and_refreshes(self, tmp_path: Path) -> None:
        validator = _load_validator()
        config = Mock(config_path=str(tmp_path), app_path=str(tmp_path))
        manager = TaskDefinitions.get_instance(directory=tmp_path, config=config, validator=validator)

        with patch("app.library.task_handlers.generic.GenericTaskHandler.refresh_definitions") as refresh:
            definition = _sample_definition("My Definition")
            record = manager.create(definition)

        refresh.assert_called_once_with(force=True)
        identifier_uuid = uuid.UUID(record.identifier)
        assert 4 == identifier_uuid.version
        expected_filename = f"{record.identifier}.json"
        saved_path = tmp_path / expected_filename
        assert saved_path.exists()
        saved_content = json.loads(saved_path.read_text(encoding="utf-8"))
        assert saved_content["name"] == "My Definition"
        assert saved_content["priority"] == 0

    def test_update_missing_definition_raises(self, tmp_path: Path) -> None:
        validator = _load_validator()
        config = Mock(config_path=str(tmp_path), app_path=str(tmp_path))
        manager = TaskDefinitions.get_instance(directory=tmp_path, config=config, validator=validator)

        with pytest.raises(ValueError, match="does not exist"):
            manager.update("missing", _sample_definition("Updated"))

    def test_update_overwrites_file(self, tmp_path: Path) -> None:
        validator = _load_validator()
        config = Mock(config_path=str(tmp_path), app_path=str(tmp_path))

        identifier = "c59ec7cf-6291-4f0f-86f8-d8cb12c325a4"
        initial = _sample_definition("Original", priority=4)
        path = tmp_path / f"{identifier}.json"
        path.write_text(json.dumps(initial), encoding="utf-8")

        manager = TaskDefinitions.get_instance(directory=tmp_path, config=config, validator=validator)

        with patch("app.library.task_handlers.generic.GenericTaskHandler.refresh_definitions") as refresh:
            updated_record = manager.update(identifier, _sample_definition("Updated", priority=2))

        refresh.assert_called_once_with(force=True)
        assert updated_record.name == "Updated"
        assert updated_record.priority == 2
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["name"] == "Updated"
        assert saved["priority"] == 2

    def test_delete_removes_file(self, tmp_path: Path) -> None:
        validator = _load_validator()
        config = Mock(config_path=str(tmp_path), app_path=str(tmp_path))

        identifier = "f0b71f47-6b65-4b6d-89fd-6b87ce47d3bc"
        definition_path = tmp_path / f"{identifier}.json"
        definition_path.write_text(json.dumps(_sample_definition("Delete")), encoding="utf-8")

        manager = TaskDefinitions.get_instance(directory=tmp_path, config=config, validator=validator)

        with patch("app.library.task_handlers.generic.GenericTaskHandler.refresh_definitions") as refresh:
            manager.delete(identifier)

        refresh.assert_called_once_with(force=True)
        assert not definition_path.exists()
        assert manager.get(identifier) is None


@pytest.mark.asyncio
class TestTaskDefinitionRoutes:
    def setup_method(self) -> None:
        TaskDefinitions._reset_singleton()

    def teardown_method(self) -> None:
        TaskDefinitions._reset_singleton()

    async def test_list_definitions(self) -> None:
        request = MagicMock(spec=Request)
        request.query = {}

        identifier = "9af7018f-8659-4d2a-a42b-b5d2c5f0a6e2"
        record = TaskDefinitionRecord(
            identifier=identifier,
            filename=f"{identifier}.json",
            name="Sample",
            priority=0,
            path=Path("/tmp/sample.json"),
            data=_sample_definition("Sample"),
            updated_at=123.0,
        )

        task_definitions = MagicMock(spec=TaskDefinitions)
        task_definitions.list.return_value = [record]

        response = await api.task_definitions_list(request, Encoder(), task_definitions)
        payload = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code
        assert payload == [record.serialize()]
        assert "filename" not in payload[0]

    async def test_list_definitions_includes_definition(self) -> None:
        request = MagicMock(spec=Request)
        request.query = {"include": "definition"}

        identifier = "f5b5e88d-5c6b-4a27-8453-1b6a4fb8a8d1"
        record = TaskDefinitionRecord(
            identifier=identifier,
            filename=f"{identifier}.json",
            name="Sample",
            priority=0,
            path=Path("/tmp/sample.json"),
            data=_sample_definition("Sample"),
            updated_at=123.0,
        )

        task_definitions = MagicMock(spec=TaskDefinitions)
        task_definitions.list.return_value = [record]

        response = await api.task_definitions_list(request, Encoder(), task_definitions)
        payload = json.loads(response.text)

        assert payload[0]["definition"]["name"] == "Sample"

    async def test_get_definition_not_found(self) -> None:
        request = MagicMock(spec=Request)
        request.match_info = {"identifier": "unknown"}

        task_definitions = MagicMock(spec=TaskDefinitions)
        task_definitions.get.return_value = None

        response = await api.task_definitions_get(request, Encoder(), task_definitions)
        payload = json.loads(response.text)

        assert response.status == web.HTTPNotFound.status_code
        assert "error" in payload

    async def test_create_definition_success(self) -> None:
        payload_definition = _sample_definition("New", priority=1)
        payload = {"definition": payload_definition}

        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value=payload)

        identifier = "4f08b8af-b87a-4d6e-9289-39e5172898aa"
        record = TaskDefinitionRecord(
            identifier=identifier,
            filename=f"{identifier}.json",
            name="New",
            priority=1,
            path=Path("/tmp/new.json"),
            data=payload["definition"],
            updated_at=123.0,
        )

        task_definitions = MagicMock(spec=TaskDefinitions)
        task_definitions.create.return_value = record

        response = await api.task_definitions_create(request, Encoder(), task_definitions)
        body = json.loads(response.text)

        assert response.status == web.HTTPCreated.status_code
        assert body["id"] == identifier
        assert body["priority"] == 1
        assert "filename" not in body
        task_definitions.create.assert_called_once_with(payload_definition)

    async def test_create_definition_invalid_payload(self) -> None:
        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value=[])  # type: ignore[arg-type]

        task_definitions = MagicMock(spec=TaskDefinitions)

        response = await api.task_definitions_create(request, Encoder(), task_definitions)
        body = json.loads(response.text)

        assert response.status == web.HTTPBadRequest.status_code
        assert "error" in body

    async def test_update_definition_success(self) -> None:
        request = MagicMock(spec=Request)
        identifier = "6d8d5719-95ae-4478-bb05-986f5b72b6c1"
        request.match_info = {"identifier": identifier}
        definition = _sample_definition("Updated", priority=4)
        request.json = AsyncMock(return_value={"definition": definition})
        record = TaskDefinitionRecord(
            identifier=identifier,
            filename=f"{identifier}.json",
            name="Updated",
            priority=4,
            path=Path("/tmp/existing.json"),
            data=definition,
            updated_at=456.0,
        )

        task_definitions = MagicMock(spec=TaskDefinitions)
        task_definitions.update.return_value = record

        response = await api.task_definitions_update(request, Encoder(), task_definitions)
        body = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code
        assert body["name"] == "Updated"
        assert body["priority"] == 4
        task_definitions.update.assert_called_once_with(identifier, definition)

    async def test_update_definition_missing_identifier(self) -> None:
        request = MagicMock(spec=Request)
        request.match_info = {"identifier": ""}
        request.json = AsyncMock(return_value={})

        task_definitions = MagicMock(spec=TaskDefinitions)

        response = await api.task_definitions_update(request, Encoder(), task_definitions)
        body = json.loads(response.text)

        assert response.status == web.HTTPBadRequest.status_code
        assert "error" in body

    async def test_delete_definition_success(self) -> None:
        request = MagicMock(spec=Request)
        identifier = "c9f4ac6c-a4ab-4d1a-8d25-764dc0c8a3f0"
        request.match_info = {"identifier": identifier}

        task_definitions = MagicMock(spec=TaskDefinitions)

        response = await api.task_definitions_delete(request, task_definitions)
        body = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code
        assert body["status"] == "deleted"
        task_definitions.delete.assert_called_once_with(identifier)

    async def test_delete_definition_missing_identifier(self) -> None:
        request = MagicMock(spec=Request)
        request.match_info = {"identifier": ""}

        task_definitions = MagicMock(spec=TaskDefinitions)

        response = await api.task_definitions_delete(request, task_definitions)
        body = json.loads(response.text)

        assert response.status == web.HTTPBadRequest.status_code
        assert "error" in body
