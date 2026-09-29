from __future__ import annotations

import pytest
import pytest_asyncio

from app.features.dl_fields.repository import DLFieldsRepository
from app.library.sqlite_store import SqliteStore
from app.tests.helpers import make_in_memory_db_path


@pytest_asyncio.fixture
async def repo():
    """Provide a fresh repository instance with initialized database for each test."""
    DLFieldsRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=make_in_memory_db_path("dl-fields-repository"))
    await store.get_connection()

    repository = DLFieldsRepository.get_instance()

    yield repository

    await store.close()

    DLFieldsRepository._reset_singleton()
    SqliteStore._reset_singleton()


class TestDLFieldsRepository:
    @pytest.mark.asyncio
    async def test_create_field(self, repo):
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

        assert model.id is not None
        assert model.name == "quality"
        assert model.description == "Video quality setting"
        assert model.field == "--format"
        assert model.kind == "string"
        assert model.icon == "fa-video"
        assert model.order == 1
        assert model.value == "best"
        assert model.extras == {"options": ["best", "worst"]}

    @pytest.mark.asyncio
    async def test_create_with_defaults(self, repo):
        data = {
            "name": "minimal",
            "description": "Minimal",
            "field": "--minimal",
            "kind": "text",
        }

        model = await repo.create(data)

        assert model.icon == ""
        assert model.order == 0
        assert model.value == ""
        assert model.extras == {}

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo):
        created = await repo.create(
            {
                "name": "get_test",
                "description": "Get test",
                "field": "--get-test",
                "kind": "text",
            }
        )

        retrieved = await repo.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "get_test"

    @pytest.mark.asyncio
    async def test_get_by_name(self, repo):
        await repo.create(
            {
                "name": "named_test",
                "description": "Named test",
                "field": "--named-test",
                "kind": "text",
            }
        )

        retrieved = await repo.get("named_test")

        assert retrieved is not None
        assert retrieved.name == "named_test"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, repo):
        result = await repo.get(99999)
        assert result is None

        result = await repo.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_field(self, repo):
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

        assert updated.name == "updated_name"
        assert updated.order == 5
        assert updated.extras == {"updated": True}
        assert updated.field == "--update-test"

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises(self, repo):
        with pytest.raises(KeyError):
            await repo.update(99999, {"name": "should_fail"})

    @pytest.mark.asyncio
    async def test_delete_field(self, repo):
        created = await repo.create(
            {
                "name": "delete_test",
                "description": "Delete test",
                "field": "--delete-test",
                "kind": "text",
            }
        )

        deleted = await repo.delete(created.id)

        assert deleted.id == created.id

        result = await repo.get(created.id)
        assert result is None, "Deleted field should not be retrievable"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, repo):
        with pytest.raises(KeyError):
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

        assert len(items) == 2
        assert total == 5
        assert page == 1
        assert total_pages == 3

    @pytest.mark.asyncio
    async def test_list_ordering(self, repo):
        """List orders by order asc then name asc."""
        await repo.create({"name": "b", "description": "b", "field": "--b", "kind": "text", "order": 1})
        await repo.create({"name": "a", "description": "a", "field": "--a", "kind": "text", "order": 1})
        await repo.create({"name": "c", "description": "c", "field": "--c", "kind": "text", "order": 0})

        items = await repo.all()

        assert items[0].name == "c", "Lowest order should be first"
        assert items[1].name == "a", "Same order sorted alphabetically"
        assert items[2].name == "b", "Same order sorted alphabetically"

    @pytest.mark.asyncio
    async def test_get_name_excludes_id(self, repo):
        first = await repo.create(
            {
                "name": "duplicate",
                "description": "duplicate",
                "field": "--duplicate",
                "kind": "text",
            }
        )

        result = await repo.get_by_name("duplicate", exclude_id=first.id)
        assert result is None

        result = await repo.get_by_name("duplicate", exclude_id=None)
        assert result is not None

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

        assert len(result) == 2

        all_items = await repo.all()
        assert len(all_items) == 2
        assert {item.name for item in all_items} == {"new_1", "new_2"}
