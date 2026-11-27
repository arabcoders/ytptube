from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.web import Request

from app.features.presets.repository import PresetsRepository
from app.features.presets.router import presets_add, presets_list, presets_patch
from app.features.presets.service import Presets
from app.library.encoder import Encoder
from app.library.Services import Services
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
        assert fetched.max_workers == 0

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
async def test_preset_cache_refresh(repo: PresetsRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Services, "get_instance", Mock())
    presets = object.__new__(Presets)
    presets.__init__(repo)
    async with asyncio.timeout(5):
        proxy = await repo.create({"name": "Proxy Preset", "priority": 1, "max_workers": 1})
        await repo.create({"name": "Home"})
        await presets.refresh_cache(await repo.all())

        assert [preset.name for preset in presets.get_all()] == ["proxy_preset", "home"]
        cached = presets.get(" PROXY PRESET ")
        assert cached is not None and cached.max_workers == 1
        assert presets.get(proxy.id) is cached

        await repo.update(proxy.id, {"name": "New Proxy", "max_workers": 2})
        await presets.refresh_cache(await repo.all())
    assert presets.get("proxy_preset") is None
    cached = presets.get("new_proxy")
    assert cached is not None and cached.max_workers == 2
    assert presets.get(proxy.id) is cached


@pytest.mark.asyncio
class TestPresetRoutes:
    async def test_worker_limit_roundtrip(self, repo: PresetsRepository) -> None:
        notify = Mock()
        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value={"name": "Proxy", "max_workers": 1})
        encoder = Encoder()

        response = await presets_add(request, encoder, notify, repo)
        assert response.status == web.HTTPOk.status_code
        payload = json.loads(response.text)
        assert payload["max_workers"] == 1
        preset_id = payload["id"]
        request.match_info = {"id": str(preset_id)}

        for body, cap in [
            ({"description": "Slow proxy"}, 1),
            ({"max_workers": 1000}, 1000),
            ({"max_workers": 0}, 0),
        ]:
            request.json.return_value = body
            response = await presets_patch(request, encoder, notify, repo)
            assert response.status == web.HTTPOk.status_code
            assert json.loads(response.text)["max_workers"] == cap
            fetched = await repo.get(preset_id)
            assert fetched is not None and fetched.max_workers == cap

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
