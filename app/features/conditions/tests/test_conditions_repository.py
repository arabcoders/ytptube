"""Tests for ConditionsRepository."""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.features.conditions.models import ConditionModel
from app.features.conditions.repository import ConditionsRepository
from app.library.sqlite_store import SqliteStore


@pytest_asyncio.fixture
async def repo():
    ConditionsRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=":memory:")
    await store.get_connection()

    # Create repository
    repository = ConditionsRepository.get_instance()

    yield repository

    # Cleanup - close connections properly
    if store._conn:
        await store._conn.close()
    if store._engine:
        await store._engine.dispose()

    # Reset singletons
    ConditionsRepository._reset_singleton()
    SqliteStore._reset_singleton()


class TestConditionsRepository:
    """Test suite for ConditionsRepository database operations."""

    @pytest.mark.asyncio
    async def test_repository_singleton(self, repo):
        """Verify repository follows singleton pattern."""
        instance1 = ConditionsRepository.get_instance()
        instance2 = ConditionsRepository.get_instance()
        assert instance1 is instance2, "Should return same singleton instance"

    @pytest.mark.asyncio
    async def test_list_empty(self, repo):
        """List returns empty when no conditions exist."""
        conditions = await repo.list()
        assert conditions == [], "Should return empty list when no conditions"

    @pytest.mark.asyncio
    async def test_count_empty(self, repo):
        """Count returns 0 when no conditions exist."""
        count = await repo.count()
        assert count == 0, "Should return 0 when no conditions exist"

    @pytest.mark.asyncio
    async def test_create_condition(self, repo):
        """Create condition with valid data."""
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

        assert model.id is not None, "Should generate ID for new condition"
        assert model.name == "Test Condition", "Should store name correctly"
        assert model.filter == "duration > 60", "Should store filter correctly"
        assert model.cli == "--format best", "Should store CLI correctly"
        assert model.enabled is True, "Should store enabled flag correctly"
        assert model.priority == 10, "Should store priority correctly"
        assert model.description == "Test description", "Should store description correctly"
        assert model.extras == {"key": "value"}, "Should store extras as dict"

    @pytest.mark.asyncio
    async def test_create_with_defaults(self, repo):
        """Create condition with minimal data uses defaults."""
        data = {
            "name": "Minimal",
            "filter": "duration > 30",
        }

        model = await repo.create(data)

        assert model.cli == "", "Should default CLI to empty string"
        assert model.enabled is True, "Should default enabled to True"
        assert model.priority == 0, "Should default priority to 0"
        assert model.description == "", "Should default description to empty"
        assert model.extras == {}, "Should default extras to empty dict"

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo):
        """Get condition by integer ID."""
        created = await repo.create({"name": "Get Test", "filter": "duration > 40"})

        retrieved = await repo.get(created.id)

        assert retrieved is not None, "Should retrieve created condition"
        assert retrieved.id == created.id, "Should retrieve correct condition by ID"
        assert retrieved.name == "Get Test", "Should match created condition name"

    @pytest.mark.asyncio
    async def test_get_by_name(self, repo):
        """Get condition by string name."""
        await repo.create({"name": "Named Test", "filter": "duration > 50"})

        retrieved = await repo.get("Named Test")

        assert retrieved is not None, "Should retrieve by name"
        assert retrieved.name == "Named Test", "Should match condition name"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, repo):
        """Get nonexistent condition returns None."""
        result = await repo.get(99999)
        assert result is None, "Should return None for nonexistent ID"

        result = await repo.get("nonexistent")
        assert result is None, "Should return None for nonexistent name"

    @pytest.mark.asyncio
    async def test_update_condition(self, repo):
        """Update existing condition."""
        created = await repo.create({"name": "Update Test", "filter": "duration > 60"})

        updated = await repo.update(
            created.id,
            {
                "name": "Updated Name",
                "priority": 5,
                "extras": {"updated": True},
            },
        )

        assert updated.name == "Updated Name", "Should update name"
        assert updated.priority == 5, "Should update priority"
        assert updated.extras == {"updated": True}, "Should update extras"
        assert updated.filter == "duration > 60", "Should preserve unchanged filter"

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises(self, repo):
        """Update nonexistent condition raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            await repo.update(99999, {"name": "Should Fail"})

    @pytest.mark.asyncio
    async def test_delete_condition(self, repo):
        """Delete existing condition."""
        created = await repo.create({"name": "Delete Test", "filter": "duration > 70"})

        deleted = await repo.delete(created.id)

        assert deleted.id == created.id, "Should return deleted condition"

        result = await repo.get(created.id)
        assert result is None, "Deleted condition should not be retrievable"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, repo):
        """Delete nonexistent condition raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            await repo.delete(99999)

    @pytest.mark.asyncio
    async def test_list_paginated(self, repo):
        """List paginated returns correct subset."""
        for i in range(5):
            await repo.create({"name": f"Item {i}", "filter": "duration > 10", "priority": i})

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=2)

        assert len(items) == 2, "Should return 2 items per page"
        assert total == 5, "Should report total count of 5"
        assert page == 1, "Should be on page 1"
        assert total_pages == 3, "Should have 3 pages total"

    @pytest.mark.asyncio
    async def test_list_ordering(self, repo):
        """List orders by priority desc then name asc."""
        await repo.create({"name": "B", "filter": "test", "priority": 1})
        await repo.create({"name": "A", "filter": "test", "priority": 1})
        await repo.create({"name": "C", "filter": "test", "priority": 2})

        items = await repo.list()

        assert items[0].name == "C", "Highest priority should be first"
        assert items[1].name == "A", "Same priority sorted alphabetically"
        assert items[2].name == "B", "Same priority sorted alphabetically"

    @pytest.mark.asyncio
    async def test_get_by_name_excludes_id(self, repo):
        """Get by name can exclude specific ID."""
        first = await repo.create({"name": "Duplicate", "filter": "test"})

        result = await repo.get_by_name("Duplicate", exclude_id=first.id)
        assert result is None, "Should not find when excluding only match"

        result = await repo.get_by_name("Duplicate", exclude_id=None)
        assert result is not None, "Should find without exclusion"

    @pytest.mark.asyncio
    async def test_replace_all(self, repo):
        """Replace all conditions atomically."""
        await repo.create({"name": "Old 1", "filter": "test"})
        await repo.create({"name": "Old 2", "filter": "test"})

        new_items = [
            {"name": "New 1", "filter": "duration > 10"},
            {"name": "New 2", "filter": "duration > 20"},
        ]

        result = await repo.replace_all(new_items)

        assert len(result) == 2, "Should create 2 new conditions"

        all_items = await repo.list()
        assert len(all_items) == 2, "Should only have new conditions"
        assert all_items[0].name in ["New 1", "New 2"], "Should only have new items"
