from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.web import Request

from app.features.presets.repository import PresetsRepository
from app.features.presets.router import presets_list
from app.library.encoder import Encoder
from app.library.sqlite_store import SqliteStore
from app.tests.helpers import make_in_memory_db_path


@pytest_asyncio.fixture
async def repo():
    PresetsRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=make_in_memory_db_path("presets-repository"))
    await store.get_connection()

    repository = PresetsRepository.get_instance()
    yield repository

    await store.close()

    PresetsRepository._reset_singleton()
    SqliteStore._reset_singleton()


class TestPresetsRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(self, repo):
        preset = await repo.create({"name": "Custom", "cli": "--format best"})

        assert preset.id is not None
        assert preset.name == "custom"
        assert preset.cli == "--format best"

        fetched = await repo.get(preset.id)
        assert fetched is not None
        assert fetched.name == "custom"

    @pytest.mark.asyncio
    async def test_create_normalizes_spaces(self, repo):
        preset = await repo.create({"name": "My Preset"})

        assert preset.name == "my_preset"

    @pytest.mark.asyncio
    async def test_orders_priority_then_name(self, repo):
        await repo.create({"name": "B", "priority": 1})
        await repo.create({"name": "A", "priority": 1})
        await repo.create({"name": "C", "priority": 2})

        items = await repo.all()

        assert items[0].name == "c", "Highest priority should be first"
        assert items[1].name == "a", "Same priority should sort by name"
        assert items[2].name == "b", "Same priority should sort by name"

    @pytest.mark.asyncio
    async def test_list_paginated(self, repo):
        for i in range(5):
            await repo.create({"name": f"Item {i}", "priority": i})

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=2)

        assert len(items) == 2
        assert total == 5
        assert page == 1
        assert total_pages == 3
        assert [item.priority for item in items] == [4, 3]

    @pytest.mark.asyncio
    async def test_paginated_sorts_name_desc(self, repo):
        await repo.create({"name": "Alpha", "priority": 1})
        await repo.create({"name": "Gamma", "priority": 3})
        await repo.create({"name": "Beta", "priority": 2})

        items, _, _, _ = await repo.list_paginated(page=1, per_page=10, sort="name", order="desc")

        assert [item.name for item in items] == ["gamma", "beta", "alpha"]

    @pytest.mark.asyncio
    async def test_list_paginated_excludes_defaults(self, repo):
        await repo.create({"name": "System Default", "default": True, "priority": 10})
        await repo.create({"name": "Custom Preset", "priority": 1})

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=10, exclude_defaults=True)

        assert [item.name for item in items] == ["custom_preset"]
        assert total == 1
        assert page == 1
        assert total_pages == 1

    @pytest.mark.asyncio
    async def test_list_paginated_multi_sort(self, repo):
        await repo.create({"name": "Charlie", "priority": 2})
        await repo.create({"name": "Alpha", "priority": 1})
        await repo.create({"name": "Bravo", "priority": 1})

        items, _, _, _ = await repo.list_paginated(page=1, per_page=10, sort="priority,name", order="asc,desc")

        assert [(item.priority, item.name) for item in items] == [
            (1, "bravo"),
            (1, "alpha"),
            (2, "charlie"),
        ]

    @pytest.mark.asyncio
    async def test_list_paginated_bad_sort(self, repo):
        with pytest.raises(ValueError):
            await repo.list_paginated(page=1, per_page=10, sort="cli", order="asc")

    @pytest.mark.asyncio
    async def test_list_paginated_bad_order(self, repo):
        with pytest.raises(ValueError):
            await repo.list_paginated(page=1, per_page=10, sort="name", order="sideways")

    @pytest.mark.asyncio
    async def test_list_paginated_mismatched_order(self, repo):
        with pytest.raises(ValueError):
            await repo.list_paginated(page=1, per_page=10, sort="priority,name", order="asc,desc,asc")


@pytest.mark.asyncio
class TestPresetRoutes:
    async def test_list_route_sort(self, repo):
        await repo.create({"name": "Alpha", "priority": 1})
        await repo.create({"name": "Bravo", "priority": 1})
        await repo.create({"name": "Charlie", "priority": 2})

        request = MagicMock(spec=Request)
        request.query = {"page": "1", "per_page": "10", "sort": "priority,name", "order": "asc,desc"}

        response = await presets_list(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code
        assert [item["name"] for item in payload["items"]] == ["bravo", "alpha", "charlie"]

    async def test_list_route_bad_sort(self, repo):
        request = MagicMock(spec=Request)
        request.query = {"sort": "cli", "order": "asc"}

        response = await presets_list(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPBadRequest.status_code
        assert "sort" in payload["error"]
        assert payload["code"] == "INVALID"
        assert payload["params"] == {"resource": "api.resources.preset"}

    async def test_list_route_bad_order(self, repo):
        request = MagicMock(spec=Request)
        request.query = {"sort": "name", "order": "sideways"}

        response = await presets_list(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPBadRequest.status_code
        assert "order" in payload["error"]
        assert payload["code"] == "INVALID"

    async def test_list_route_exclude_defaults(self, repo):
        await repo.create({"name": "System Default", "default": True, "priority": 10})
        await repo.create({"name": "Custom Preset", "priority": 1})

        request = MagicMock(spec=Request)
        request.query = {"page": "1", "per_page": "10", "exclude_defaults": "true"}

        response = await presets_list(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code
        assert [item["name"] for item in payload["items"]] == ["custom_preset"]
        assert payload["pagination"]["total"] == 1
