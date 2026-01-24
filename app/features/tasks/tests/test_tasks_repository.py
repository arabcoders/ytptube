"""Tests for TasksRepository."""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.features.tasks.models import TaskModel
from app.features.tasks.repository import TasksRepository
from app.library.sqlite_store import SqliteStore


@pytest_asyncio.fixture
async def repo(tmp_path):
    """Provide a fresh repository instance with initialized database for each test."""
    TasksRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=str(":memory:"))
    await store.get_connection()

    repository = TasksRepository.get_instance()

    yield repository

    if store._conn:
        await store._conn.close()
    if store._engine:
        await store._engine.dispose()

    TasksRepository._reset_singleton()
    SqliteStore._reset_singleton()


class TestTasksRepository:
    """Test suite for TasksRepository database operations."""

    @pytest.mark.asyncio
    async def test_repository_singleton(self, repo):
        """Verify repository follows singleton pattern."""
        instance1 = TasksRepository.get_instance()
        instance2 = TasksRepository.get_instance()
        assert instance1 is instance2, "Should return same singleton instance"

    @pytest.mark.asyncio
    async def test_list_empty(self, repo):
        """List returns empty when no tasks exist."""
        tasks = await repo.list()
        assert tasks == [], "Should return empty list when no tasks"

    @pytest.mark.asyncio
    async def test_count_empty(self, repo):
        """Count returns 0 when no tasks exist."""
        count = await repo.count()
        assert count == 0, "Should return 0 when no tasks exist"

    @pytest.mark.asyncio
    async def test_create_task(self, repo):
        """Create task with valid data."""
        data = {
            "name": "Daily Download",
            "url": "https://example.com/video",
            "folder": "/downloads",
            "preset": "audio",
            "timer": "0 0 * * *",
            "template": "%(title)s.%(ext)s",
            "cli": "--format best",
            "auto_start": True,
            "handler_enabled": True,
            "enabled": True,
        }

        model = await repo.create(data)

        assert model.id is not None, "Should generate ID for new task"
        assert model.name == "Daily Download", "Should store name correctly"
        assert model.url == "https://example.com/video", "Should store URL correctly"
        assert model.folder == "/downloads", "Should store folder correctly"
        assert model.preset == "audio", "Should store preset correctly"
        assert model.timer == "0 0 * * *", "Should store timer correctly"
        assert model.template == "%(title)s.%(ext)s", "Should store template correctly"
        assert model.cli == "--format best", "Should store CLI correctly"
        assert model.auto_start is True, "Should store auto_start correctly"
        assert model.handler_enabled is True, "Should store handler_enabled correctly"
        assert model.enabled is True, "Should store enabled correctly"
        assert model.created_at is not None, "Should have created_at timestamp"
        assert model.updated_at is not None, "Should have updated_at timestamp"

    @pytest.mark.asyncio
    async def test_create_with_minimal_data(self, repo):
        """Create task with minimal required data."""
        data = {
            "name": "Simple Task",
            "url": "https://example.com",
        }

        model = await repo.create(data)

        assert model.name == "Simple Task", "Should store name"
        assert model.url == "https://example.com", "Should store URL"
        assert model.folder == "", "Should default folder to empty string"
        assert model.preset == "", "Should default preset to empty string"
        assert model.timer == "", "Should default timer to empty string"
        assert model.template == "", "Should default template to empty string"
        assert model.cli == "", "Should default CLI to empty string"
        assert model.auto_start is True, "Should default auto_start to True"
        assert model.handler_enabled is True, "Should default handler_enabled to True"
        assert model.enabled is True, "Should default enabled to True"

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo):
        """Get task by integer ID."""
        created = await repo.create(
            {
                "name": "Get Test",
                "url": "https://example.com",
            }
        )

        retrieved = await repo.get(created.id)

        assert retrieved is not None, "Should retrieve created task"
        assert retrieved.id == created.id, "Should retrieve correct task by ID"
        assert retrieved.name == "Get Test", "Should match created task name"

    @pytest.mark.asyncio
    async def test_get_by_string_id(self, repo):
        """Get task by string ID."""
        created = await repo.create(
            {
                "name": "String ID Test",
                "url": "https://example.com",
            }
        )

        retrieved = await repo.get(str(created.id))

        assert retrieved is not None, "Should retrieve by string ID"
        assert retrieved.id == created.id, "Should match created task ID"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, repo):
        """Get nonexistent task returns None."""
        result = await repo.get(99999)
        assert result is None, "Should return None for nonexistent ID"

        result = await repo.get("99999")
        assert result is None, "Should return None for nonexistent string ID"

    @pytest.mark.asyncio
    async def test_update_task(self, repo):
        """Update existing task."""
        created = await repo.create(
            {
                "name": "Update Test",
                "url": "https://example.com",
                "preset": "video",
                "enabled": True,
            }
        )

        updated = await repo.update(
            created.id,
            {
                "name": "Updated Name",
                "preset": "audio",
                "enabled": False,
            },
        )

        assert updated.name == "Updated Name", "Should update name"
        assert updated.preset == "audio", "Should update preset"
        assert updated.enabled is False, "Should update enabled"
        assert updated.url == "https://example.com", "Should preserve unchanged URL"

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises(self, repo):
        """Update nonexistent task raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            await repo.update(99999, {"name": "should_fail"})

    @pytest.mark.asyncio
    async def test_delete_task(self, repo):
        """Delete existing task."""
        created = await repo.create(
            {
                "name": "Delete Test",
                "url": "https://example.com",
            }
        )

        deleted = await repo.delete(created.id)

        assert deleted.id == created.id, "Should return deleted task"

        result = await repo.get(created.id)
        assert result is None, "Deleted task should not be retrievable"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, repo):
        """Delete nonexistent task raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            await repo.delete(99999)

    @pytest.mark.asyncio
    async def test_get_by_name(self, repo):
        """Get task by name."""
        await repo.create(
            {
                "name": "Named Task",
                "url": "https://example.com",
            }
        )

        retrieved = await repo.get_by_name("Named Task")

        assert retrieved is not None, "Should retrieve by name"
        assert retrieved.name == "Named Task", "Should match task name"

    @pytest.mark.asyncio
    async def test_get_by_name_excludes_id(self, repo):
        """Get by name can exclude specific ID."""
        first = await repo.create(
            {
                "name": "duplicate",
                "url": "https://example.com",
            }
        )

        result = await repo.get_by_name("duplicate", exclude_id=first.id)
        assert result is None, "Should not find when excluding only match"

        result = await repo.get_by_name("duplicate", exclude_id=None)
        assert result is not None, "Should find without exclusion"

    @pytest.mark.asyncio
    async def test_get_all_enabled(self, repo):
        """Get all enabled tasks."""
        await repo.create({"name": "Enabled 1", "url": "https://example.com", "enabled": True})
        await repo.create({"name": "Disabled", "url": "https://example.com", "enabled": False})
        await repo.create({"name": "Enabled 2", "url": "https://example.com", "enabled": True})

        enabled = await repo.get_all_enabled()

        assert len(enabled) == 2, "Should return only enabled tasks"
        assert all(task.enabled for task in enabled), "All tasks should be enabled"

    @pytest.mark.asyncio
    async def test_get_all_with_timer(self, repo):
        """Get all tasks with timer configured."""
        await repo.create({"name": "With Timer", "url": "https://example.com", "timer": "0 0 * * *"})
        await repo.create({"name": "No Timer", "url": "https://example.com", "timer": ""})
        await repo.create({"name": "Another Timer", "url": "https://example.com", "timer": "0 12 * * *"})

        with_timer = await repo.get_all_with_timer()

        assert len(with_timer) == 2, "Should return only tasks with timer"
        assert all(task.timer for task in with_timer), "All tasks should have timer"

    @pytest.mark.asyncio
    async def test_list_paginated(self, repo):
        """List paginated returns correct subset."""
        for i in range(5):
            await repo.create(
                {
                    "name": f"Task {i}",
                    "url": "https://example.com",
                }
            )

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=2)

        assert len(items) == 2, "Should return 2 items per page"
        assert total == 5, "Should report total count of 5"
        assert page == 1, "Should be on page 1"
        assert total_pages == 3, "Should have 3 pages total"

    @pytest.mark.asyncio
    async def test_list_ordering(self, repo):
        """List orders by name ascending."""
        await repo.create({"name": "Charlie", "url": "https://example.com"})
        await repo.create({"name": "Alice", "url": "https://example.com"})
        await repo.create({"name": "Bob", "url": "https://example.com"})

        items = await repo.list()

        assert items[0].name == "Alice", "Should be alphabetically first"
        assert items[1].name == "Bob", "Should be alphabetically second"
        assert items[2].name == "Charlie", "Should be alphabetically third"
