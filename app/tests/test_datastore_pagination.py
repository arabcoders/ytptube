import json
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from app.library.DataStore import DataStore, StoreType
from app.library.Download import Download
from app.library.ItemDTO import ItemDTO
from app.library.sqlite_store import SqliteStore


async def make_db(data: int = 100) -> SqliteStore:
    """Create a temporary database with test data."""
    SqliteStore._reset_singleton()
    ins = SqliteStore.get_instance(db_path=":memory:")
    await ins._ensure_conn()

    base_time = datetime.now(UTC)
    for i in range(data):
        created_at = base_time.replace(hour=(i // 4) % 24, minute=(i * 15) % 60, second=i % 60).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        item_data = {
            "url": f"https://example.com/video{i}",
            "title": f"Test Video {i}",
            "id": f"video{i}",
            "folder": "/downloads",
            "status": "finished",
        }

        await ins._conn.execute(
            'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (?, ?, ?, ?, ?)',
            (
                f"test-id-{i}",
                str(StoreType.HISTORY),
                item_data["url"],
                json.dumps(item_data),
                created_at,
            ),
        )
    if data > 0:
        await ins._conn.commit()

    return ins


@pytest.mark.asyncio
class TestDataStorePagination:
    """Test pagination functionality of DataStore."""

    @pytest_asyncio.fixture
    async def make_db(self, data: int = 100):
        """Fixture to provide a temporary database with test data."""
        return await make_db(data=data)

    async def test_get_total_count(self):
        """Test getting total count of items."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            count = await datastore.get_total_count()
            assert count == 100
        finally:
            await db.close()

    async def test_pagination_basic(self):
        """Test basic pagination functionality."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            items, total, page, total_pages = await datastore.get_items_paginated(page=1, per_page=10)
            assert len(items) == 10
            assert total == 100
            assert page == 1
            assert total_pages == 10
            for _, item in items:
                assert isinstance(item, Download)
                assert isinstance(item.info, ItemDTO)
                assert item.info._id.startswith("test-id-")
        finally:
            await db.close()

    async def test_pagination_last_page(self):
        """Test pagination on last page."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            items, total, page, total_pages = await datastore.get_items_paginated(page=10, per_page=10)
            assert len(items) == 10
            assert total == 100
            assert page == 10
            assert total_pages == 10
        finally:
            await db.close()

    async def test_pagination_partial_page(self):
        """Test pagination with partial last page."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            items, total, page, total_pages = await datastore.get_items_paginated(page=4, per_page=30)
            assert len(items) == 10  # 100 items / 30 per page = 3 full pages + 10 items
            assert total == 100
            assert page == 4
            assert total_pages == 4
        finally:
            await db.close()

    async def test_pagination_out_of_range(self):
        """Test pagination with page number out of range."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            items, total, page, total_pages = await datastore.get_items_paginated(page=999, per_page=10)
            assert len(items) == 10
            assert total == 100
            assert page == 10  # Adjusted to last page
            assert total_pages == 10
        finally:
            await db.close()

    async def test_pagination_order_desc(self):
        """Test pagination with descending order (newest first)."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            items, _, _, _ = await datastore.get_items_paginated(page=1, per_page=5, order="DESC")
            assert len(items) == 5
        finally:
            await db.close()

    async def test_pagination_order_asc(self):
        """Test pagination with ascending order (oldest first)."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            items, _, _, _ = await datastore.get_items_paginated(page=1, per_page=5, order="ASC")
            assert len(items) == 5
        finally:
            await db.close()

    async def test_pagination_invalid_page(self):
        """Test pagination with invalid page number."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            with pytest.raises(ValueError, match="page must be >= 1"):
                await datastore.get_items_paginated(page=0, per_page=10)

            with pytest.raises(ValueError, match="page must be >= 1"):
                await datastore.get_items_paginated(page=-1, per_page=10)
        finally:
            await db.close()

    async def test_pagination_invalid_per_page(self):
        """Test pagination with invalid per_page value."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)

            with pytest.raises(ValueError, match="per_page must be >= 1"):
                await datastore.get_items_paginated(page=1, per_page=0)

            with pytest.raises(ValueError, match="per_page must be >= 1"):
                await datastore.get_items_paginated(page=1, per_page=-10)
        finally:
            await db.close()

    async def test_pagination_invalid_order(self):
        """Test pagination with invalid order parameter."""
        db = await make_db(data=100)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            with pytest.raises(ValueError, match="order must be 'ASC' or 'DESC'"):
                await datastore.get_items_paginated(page=1, per_page=10, order="INVALID")
        finally:
            await db.close()

    async def test_pagination_empty_store(self):
        """Test pagination with empty datastore."""
        db = await make_db(data=0)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            items, total, page, total_pages = await datastore.get_items_paginated(page=1, per_page=10)

            assert len(items) == 0
            assert total == 0
            assert page == 1
            assert total_pages == 1
        finally:
            await db.close()

    async def test_pagination_single_item(self):
        """Test pagination with single item."""
        db = await make_db(data=1)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)
            items, total, page, total_pages = await datastore.get_items_paginated(page=1, per_page=10)

            assert len(items) == 1
            assert total == 1
            assert page == 1
            assert total_pages == 1
        finally:
            await db.close()

    async def test_pagination_status_filter_include(self):
        """Test pagination with status filter (inclusion)."""
        # Add some items with different status values
        item_data_pending = {
            "url": "https://example.com/pending",
            "title": "Pending Video",
            "id": "pending-video",
            "folder": "/downloads",
            "status": "pending",
        }
        item_data_downloading = {
            "url": "https://example.com/downloading",
            "title": "Downloading Video",
            "id": "downloading-video",
            "folder": "/downloads",
            "status": "downloading",
        }

        db = await make_db(data=100)
        try:
            await db._conn.execute(
                'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (?, ?, ?, ?, ?)',
                (
                    "pending-id",
                    str(StoreType.HISTORY),
                    item_data_pending["url"],
                    json.dumps(item_data_pending),
                    datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            await db._conn.execute(
                'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (?, ?, ?, ?, ?)',
                (
                    "downloading-id",
                    str(StoreType.HISTORY),
                    item_data_downloading["url"],
                    json.dumps(item_data_downloading),
                    datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            await db._conn.commit()
            datastore = DataStore(type=StoreType.HISTORY, connection=db)

            # Filter for finished items only
            items, total, _, __ = await datastore.get_items_paginated(page=1, per_page=50, status_filter="finished")

            assert len(items) == 50  # First page of finished items
            assert total == 100  # Only 100 finished items in fixture
            for _item_id, item in items:
                assert item.info.status == "finished"

            # Filter for pending items only
            items, total, _page, _total_pages = await datastore.get_items_paginated(
                page=1, per_page=50, status_filter="pending"
            )

            assert len(items) == 1
            assert total == 1
            assert items[0][1].info.status == "pending"
        finally:
            await db.close()

    async def test_pagination_status_filter_exclude(self):
        """Test pagination with status filter (exclusion)."""
        # Add some items with different status values
        item_data_pending = {
            "url": "https://example.com/pending2",
            "title": "Pending Video 2",
            "id": "pending-video-2",
            "folder": "/downloads",
            "status": "pending",
        }
        item_data_error = {
            "url": "https://example.com/error",
            "title": "Error Video",
            "id": "error-video",
            "folder": "/downloads",
            "status": "error",
        }
        db = await make_db(data=0)
        try:
            await db._conn.execute(
                'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (?, ?, ?, ?, ?)',
                (
                    "pending-id-2",
                    str(StoreType.HISTORY),
                    item_data_pending["url"],
                    json.dumps(item_data_pending),
                    datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            await db._conn.execute(
                'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (?, ?, ?, ?, ?)',
                (
                    "error-id",
                    str(StoreType.HISTORY),
                    item_data_error["url"],
                    json.dumps(item_data_error),
                    datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            await db._conn.commit()

            datastore = DataStore(type=StoreType.HISTORY, connection=db)

            # Exclude finished items
            items, total, _page, _total_pages = await datastore.get_items_paginated(
                page=1, per_page=50, status_filter="!finished"
            )

            assert total == 2  # Only 2 non-finished items
            assert len(items) == 2
            for _item_id, item in items:
                assert item.info.status != "finished"

            # Verify we have pending and error
            statuses = {item.info.status for _, item in items}
            assert statuses == {"pending", "error"}
        finally:
            await db.close()

    async def test_pagination_status_filter_none_matching(self):
        """Test pagination with status filter that matches no items."""
        db = await make_db(data=0)
        try:
            datastore = DataStore(type=StoreType.HISTORY, connection=db)

            # Filter for a status that doesn't exist
            items, total, page, total_pages = await datastore.get_items_paginated(
                page=1, per_page=50, status_filter="nonexistent"
            )

            assert len(items) == 0
            assert total == 0
            assert page == 1
            assert total_pages == 1
        finally:
            await db.close()
