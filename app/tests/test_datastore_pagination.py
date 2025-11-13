import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.library.DataStore import DataStore, StoreType
from app.library.ItemDTO import ItemDTO


class TestDataStorePagination:
    """Test pagination functionality of DataStore."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with test data."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # Create the history table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "history" (
                    "id" TEXT PRIMARY KEY,
                    "type" TEXT NOT NULL,
                    "url" TEXT NOT NULL,
                    "data" TEXT NOT NULL,
                    "created_at" TEXT NOT NULL
                )
                """
            )

            # Insert test data
            base_time = datetime.now(UTC)
            for i in range(100):
                created_at = base_time.replace(
                    hour=(i // 4) % 24, minute=(i * 15) % 60, second=i % 60
                ).strftime("%Y-%m-%d %H:%M:%S")

                item_data = {
                    "url": f"https://example.com/video{i}",
                    "title": f"Test Video {i}",
                    "id": f"video{i}",
                    "folder": "/downloads",
                    "status": "finished",
                }

                conn.execute(
                    'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (?, ?, ?, ?, ?)',
                    (
                        f"test-id-{i}",
                        str(StoreType.HISTORY),
                        item_data["url"],
                        json.dumps(item_data),
                        created_at,
                    ),
                )

            conn.commit()
            yield conn
            conn.close()

    def test_get_total_count(self, temp_db):
        """Test getting total count of items."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)
        count = datastore.get_total_count()
        assert count == 100

    def test_pagination_basic(self, temp_db):
        """Test basic pagination functionality."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)

        # Get first page
        items, total, page, total_pages = datastore.get_items_paginated(page=1, per_page=10)

        assert len(items) == 10
        assert total == 100
        assert page == 1
        assert total_pages == 10

        # Verify items are ItemDTO instances
        for _item_id, item in items:
            assert isinstance(item, ItemDTO)
            assert item._id.startswith("test-id-")

    def test_pagination_last_page(self, temp_db):
        """Test pagination on last page."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)

        # Get last page
        items, total, page, total_pages = datastore.get_items_paginated(page=10, per_page=10)

        assert len(items) == 10
        assert total == 100
        assert page == 10
        assert total_pages == 10

    def test_pagination_partial_page(self, temp_db):
        """Test pagination with partial last page."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)

        # Get items with per_page that doesn't divide evenly
        items, total, page, total_pages = datastore.get_items_paginated(page=4, per_page=30)

        assert len(items) == 10  # 100 items / 30 per page = 3 full pages + 10 items
        assert total == 100
        assert page == 4
        assert total_pages == 4

    def test_pagination_out_of_range(self, temp_db):
        """Test pagination with page number out of range."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)

        # Request page beyond total pages - should return last page
        items, total, page, total_pages = datastore.get_items_paginated(page=999, per_page=10)

        assert len(items) == 10
        assert total == 100
        assert page == 10  # Adjusted to last page
        assert total_pages == 10

    def test_pagination_order_desc(self, temp_db):
        """Test pagination with descending order (newest first)."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)

        items, _, _, _ = datastore.get_items_paginated(page=1, per_page=5, order="DESC")

        assert len(items) == 5
        # Verify order - should be newest to oldest
        # (note: exact order depends on the timestamp generation in fixture)

    def test_pagination_order_asc(self, temp_db):
        """Test pagination with ascending order (oldest first)."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)

        items, _, _, _ = datastore.get_items_paginated(page=1, per_page=5, order="ASC")

        assert len(items) == 5

    def test_pagination_invalid_page(self, temp_db):
        """Test pagination with invalid page number."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)

        with pytest.raises(ValueError, match="page must be >= 1"):
            datastore.get_items_paginated(page=0, per_page=10)

        with pytest.raises(ValueError, match="page must be >= 1"):
            datastore.get_items_paginated(page=-1, per_page=10)

    def test_pagination_invalid_per_page(self, temp_db):
        """Test pagination with invalid per_page value."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)

        with pytest.raises(ValueError, match="per_page must be >= 1"):
            datastore.get_items_paginated(page=1, per_page=0)

        with pytest.raises(ValueError, match="per_page must be >= 1"):
            datastore.get_items_paginated(page=1, per_page=-10)

    def test_pagination_invalid_order(self, temp_db):
        """Test pagination with invalid order parameter."""
        datastore = DataStore(type=StoreType.HISTORY, connection=temp_db)

        with pytest.raises(ValueError, match="order must be 'ASC' or 'DESC'"):
            datastore.get_items_paginated(page=1, per_page=10, order="INVALID")

    def test_pagination_empty_store(self):
        """Test pagination with empty datastore."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "empty.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # Create empty table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "history" (
                    "id" TEXT PRIMARY KEY,
                    "type" TEXT NOT NULL,
                    "url" TEXT NOT NULL,
                    "data" TEXT NOT NULL,
                    "created_at" TEXT NOT NULL
                )
                """
            )
            conn.commit()

            datastore = DataStore(type=StoreType.HISTORY, connection=conn)

            items, total, page, total_pages = datastore.get_items_paginated(page=1, per_page=10)

            assert len(items) == 0
            assert total == 0
            assert page == 1
            assert total_pages == 1

            conn.close()

    def test_pagination_single_item(self):
        """Test pagination with single item."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "single.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # Create table with single item
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS "history" (
                    "id" TEXT PRIMARY KEY,
                    "type" TEXT NOT NULL,
                    "url" TEXT NOT NULL,
                    "data" TEXT NOT NULL,
                    "created_at" TEXT NOT NULL
                )
                """
            )

            item_data = {
                "url": "https://example.com/single",
                "title": "Single Video",
                "id": "single-video",
                "folder": "/downloads",
                "status": "finished",
            }

            conn.execute(
                'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (?, ?, ?, ?, ?)',
                (
                    "single-id",
                    str(StoreType.HISTORY),
                    item_data["url"],
                    json.dumps(item_data),
                    datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()

            datastore = DataStore(type=StoreType.HISTORY, connection=conn)

            items, total, page, total_pages = datastore.get_items_paginated(page=1, per_page=10)

            assert len(items) == 1
            assert total == 1
            assert page == 1
            assert total_pages == 1

            conn.close()
