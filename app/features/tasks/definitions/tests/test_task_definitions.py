from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.web import Request

from app.features.tasks.definitions.repository import TaskDefinitionsRepository
from app.features.tasks.definitions.router import (
    task_definitions_create,
    task_definitions_delete,
    task_definitions_get,
    task_definitions_list,
    task_definitions_patch,
    task_definitions_update,
)
from app.library.encoder import Encoder
from app.library.sqlite_store import SqliteStore
from app.main import EventBus


def _sample_definition(name: str = "example", *, priority: int = 0) -> dict:
    """Returns a properly structured task definition payload for the repository."""
    return {
        "name": name,
        "match_url": ["https://example.com/*"],
        "priority": priority,
        "definition": {
            "parse": {
                "link": {
                    "type": "css",
                    "expression": "a",
                    "attribute": "href",
                }
            },
            "engine": {"type": "httpx"},
            "request": {},
            "response": {"type": "html"},
        },
    }


@pytest_asyncio.fixture
async def repo() -> AsyncGenerator[TaskDefinitionsRepository, None]:
    TaskDefinitionsRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=":memory:")
    await store.get_connection()

    repository = TaskDefinitionsRepository.get_instance()

    yield repository

    if store._conn:
        await store._conn.close()
    if store._engine:
        await store._engine.dispose()

    TaskDefinitionsRepository._reset_singleton()
    SqliteStore._reset_singleton()


class TestTaskDefinitionsRepository:
    @pytest.mark.asyncio
    async def test_create_and_list(self, repo: TaskDefinitionsRepository) -> None:
        await repo.create(_sample_definition("Alpha", priority=2))
        await repo.create(_sample_definition("Beta", priority=1))

        items = await repo.list()
        assert len(items) == 2, "Should return two task definitions"
        assert [item.name for item in items] == ["Beta", "Alpha"], "Should sort by priority then name"

    @pytest.mark.asyncio
    async def test_create_duplicate_name_raises(self, repo: TaskDefinitionsRepository) -> None:
        payload = _sample_definition("Dup")
        await repo.create(payload)

        with pytest.raises(ValueError, match="already exists"):
            await repo.create(payload)

        with pytest.raises(ValueError, match="already exists"):
            await repo.create(payload)

    @pytest.mark.asyncio
    async def test_update_missing_raises(self, repo: TaskDefinitionsRepository) -> None:
        with pytest.raises(KeyError, match="not found"):
            await repo.update(999, {"name": "Missing"})

    @pytest.mark.asyncio
    async def test_list_paginated(self, repo: TaskDefinitionsRepository) -> None:
        for idx in range(5):
            await repo.create(_sample_definition(f"Item {idx}", priority=idx))

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=2)
        assert len(items) == 2, "Should return two items per page"
        assert total == 5, "Should report total count of 5"
        assert page == 1, "Should return requested page"
        assert total_pages == 3, "Should compute total pages"


