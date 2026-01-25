from __future__ import annotations

import pytest
import pytest_asyncio

from app.features.presets.repository import PresetsRepository
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
