from __future__ import annotations

import pytest
import pytest_asyncio
from app.features.conditions.repository import ConditionsRepository
from app.library.sqlite_store import SqliteStore
from app.tests.helpers import make_in_memory_db_path


@pytest_asyncio.fixture
async def repo():
    ConditionsRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=make_in_memory_db_path("conditions-repository"))
    await store.get_connection()

    repository = ConditionsRepository.get_instance()

    yield repository

    # Cleanup - close connections properly
    await store.close()

    # Reset singletons
    ConditionsRepository._reset_singleton()
    SqliteStore._reset_singleton()


class TestConditionsRepository:
    @pytest.mark.asyncio
    async def test_create_condition(self, repo):
        data = {
            "name": "Test Condition",
            "filter": "duration > 60",
            "cli": "--format best",
            "enabled": True,
            "priority": 10,
            "description": "Test description",
            "extras": {"key": "value"},
        }

        model = await repo.create(data)

        assert model.id is not None
        assert model.name == "Test Condition"
        assert model.filter == "duration > 60"
        assert model.cli == "--format best"
        assert model.enabled is True
        assert model.priority == 10
        assert model.description == "Test description"
        assert model.extras == {"key": "value"}

    @pytest.mark.asyncio
    async def test_create_with_defaults(self, repo):
        data = {
            "name": "Minimal",
            "filter": "duration > 30",
        }

        model = await repo.create(data)

        assert model.cli == ""
        assert model.enabled is True
        assert model.priority == 0
        assert model.description == ""
        assert model.extras == {}

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo):
        created = await repo.create({"name": "Get Test", "filter": "duration > 40"})

        retrieved = await repo.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Get Test"

    @pytest.mark.asyncio
    async def test_get_by_name(self, repo):
        await repo.create({"name": "Named Test", "filter": "duration > 50"})

        retrieved = await repo.get("Named Test")

        assert retrieved is not None
        assert retrieved.name == "Named Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, repo):
        result = await repo.get(99999)
        assert result is None

        result = await repo.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_condition(self, repo):
        created = await repo.create({"name": "Update Test", "filter": "duration > 60"})

        updated = await repo.update(
            created.id,
            {
                "name": "Updated Name",
                "priority": 5,
                "extras": {"updated": True},
            },
        )

        assert updated.name == "Updated Name"
        assert updated.priority == 5
        assert updated.extras == {"updated": True}
        assert updated.filter == "duration > 60"

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises(self, repo):
        with pytest.raises(KeyError):
            await repo.update(99999, {"name": "Should Fail"})

    @pytest.mark.asyncio
    async def test_delete_condition(self, repo):
        created = await repo.create({"name": "Delete Test", "filter": "duration > 70"})

        deleted = await repo.delete(created.id)

        assert deleted.id == created.id

        result = await repo.get(created.id)
        assert result is None, "Deleted condition should not be retrievable"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, repo):
        with pytest.raises(KeyError):
            await repo.delete(99999)

    @pytest.mark.asyncio
    async def test_list_paginated(self, repo):
        for i in range(5):
            await repo.create({"name": f"Item {i}", "filter": "duration > 10", "priority": i})

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=2)

        assert len(items) == 2
        assert total == 5
        assert page == 1
        assert total_pages == 3

    @pytest.mark.asyncio
    async def test_list_ordering(self, repo):
        await repo.create({"name": "B", "filter": "test", "priority": 1})
        await repo.create({"name": "A", "filter": "test", "priority": 1})
        await repo.create({"name": "C", "filter": "test", "priority": 2})

        items = await repo.all()

        assert items[0].name == "C", "Highest priority should be first"
        assert items[1].name == "A", "Same priority sorted alphabetically"
        assert items[2].name == "B", "Same priority sorted alphabetically"

    @pytest.mark.asyncio
    async def test_get_name_without_id(self, repo):
        first = await repo.create({"name": "Duplicate", "filter": "test"})

        result = await repo.get_by_name("Duplicate", exclude_id=first.id)
        assert result is None

        result = await repo.get_by_name("Duplicate", exclude_id=None)
        assert result is not None

    @pytest.mark.asyncio
    async def test_replace_all(self, repo):
        await repo.create({"name": "Old 1", "filter": "test"})
        await repo.create({"name": "Old 2", "filter": "test"})

        new_items = [
            {"name": "New 1", "filter": "duration > 10"},
            {"name": "New 2", "filter": "duration > 20"},
        ]

        result = await repo.replace_all(new_items)

        assert len(result) == 2

        all_items = await repo.all()
        assert len(all_items) == 2
        assert {item.name for item in all_items} == {"New 1", "New 2"}
