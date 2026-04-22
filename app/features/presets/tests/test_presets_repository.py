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


@pytest_asyncio.fixture
async def repo():
    PresetsRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=":memory:")
    await store.get_connection()

    repository = PresetsRepository.get_instance()
    yield repository

    if store._conn:
        await store._conn.close()
    if store._engine:
        await store._engine.dispose()

    PresetsRepository._reset_singleton()
    SqliteStore._reset_singleton()


class TestPresetsRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(self, repo):
        preset = await repo.create({"name": "Custom", "cli": "--format best"})

        assert preset.id is not None, "Should generate ID for new preset"
        assert preset.name == "custom", "Should normalize preset name"
        assert preset.cli == "--format best", "Should store preset cli"

        fetched = await repo.get(preset.id)
        assert fetched is not None, "Should fetch preset by id"
        assert fetched.name == "custom", "Should return matching preset"

    @pytest.mark.asyncio
    async def test_create_normalizes_spaces(self, repo):
        preset = await repo.create({"name": "My Preset"})

        assert preset.name == "my_preset", "Should normalize spaces to underscores"

    @pytest.mark.asyncio
    async def test_list_orders_by_priority_then_name(self, repo):
        await repo.create({"name": "B", "priority": 1})
        await repo.create({"name": "A", "priority": 1})
        await repo.create({"name": "C", "priority": 2})

        items = await repo.list()

        assert items[0].name == "c", "Highest priority should be first"
        assert items[1].name == "a", "Same priority should sort by name"
        assert items[2].name == "b", "Same priority should sort by name"

    @pytest.mark.asyncio
    async def test_list_paginated(self, repo):
        for i in range(5):
            await repo.create({"name": f"Item {i}", "priority": i})

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=2)

        assert len(items) == 2, "Should return 2 items per page"
        assert total == 5, "Should report total count"
        assert page == 1, "Should be on page 1"
        assert total_pages == 3, "Should have 3 pages total"
        assert [item.priority for item in items] == [4, 3], "Should keep default priority-desc order"

    @pytest.mark.asyncio
    async def test_list_paginated_sorts_by_name_desc(self, repo):
        await repo.create({"name": "Alpha", "priority": 1})
        await repo.create({"name": "Gamma", "priority": 3})
        await repo.create({"name": "Beta", "priority": 2})

        items, _, _, _ = await repo.list_paginated(page=1, per_page=10, sort="name", order="desc")

        assert [item.name for item in items] == ["gamma", "beta", "alpha"], "Should sort by requested field"

    @pytest.mark.asyncio
    async def test_list_paginated_excludes_defaults(self, repo):
        await repo.create({"name": "System Default", "default": True, "priority": 10})
        await repo.create({"name": "Custom Preset", "priority": 1})

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=10, exclude_defaults=True)

        assert [item.name for item in items] == ["custom_preset"], "Should exclude default presets"
        assert total == 1, "Should count only custom presets"
        assert page == 1, "Should keep current page when filtered results exist"
        assert total_pages == 1, "Should compute pages from the filtered total"

    @pytest.mark.asyncio
    async def test_list_paginated_supports_multiple_sort_fields(self, repo):
        await repo.create({"name": "Charlie", "priority": 2})
        await repo.create({"name": "Alpha", "priority": 1})
        await repo.create({"name": "Bravo", "priority": 1})

        items, _, _, _ = await repo.list_paginated(page=1, per_page=10, sort="priority,name", order="asc,desc")

        assert [(item.priority, item.name) for item in items] == [
            (1, "bravo"),
            (1, "alpha"),
            (2, "charlie"),
        ], "Should support multiple sort fields and directions"

    @pytest.mark.asyncio
    async def test_list_paginated_rejects_invalid_sort_field(self, repo):
        with pytest.raises(ValueError, match="sort must use supported fields"):
            await repo.list_paginated(page=1, per_page=10, sort="cli", order="asc")

    @pytest.mark.asyncio
    async def test_list_paginated_rejects_invalid_sort_direction(self, repo):
        with pytest.raises(ValueError, match="order must be 'asc' or 'desc'"):
            await repo.list_paginated(page=1, per_page=10, sort="name", order="sideways")

    @pytest.mark.asyncio
    async def test_list_paginated_rejects_mismatched_sort_and_order_lengths(self, repo):
        with pytest.raises(ValueError, match="order must provide one direction or match the number of sort fields"):
            await repo.list_paginated(page=1, per_page=10, sort="priority,name", order="asc,desc,asc")


@pytest.mark.asyncio
class TestPresetRoutes:
    async def test_list_route_supports_sort_params(self, repo):
        await repo.create({"name": "Alpha", "priority": 1})
        await repo.create({"name": "Bravo", "priority": 1})
        await repo.create({"name": "Charlie", "priority": 2})

        request = MagicMock(spec=Request)
        request.query = {"page": "1", "per_page": "10", "sort": "priority,name", "order": "asc,desc"}

        response = await presets_list(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code, "Should return 200 for valid sorting"
        assert [item["name"] for item in payload["items"]] == ["bravo", "alpha", "charlie"], "Should sort response"

    async def test_list_route_rejects_invalid_sort_field(self, repo):
        request = MagicMock(spec=Request)
        request.query = {"sort": "cli", "order": "asc"}

        response = await presets_list(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPBadRequest.status_code, "Should reject unsupported sort field"
        assert "sort" in payload["error"], "Should explain invalid sort field"

    async def test_list_route_rejects_invalid_sort_direction(self, repo):
        request = MagicMock(spec=Request)
        request.query = {"sort": "name", "order": "sideways"}

        response = await presets_list(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPBadRequest.status_code, "Should reject unsupported sort direction"
        assert "order" in payload["error"], "Should explain invalid sort direction"

    async def test_list_route_supports_excluding_defaults(self, repo):
        await repo.create({"name": "System Default", "default": True, "priority": 10})
        await repo.create({"name": "Custom Preset", "priority": 1})

        request = MagicMock(spec=Request)
        request.query = {"page": "1", "per_page": "10", "exclude_defaults": "true"}

        response = await presets_list(request, Encoder(), repo)
        payload = json.loads(response.text)

        assert response.status == web.HTTPOk.status_code, "Should return 200 for valid default exclusion"
        assert [item["name"] for item in payload["items"]] == ["custom_preset"], "Should exclude default presets"
        assert payload["pagination"]["total"] == 1, "Should report filtered total"
