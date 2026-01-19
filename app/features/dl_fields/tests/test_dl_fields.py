"""Tests for dl_fields feature service."""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.features.dl_fields.repository import DLFieldsRepository
from app.features.dl_fields.service import DLFields
from app.library.sqlite_store import SqliteStore


@pytest_asyncio.fixture
async def repo(tmp_path):
    """Provide a fresh repository instance with initialized database for each test."""
    DLFieldsRepository._reset_singleton()
    DLFields._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=":memory:")
    await store.get_connection()

    repository = DLFieldsRepository.get_instance()

    yield repository

    if store._conn:
        await store._conn.close()
    if store._engine:
        await store._engine.dispose()

    DLFieldsRepository._reset_singleton()
    DLFields._reset_singleton()
    SqliteStore._reset_singleton()


class TestDLFieldsService:
    """Test suite for DLFields service methods."""

    @pytest.mark.asyncio
    async def test_save_creates_field(self, repo):
        """Save should create a new dl field when ID is missing."""
        service = DLFields.get_instance()
        payload = {
            "name": "quality",
            "description": "Video quality",
            "field": "--format",
            "kind": "string",
            "order": 1,
            "extras": {"options": ["best", "worst"]},
        }

        model = await service.save(payload)

        assert model.id is not None, "Should create new dl field"
        assert model.name == "quality", "Should store name correctly"

    @pytest.mark.asyncio
    async def test_get_all_serialized(self, repo):
        """Get all serialized returns list of dictionaries."""
        service = DLFields.get_instance()
        await service.save(
            {
                "name": "audio_only",
                "description": "Audio",
                "field": "--extract-audio",
                "kind": "bool",
                "order": 2,
            }
        )

        items = await service.get_all_serialized()

        assert len(items) == 1, "Should return one dl field"
        assert items[0]["name"] == "audio_only", "Should serialize name"
        assert isinstance(items[0]["id"], int), "Should serialize integer ID"