@pytest.mark.asyncio
class TestTaskDefinitionRoutes:
    async def test_list_definitions(self, repo: TaskDefinitionsRepository) -> None:
        await repo.create(_sample_definition("Sample"))
        request = MagicMock(spec=Request)
        request.query = {}

        response = await task_definitions_list(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code, "Should return 200 for list"
        assert payload["items"][0]["name"] == "Sample", "Should include created definition"

    async def test_get_definition_not_found(self, repo: TaskDefinitionsRepository) -> None:
        request = MagicMock(spec=Request)
        request.match_info = {"id": "999"}

        response = await task_definitions_get(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPNotFound.status_code, "Should return 404 for missing definition"
        assert "error" in payload, "Should include error payload"

    async def test_create_definition_success(self, repo: TaskDefinitionsRepository) -> None:
        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value=_sample_definition("New", priority=3))

        response = await task_definitions_create(request, Encoder(), MagicMock(spec=EventBus), repo)
        body = json.loads(response.text)

        assert response.status == web.HTTPCreated.status_code, "Should create task definition"
        assert body["name"] == "New", "Should return created name"
        assert body["priority"] == 3, "Should return created priority"

    async def test_update_definition_success(self, repo: TaskDefinitionsRepository) -> None:
        created = await repo.create(_sample_definition("Original", priority=0))

        request = MagicMock(spec=Request)
        request.match_info = {"id": str(created.id)}
        request.json = AsyncMock(return_value=_sample_definition("Updated", priority=4))

        response = await task_definitions_update(request, Encoder(), MagicMock(spec=EventBus), repo)
        body = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code, "Should update task definition"
        assert body["name"] == "Updated", "Should return updated name"
        assert body["priority"] == 4, "Should return updated priority"

    async def test_delete_definition_success(self, repo: TaskDefinitionsRepository) -> None:
        created = await repo.create(_sample_definition("Delete"))

        request = MagicMock(spec=Request)
        request.match_info = {"id": str(created.id)}

        response = await task_definitions_delete(request, Encoder(), MagicMock(spec=EventBus), repo)
        assert response.status == web.HTTPOk.status_code, "Should delete task definition"

    async def test_patch_definition_enabled(self, repo: TaskDefinitionsRepository) -> None:
        created = await repo.create(_sample_definition("PatchTest", priority=5))
        assert created.enabled is True, "Should be enabled by default"

        request = MagicMock(spec=Request)
        request.match_info = {"id": str(created.id)}
        request.json = AsyncMock(return_value={"enabled": False})

        response = await task_definitions_patch(request, Encoder(), MagicMock(spec=EventBus), repo)
        body = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code, "Should patch task definition"
        assert body["name"] == "PatchTest", "Should keep original name"
        assert body["priority"] == 5, "Should keep original priority"
        assert body["enabled"] is False, "Should update enabled status"

    async def test_patch_definition_priority(self, repo: TaskDefinitionsRepository) -> None:
        created = await repo.create(_sample_definition("PatchPriority", priority=1))

        request = MagicMock(spec=Request)
        request.match_info = {"id": str(created.id)}
        request.json = AsyncMock(return_value={"priority": 10})

        response = await task_definitions_patch(request, Encoder(), MagicMock(spec=EventBus), repo)
        body = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code, "Should patch task definition"
        assert body["priority"] == 10, "Should update priority"
        assert body["enabled"] is True, "Should keep original enabled status"

    async def test_patch_definition_not_found(self, repo: TaskDefinitionsRepository) -> None:
        request = MagicMock(spec=Request)
        request.match_info = {"id": "999"}
        request.json = AsyncMock(return_value={"enabled": False})

        response = await task_definitions_patch(request, Encoder(), MagicMock(spec=EventBus), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPNotFound.status_code, "Should return 404 for missing definition"
        assert "error" in payload, "Should include error payload"

    async def test_create_with_regex_pattern(self, repo: TaskDefinitionsRepository) -> None:
        payload = _sample_definition("RegexTest", priority=0)
        payload["match_url"] = ["/https://example\\.com/post/[0-9]+/"]

        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value=payload)

        response = await task_definitions_create(request, Encoder(), MagicMock(spec=EventBus), repo)
        body = json.loads(response.text)

        assert response.status == web.HTTPCreated.status_code, "Should create task definition with regex pattern"
        assert body["match_url"][0] == "/https://example\\.com/post/[0-9]+/", "Should preserve regex pattern format"

    async def test_create_with_invalid_regex_pattern(self, repo: TaskDefinitionsRepository) -> None:
        payload = _sample_definition("BadRegex", priority=0)
        payload["match_url"] = ["/[invalid(/"]

        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value=payload)

        response = await task_definitions_create(request, Encoder(), MagicMock(spec=EventBus), repo)
        payload_response = json.loads(response.text)

        assert response.status == web.HTTPBadRequest.status_code, "Should reject invalid regex pattern"
        assert "error" in payload_response, "Should include error payload"
