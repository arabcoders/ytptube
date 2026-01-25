"""Tests for DLFieldsRepository."""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.features.dl_fields.models import DLFieldModel
from app.features.dl_fields.repository import DLFieldsRepository
from app.library.sqlite_store import SqliteStore


@pytest_asyncio.fixture
async def repo(tmp_path):
    """Provide a fresh repository instance with initialized database for each test."""
    DLFieldsRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=str(":memory:"))
    await store.get_connection()

    repository = DLFieldsRepository.get_instance()

    yield repository

    if store._conn:
        await store._conn.close()
    if store._engine:
        await store._engine.dispose()

    DLFieldsRepository._reset_singleton()
    SqliteStore._reset_singleton()


class TestDLFieldsRepository:
    """Test suite for DLFieldsRepository database operations."""

    @pytest.mark.asyncio
    async def test_repository_singleton(self, repo):
        """Verify repository follows singleton pattern."""
        instance1 = DLFieldsRepository.get_instance()
        instance2 = DLFieldsRepository.get_instance()
        assert instance1 is instance2, "Should return same singleton instance"

    @pytest.mark.asyncio
    async def test_list_empty(self, repo):
        """List returns empty when no fields exist."""
        fields = await repo.list()
        assert fields == [], "Should return empty list when no fields"

    @pytest.mark.asyncio
    async def test_count_empty(self, repo):
        """Count returns 0 when no fields exist."""
        count = await repo.count()
        assert count == 0, "Should return 0 when no fields exist"

    @pytest.mark.asyncio
    async def test_create_field(self, repo):
        """Create field with valid data."""
        data = {
            "name": "quality",
            "description": "Video quality setting",
            "field": "--format",
            "kind": "string",
            "icon": "fa-video",
            "order": 1,
            "value": "best",
            "extras": {"options": ["best", "worst"]},
        }

        model = await repo.create(data)

        assert model.id is not None, "Should generate ID for new field"
        assert model.name == "quality", "Should store name correctly"
        assert model.description == "Video quality setting", "Should store description correctly"
        assert model.field == "--format", "Should store field correctly"
        assert model.kind == "string", "Should store kind correctly"
        assert model.icon == "fa-video", "Should store icon correctly"
        assert model.order == 1, "Should store order correctly"
        assert model.value == "best", "Should store value correctly"
        assert model.extras == {"options": ["best", "worst"]}, "Should store extras as dict"

    @pytest.mark.asyncio
    async def test_create_with_defaults(self, repo):
        """Create field with minimal data uses defaults."""
        data = {
            "name": "minimal",
            "description": "Minimal",
            "field": "--minimal",
            "kind": "text",
        }

        model = await repo.create(data)

        assert model.icon == "", "Should default icon to empty string"
        assert model.order == 0, "Should default order to 0"
        assert model.value == "", "Should default value to empty string"
        assert model.extras == {}, "Should default extras to empty dict"

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo):
        """Get field by integer ID."""
        created = await repo.create(
            {
                "name": "get_test",
                "description": "Get test",
                "field": "--get-test",
                "kind": "text",
            }
        )

        retrieved = await repo.get(created.id)

        assert retrieved is not None, "Should retrieve created field"
        assert retrieved.id == created.id, "Should retrieve correct field by ID"
        assert retrieved.name == "get_test", "Should match created field name"

    @pytest.mark.asyncio
    async def test_get_by_name(self, repo):
        """Get field by string name."""
        await repo.create(
            {
                "name": "named_test",
                "description": "Named test",
                "field": "--named-test",
                "kind": "text",
            }
        )

        retrieved = await repo.get("named_test")

        assert retrieved is not None, "Should retrieve by name"
        assert retrieved.name == "named_test", "Should match field name"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, repo):
        """Get nonexistent field returns None."""
        result = await repo.get(99999)
        assert result is None, "Should return None for nonexistent ID"

        result = await repo.get("nonexistent")
        assert result is None, "Should return None for nonexistent name"

    @pytest.mark.asyncio
    async def test_update_field(self, repo):
        """Update existing field."""
        created = await repo.create(
            {
                "name": "update_test",
                "description": "Update test",
                "field": "--update-test",
                "kind": "text",
            }
        )

        updated = await repo.update(
            created.id,
            {
                "name": "updated_name",
                "order": 5,
                "extras": {"updated": True},
            },
        )

        assert updated.name == "updated_name", "Should update name"
        assert updated.order == 5, "Should update order"
        assert updated.extras == {"updated": True}, "Should update extras"
        assert updated.field == "--update-test", "Should preserve unchanged field"

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises(self, repo):
        """Update nonexistent field raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            await repo.update(99999, {"name": "should_fail"})

    @pytest.mark.asyncio
    async def test_delete_field(self, repo):
        """Delete existing field."""
        created = await repo.create(
            {
                "name": "delete_test",
                "description": "Delete test",
                "field": "--delete-test",
                "kind": "text",
            }
        )

        deleted = await repo.delete(created.id)

        assert deleted.id == created.id, "Should return deleted field"

        result = await repo.get(created.id)
        assert result is None, "Deleted field should not be retrievable"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, repo):
        """Delete nonexistent field raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            await repo.delete(99999)

    @pytest.mark.asyncio
    async def test_list_paginated(self, repo):
        """List paginated returns correct subset."""
        for i in range(5):
            await repo.create(
                {
                    "name": f"item_{i}",
                    "description": "desc",
                    "field": f"--item-{i}",
                    "kind": "text",
                    "order": i,
                }
            )

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=2)

        assert len(items) == 2, "Should return 2 items per page"
        assert total == 5, "Should report total count of 5"
        assert page == 1, "Should be on page 1"
        assert total_pages == 3, "Should have 3 pages total"

    @pytest.mark.asyncio
    async def test_list_ordering(self, repo):
        """List orders by order asc then name asc."""
        await repo.create({"name": "b", "description": "b", "field": "--b", "kind": "text", "order": 1})
        await repo.create({"name": "a", "description": "a", "field": "--a", "kind": "text", "order": 1})
        await repo.create({"name": "c", "description": "c", "field": "--c", "kind": "text", "order": 0})

        items = await repo.list()

        assert items[0].name == "c", "Lowest order should be first"
        assert items[1].name == "a", "Same order sorted alphabetically"
        assert items[2].name == "b", "Same order sorted alphabetically"

    @pytest.mark.asyncio
    async def test_get_by_name_excludes_id(self, repo):
        """Get by name can exclude specific ID."""
        first = await repo.create(
            {
                "name": "duplicate",
                "description": "duplicate",
                "field": "--duplicate",
                "kind": "text",
            }
        )

        result = await repo.get_by_name("duplicate", exclude_id=first.id)
        assert result is None, "Should not find when excluding only match"

        result = await repo.get_by_name("duplicate", exclude_id=None)
        assert result is not None, "Should find without exclusion"

    @pytest.mark.asyncio
    async def test_replace_all(self, repo):
        """Replace all fields atomically."""
        await repo.create({"name": "old_1", "description": "old", "field": "--old-1", "kind": "text"})
        await repo.create({"name": "old_2", "description": "old", "field": "--old-2", "kind": "text"})

        new_items = [
            {"name": "new_1", "description": "new", "field": "--new-1", "kind": "text"},
            {"name": "new_2", "description": "new", "field": "--new-2", "kind": "text"},
        ]

        result = await repo.replace_all(new_items)

        assert len(result) == 2, "Should create 2 new fields"

        all_items = await repo.list()
        assert len(all_items) == 2, "Should only have new fields"
        assert {item.name for item in all_items} == {"new_1", "new_2"}, "Should only have new items"
