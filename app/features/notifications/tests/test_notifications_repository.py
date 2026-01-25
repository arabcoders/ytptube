"""Tests for NotificationsRepository."""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.features.notifications.repository import NotificationsRepository
from app.library.sqlite_store import SqliteStore


@pytest_asyncio.fixture
async def repo(tmp_path):
    """Provide a fresh repository instance with initialized database for each test."""
    NotificationsRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=":memory:")
    await store.get_connection()

    repository = NotificationsRepository.get_instance()

    yield repository

    if store._conn:
        await store._conn.close()
    if store._engine:
        await store._engine.dispose()

    NotificationsRepository._reset_singleton()
    SqliteStore._reset_singleton()


class TestNotificationsRepository:
    """Test suite for NotificationsRepository database operations."""

    @pytest.mark.asyncio
    async def test_list_empty(self, repo):
        """List returns empty when no notifications exist."""
        notifications = await repo.list()
        assert notifications == [], "Should return empty list when no notifications exist"

    @pytest.mark.asyncio
    async def test_create_notification(self, repo):
        """Create notification with valid data."""
        payload = {
            "name": "Webhook",
            "on": ["item_completed"],
            "presets": [],
            "enabled": True,
            "request_url": "https://example.com/webhook",
            "request_method": "POST",
            "request_type": "json",
            "request_data_key": "data",
            "request_headers": [{"key": "Authorization", "value": "Bearer token"}],
        }

        model = await repo.create(payload)

        assert model.id is not None, "Should generate ID for new notification"
        assert model.name == "Webhook", "Should store name correctly"
        assert model.request_url == "https://example.com/webhook", "Should store request url"
        assert model.request_method == "POST", "Should store request method"

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo):
        """Get notification by integer ID."""
        created = await repo.create(
            {
                "name": "Get Test",
                "on": [],
                "presets": [],
                "enabled": True,
                "request_url": "https://example.com",
                "request_method": "POST",
                "request_type": "json",
                "request_data_key": "data",
                "request_headers": [],
            }
        )

        retrieved = await repo.get(created.id)

        assert retrieved is not None, "Should retrieve created notification"
        assert retrieved.id == created.id, "Should match created notification id"

    @pytest.mark.asyncio
    async def test_update_notification(self, repo):
        """Update existing notification."""
        created = await repo.create(
            {
                "name": "Update Test",
                "on": [],
                "presets": [],
                "enabled": True,
                "request_url": "https://example.com",
                "request_method": "POST",
                "request_type": "json",
                "request_data_key": "data",
                "request_headers": [],
            }
        )

        updated = await repo.update(created.id, {"name": "Updated Name", "enabled": False})

        assert updated.name == "Updated Name", "Should update name"
        assert updated.enabled is False, "Should update enabled flag"

    @pytest.mark.asyncio
    async def test_delete_notification(self, repo):
        """Delete existing notification."""
        created = await repo.create(
            {
                "name": "Delete Test",
                "on": [],
                "presets": [],
                "enabled": True,
                "request_url": "https://example.com",
                "request_method": "POST",
                "request_type": "json",
                "request_data_key": "data",
                "request_headers": [],
            }
        )

        deleted = await repo.delete(created.id)

        assert deleted.id == created.id, "Should return deleted notification"
        assert await repo.get(created.id) is None, "Deleted notification should not be retrievable"

    @pytest.mark.asyncio
    async def test_list_paginated(self, repo):
        """List paginated returns correct subset."""
        for i in range(4):
            await repo.create(
                {
                    "name": f"Item {i}",
                    "on": [],
                    "presets": [],
                    "enabled": True,
                    "request_url": "https://example.com",
                    "request_method": "POST",
                    "request_type": "json",
                    "request_data_key": "data",
                    "request_headers": [],
                }
            )

        items, total, page, total_pages = await repo.list_paginated(page=1, per_page=2)

        assert len(items) == 2, "Should return 2 items per page"
        assert total == 4, "Should report total count of 4"
        assert page == 1, "Should be on page 1"
        assert total_pages == 2, "Should have 2 pages total"
