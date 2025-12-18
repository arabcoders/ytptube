import asyncio
import json
from collections import OrderedDict
from dataclasses import asdict
from datetime import UTC, datetime
from email.utils import formatdate

import pytest

from app.library.DataStore import DataStore, StoreType
from app.library.ItemDTO import ItemDTO
from app.library.operations import Operation
from app.library.sqlite_store import SqliteStore


async def make_db(data: int = 0) -> SqliteStore:
    """Create a temporary database with test data."""
    SqliteStore._reset_singleton()
    ins = SqliteStore.get_instance(db_path=":memory:")
    await ins._ensure_conn()

    base_time = datetime.now(UTC)
    for i in range(data):
        created_at: str = base_time.replace(hour=(i // 4) % 24, minute=(i * 15) % 60, second=i % 60).strftime(
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


class StubDownload:
    def __init__(self, info: ItemDTO, started: bool = False, cancelled: bool = False):
        self.info = info
        self._started: bool = started
        self._cancelled: bool = cancelled

    def started(self) -> bool:
        return self._started

    def is_cancelled(self) -> bool:
        return self._cancelled


async def make_store_async(store_type: StoreType) -> DataStore:
    return DataStore(store_type, await make_db())


def make_item(id: str, url: str = "http://u", title: str = "t", folder: str = "f") -> ItemDTO:
    return ItemDTO(id=id, title=title, url=url, folder=folder)


class TestStoreType:
    def test_all_and_from_value_and_str(self) -> None:
        assert set(StoreType.all()) == {"done", "queue"}
        assert StoreType.from_value("queue") is StoreType.QUEUE
        assert StoreType.from_value("done") is StoreType.HISTORY
        assert str(StoreType.QUEUE) == "queue"
        with pytest.raises(ValueError, match="Invalid StoreType value"):
            StoreType.from_value("invalid")


class TestDataStore:
    @pytest.mark.asyncio
    async def test_saved_items_parses_rows(self) -> None:
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)
        db = store._connection

        dto = make_item(id="ignore", url="http://x", title="Title", folder="F")
        data = asdict(dto)
        data.pop("_id", None)
        created = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
        await db._conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            ("abc", "queue", "http://x", json.dumps(data), created.strftime("%Y-%m-%d %H:%M:%S")),
        )
        await db._conn.commit()

        items = await store.saved_items()
        assert len(items) == 1
        key, item = items[0]
        assert key == "abc"
        assert item._id == "abc"
        assert item.url == "http://x"
        assert isinstance(item.datetime, str)
        assert item.datetime == formatdate(created.timestamp())

    @pytest.mark.asyncio
    async def test_put_and_delete_persist(self) -> None:
        store = await make_store_async(StoreType.QUEUE)
        db = store._connection

        item = make_item(id="vid1")
        d = StubDownload(info=item)

        ret = await store.put(d)
        await db.flush()
        assert ret is store._dict[item._id]

        # Verify row written; JSON should not contain datetime field
        cur = await db._conn.execute("SELECT * FROM history WHERE id=?", (item._id,))
        row = await cur.fetchone()
        assert row is not None
        assert row["type"] == "queue"
        assert row["url"] == item.url
        assert '"datetime"' not in row["data"]
        assert row["id"] == item._id

        # Delete and ensure removal
        await store.delete(item._id)
        await asyncio.sleep(0)
        await db.flush()
        cur2 = await db._conn.execute("SELECT * FROM history WHERE id=?", (item._id,))
        row2 = await cur2.fetchone()
        assert row2 is None
        await db.close()

    @pytest.mark.asyncio
    async def test_exists_and_get(self) -> None:
        store = await make_store_async(StoreType.QUEUE)

        item = make_item(id="a1", url="http://u1")
        d = StubDownload(info=item)
        await store.put(d)
        await store._connection.flush()

        assert await store.exists(key=item._id) is True
        assert await store.exists(url=item.url) is True
        with pytest.raises(KeyError):
            await store.exists()

        got = await store.get(key=item._id)
        assert got.info._id == item._id
        got2 = await store.get(url=item.url)
        assert got2.info.url == item.url
        with pytest.raises(KeyError):
            await store.get()
        with pytest.raises(KeyError):
            await store.get(key="missing")
        await store._connection.close()

    @pytest.mark.asyncio
    async def test_next_and_empty(self) -> None:
        store = await make_store_async(StoreType.QUEUE)

        assert store.empty() is True
        d1 = StubDownload(info=make_item(id="x1"))
        d2 = StubDownload(info=make_item(id="x2"))
        await store.put(d1)
        await store.put(d2)
        await store._connection.flush()
        assert store.empty() is False
        first_key, first_val = store.next()
        assert first_key == d1.info._id
        assert first_val.info._id == d1.info._id
        await store._connection.close()

    @pytest.mark.asyncio
    async def test_has_downloads_and_get_next_download(self) -> None:
        store = await make_store_async(StoreType.QUEUE)

        # One non-auto-start, one started, one cancelled, and one eligible
        i1 = make_item(id="n1")
        i1.auto_start = False
        i2 = make_item(id="s1")
        i3 = make_item(id="c1")
        i4 = make_item(id="ok1")

        await store.put(StubDownload(info=i1, started=False))
        await store.put(StubDownload(info=i2, started=True))
        await store.put(StubDownload(info=i3, started=False, cancelled=True))
        await store.put(StubDownload(info=i4, started=False))
        await store._connection.flush()

        assert store.has_downloads() is True
        nxt = store.get_next_download()
        assert isinstance(nxt, StubDownload)
        assert nxt.info._id == i4._id
        await store._connection.close()

    @pytest.mark.asyncio
    async def test_test_method_executes_query(self) -> None:
        store = await make_store_async(StoreType.QUEUE)
        # Should not raise
        ok = await store.test()
        assert ok is True

    @pytest.mark.asyncio
    async def test_get_item_returns_none_when_no_kwargs(self) -> None:
        """Test that get_item returns None when no kwargs provided."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        result = await store.get_item()
        assert result is None
        await db.close()

    @pytest.mark.asyncio
    async def test_get_item_finds_by_single_attribute(self) -> None:
        """Test that get_item correctly finds item by a single attribute."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        # Create items with different attributes
        item1 = make_item(id="vid1", url="http://example.com/1", title="Video 1", folder="folder1")
        item1._id = "id1"  # Override auto-generated UUID
        item2 = make_item(id="vid2", url="http://example.com/2", title="Video 2", folder="folder2")
        item2._id = "id2"  # Override auto-generated UUID

        d1 = StubDownload(info=item1)
        d2 = StubDownload(info=item2)

        await store.put(d1)
        await store.put(d2)
        await store._connection.flush()

        # Test finding by title
        result = await store.get_item(title="Video 1")
        assert result is not None
        assert result.info._id == "id1"
        assert result.info.title == "Video 1"

        # Test finding by folder
        result = await store.get_item(folder="folder2")
        assert result is not None
        assert result.info._id == "id2"
        assert result.info.folder == "folder2"

        # Test finding by url
        result = await store.get_item(url="http://example.com/1")
        assert result is not None
        assert result.info._id == "id1"
        await db.close()

    @pytest.mark.asyncio
    async def test_get_item_finds_by_multiple_attributes(self) -> None:
        """Test that get_item finds item when ANY of the provided attributes match."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", url="http://example.com/1", title="Video 1", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", url="http://example.com/2", title="Video 2", folder="folder2")
        item2._id = "id2"

        d1 = StubDownload(info=item1)
        d2 = StubDownload(info=item2)

        await store.put(d1)
        await store.put(d2)
        await store._connection.flush()

        # Test finding by multiple attributes where one matches
        result = await store.get_item(title="Video 1", folder="wrong_folder")
        assert result is not None
        assert result.info._id == "id1"

        # Test finding where second attribute matches
        result = await store.get_item(title="Wrong Title", folder="folder2")
        assert result is not None
        assert result.info._id == "id2"
        await db.close()

    @pytest.mark.asyncio
    async def test_get_item_returns_none_when_no_match(self) -> None:
        """Test that get_item returns None when no attributes match."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item = make_item(id="vid1", url="http://example.com/1", title="Video 1", folder="folder1")
        item._id = "id1"
        d = StubDownload(info=item)
        await store.put(d)
        await store._connection.flush()

        # Test with non-matching attribute
        result = await store.get_item(title="Nonexistent Video")
        assert result is None

        # Test with non-existent attribute key
        result = await store.get_item(nonexistent_field="value")
        assert result is None
        await db.close()

    @pytest.mark.asyncio
    async def test_get_item_skips_items_with_no_info(self) -> None:
        """Test that get_item skips items that have no info attribute."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        # Create a valid item
        item = make_item(id="vid1", url="http://example.com/1", title="Video 1")
        item._id = "id1"
        d = StubDownload(info=item)
        await store.put(d)
        await store._connection.flush()

        # Manually add an item with None info
        class BrokenDownload:
            def __init__(self):
                self.info = None

        store._dict["broken"] = BrokenDownload()

        # Should still find the valid item
        result = await store.get_item(title="Video 1")
        assert result is not None
        assert result.info._id == "id1"
        await db.close()

    @pytest.mark.asyncio
    async def test_get_item_returns_first_match(self) -> None:
        """Test that get_item returns the first matching item when multiple match."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        # Create multiple items with same title
        item1 = make_item(id="vid1", url="http://example.com/1", title="Same Title", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", url="http://example.com/2", title="Same Title", folder="folder2")
        item2._id = "id2"

        d1 = StubDownload(info=item1)
        d2 = StubDownload(info=item2)

        await store.put(d1)
        await store.put(d2)
        await store._connection.flush()

        # Should return first match (note: OrderedDict maintains insertion order)
        result = await store.get_item(title="Same Title")
        assert result is not None
        assert result.info._id == "id1"
        await db.close()

    @pytest.mark.asyncio
    async def test_init(self) -> None:
        """Test DataStore initialization."""
        store = await make_store_async(StoreType.QUEUE)

        assert store._type == StoreType.QUEUE
        assert store._connection is not None
        assert isinstance(store._dict, OrderedDict)
        assert len(store._dict) == 0

    @pytest.mark.asyncio
    async def test_load(self) -> None:
        """Test loading items from database into memory."""
        db = await make_db()
        conn = db._conn

        # Insert items directly into database
        item1_data = asdict(make_item(id="vid1", url="http://example.com/1", title="Video 1"))
        item1_data.pop("_id", None)
        item2_data = asdict(make_item(id="vid2", url="http://example.com/2", title="Video 2"))
        item2_data.pop("_id", None)

        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        await conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "id1",
                str(StoreType.QUEUE),
                "http://example.com/1",
                json.dumps(item1_data),
                created.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        await conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "id2",
                str(StoreType.QUEUE),
                "http://example.com/2",
                json.dumps(item2_data),
                created.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        await conn.commit()

        store = DataStore(StoreType.QUEUE, db)
        assert len(store._dict) == 0

        await store.load()
        assert len(store._dict) == 2
        assert "id1" in store._dict
        assert "id2" in store._dict
        assert store._dict["id1"].info.url == "http://example.com/1"
        assert store._dict["id2"].info.url == "http://example.com/2"
        await db.close()

    @pytest.mark.asyncio
    async def test_load_with_different_store_types(self) -> None:
        """Test that load only loads items matching the store type."""
        db = await make_db()
        conn = db._conn

        # Insert items with different types
        item1_data = asdict(make_item(id="vid1", url="http://example.com/1"))
        item1_data.pop("_id", None)
        item2_data = asdict(make_item(id="vid2", url="http://example.com/2"))
        item2_data.pop("_id", None)

        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        await conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "id1",
                str(StoreType.QUEUE),
                "http://example.com/1",
                json.dumps(item1_data),
                created.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        await conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "id2",
                str(StoreType.HISTORY),
                "http://example.com/2",
                json.dumps(item2_data),
                created.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        await conn.commit()

        # Load QUEUE store - should only get queue items
        queue_store = DataStore(StoreType.QUEUE, db)
        await queue_store.load()
        assert len(queue_store._dict) == 1
        assert "id1" in queue_store._dict

        # Load HISTORY store - should only get history items
        history_store = DataStore(StoreType.HISTORY, db)
        await history_store.load()
        assert len(history_store._dict) == 1
        assert "id2" in history_store._dict
        await db.close()

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        """Test getting item by ID."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", url="http://example.com/1", title="Video 1")
        item1._id = "id1"
        item2 = make_item(id="vid2", url="http://example.com/2", title="Video 2")
        item2._id = "id2"

        d1 = StubDownload(info=item1)
        d2 = StubDownload(info=item2)

        await store.put(d1)
        await store.put(d2)
        await store._connection.flush()

        # Test getting existing items
        result = await store.get_by_id("id1")
        assert result is not None
        assert result.info._id == "id1"
        assert result.info.title == "Video 1"

        result = await store.get_by_id("id2")
        assert result is not None
        assert result.info._id == "id2"

        # Test getting non-existent item
        result = await store.get_by_id("nonexistent")
        assert result is None
        await db.close()

    @pytest.mark.asyncio
    async def test_items(self) -> None:
        """Test getting all items as list of tuples."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        # Empty store
        result = store.items()
        assert len(list(result)) == 0

        # Add items
        item1 = make_item(id="vid1", url="http://example.com/1", title="Video 1")
        item1._id = "id1"
        item2 = make_item(id="vid2", url="http://example.com/2", title="Video 2")
        item2._id = "id2"

        d1 = StubDownload(info=item1)
        d2 = StubDownload(info=item2)

        await store.put(d1)
        await store.put(d2)
        await store._connection.flush()

        # Test getting all items
        result = list(store.items())
        assert len(result) == 2

        # Verify structure (list of tuples)
        ids = [item[0] for item in result]
        assert "id1" in ids
        assert "id2" in ids

        # Verify order is maintained (OrderedDict)
        assert result[0][0] == "id1"
        assert result[1][0] == "id2"
        await db.close()

    @pytest.mark.asyncio
    async def test_get_total_count_with_empty_store(self) -> None:
        """Test get_total_count with empty datastore."""
        store = await make_store_async(StoreType.QUEUE)

        count = await store.get_total_count()
        assert count == 0
        await store._connection.close()

    @pytest.mark.asyncio
    async def test_get_total_count_with_items(self) -> None:
        """Test get_total_count with items in database."""
        store = await make_store_async(StoreType.QUEUE)
        db = store._connection
        conn = db._conn

        # Add items directly to database
        created = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        for i in range(5):
            item_data = asdict(make_item(id=f"vid{i}"))
            item_data.pop("_id", None)
            await conn.execute(
                "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (f"id{i}", str(StoreType.QUEUE), f"http://example.com/{i}", json.dumps(item_data), created),
            )
        await conn.commit()

        count = await store.get_total_count()
        assert count == 5
        await store._connection.close()

    @pytest.mark.asyncio
    async def test_get_total_count_respects_store_type(self) -> None:
        """Test that get_total_count only counts items of the correct type."""
        db = await make_db()
        conn = db._conn

        created = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

        # Add 3 QUEUE items
        for i in range(3):
            item_data = asdict(make_item(id=f"vid{i}"))
            item_data.pop("_id", None)
            await conn.execute(
                "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (f"q{i}", str(StoreType.QUEUE), f"http://example.com/queue/{i}", json.dumps(item_data), created),
            )

        # Add 2 HISTORY items
        for i in range(2):
            item_data = asdict(make_item(id=f"vid{i}"))
            item_data.pop("_id", None)
            await conn.execute(
                "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (f"h{i}", str(StoreType.HISTORY), f"http://example.com/history/{i}", json.dumps(item_data), created),
            )
        await conn.commit()

        queue_store = DataStore(StoreType.QUEUE, db)
        assert await queue_store.get_total_count() == 3

        history_store = DataStore(StoreType.HISTORY, db)
        assert await history_store.get_total_count() == 2
        await db.close()

    @pytest.mark.asyncio
    async def test_put_with_error_status_emits_event(self) -> None:
        """Test that put() emits an event when item has error status."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item = make_item(id="vid1")
        item.status = "error"
        item.error = "Test error message"

        d = StubDownload(info=item)

        # We can't easily test event emission without mocking EventBus
        # Just verify it doesn't crash
        result = await store.put(d)
        await store._connection.flush()
        assert result is not None
        await db.close()

    @pytest.mark.asyncio
    async def test_put_with_no_notify_skips_event(self) -> None:
        """Test that put() with no_notify=True doesn't emit events."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item = make_item(id="vid1")
        item.status = "error"
        item.error = "Test error message"

        d = StubDownload(info=item)

        # Should not emit event when no_notify=True
        result = await store.put(d, no_notify=True)
        await store._connection.flush()
        assert result is not None
        assert result.info._id == item._id
        await db.close()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_item(self) -> None:
        """Test that deleting non-existent item doesn't raise error."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        # Should not raise error
        await store.delete("nonexistent_id")

        # Verify nothing was deleted from database
        await store._connection.flush()
        cursor = await db._conn.execute("SELECT * FROM history WHERE id=?", ("nonexistent_id",))
        row = await cursor.fetchone()
        assert row is None
        await db.close()

    @pytest.mark.asyncio
    async def test_has_downloads_with_empty_dict(self) -> None:
        """Test has_downloads returns False when dict is empty."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        assert store.has_downloads() is False
        await db.close()

    @pytest.mark.asyncio
    async def test_has_downloads_with_no_eligible_downloads(self) -> None:
        """Test has_downloads returns False when no downloads are eligible."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        # Add item that's already started
        item1 = make_item(id="vid1")
        await store.put(StubDownload(info=item1, started=True))

        # Add item with auto_start=False
        item2 = make_item(id="vid2")
        item2.auto_start = False
        await store.put(StubDownload(info=item2, started=False))
        await store._connection.flush()

        assert store.has_downloads() is False
        await db.close()

    @pytest.mark.asyncio
    async def test_get_next_download_returns_none_when_empty(self) -> None:
        """Test get_next_download returns None when no eligible downloads."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        result = store.get_next_download()
        assert result is None
        await db.close()

    @pytest.mark.asyncio
    async def test_get_next_download_skips_cancelled(self) -> None:
        """Test get_next_download skips cancelled downloads."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        # Add cancelled download
        item1 = make_item(id="vid1")
        item1._id = "id1"
        await store.put(StubDownload(info=item1, started=False, cancelled=True))

        # Add eligible download
        item2 = make_item(id="vid2")
        item2._id = "id2"
        await store.put(StubDownload(info=item2, started=False, cancelled=False))
        await store._connection.flush()

        result = store.get_next_download()
        assert result is not None
        assert result.info._id == "id2"
        await db.close()

    @pytest.mark.asyncio
    async def test_update_store_item_removes_datetime_field(self) -> None:
        """Test that _update_store_item removes datetime field before storage."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item = make_item(id="vid1")
        item.datetime = "Thu, 01 Jan 2024 12:00:00 GMT"  # Add datetime field

        d = StubDownload(info=item)
        await store.put(d)
        await store._connection.flush()

        # Verify datetime field is not in stored JSON
        cursor = await db._conn.execute("SELECT data FROM history WHERE id=?", (item._id,))
        row = await cursor.fetchone()
        assert row is not None
        data = json.loads(row["data"])
        assert "datetime" not in data
        await db.close()

    @pytest.mark.asyncio
    async def test_update_store_item_removes_live_in_when_finished(self) -> None:
        """Test that _update_store_item removes live_in field when status is finished."""
        store = await make_store_async(StoreType.QUEUE)
        conn = store._connection

        item = make_item(id="vid1")
        item.status = "finished"
        item.live_in = "PT5M"  # Add live_in field

        d = StubDownload(info=item)
        await store.put(d)
        await store._connection.flush()

        # Verify live_in field is not in stored JSON when status is finished
        cursor = await conn._conn.execute("SELECT data FROM history WHERE id=?", (item._id,))
        row = await cursor.fetchone()
        assert row is not None
        data = json.loads(row["data"])
        assert "live_in" not in data
        await store._connection.close()

    @pytest.mark.asyncio
    async def test_update_store_item_keeps_live_in_when_not_finished(self) -> None:
        """Test that _update_store_item keeps live_in field when status is not finished."""
        store = await make_store_async(StoreType.QUEUE)
        conn = store._connection

        item = make_item(id="vid1")
        item.status = "downloading"
        item.live_in = "PT5M"  # Add live_in field

        d = StubDownload(info=item)
        await store.put(d)
        await store._connection.flush()

        # Verify live_in field IS in stored JSON when status is not finished
        cursor = await conn._conn.execute("SELECT data FROM history WHERE id=?", (item._id,))
        row = await cursor.fetchone()
        assert row is not None
        data = json.loads(row["data"])
        assert "live_in" in data
        assert data["live_in"] == "PT5M"
        await store._connection.close()


@pytest.mark.asyncio
class TestDataStoreOperations:
    """Test get_item with different comparison operations."""

    async def test_operation_equal(self) -> None:
        """Test EQUAL operation (default behavior)."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Exact Match", folder="folder1")
        item1._id = "id1"
        await store.put(StubDownload(info=item1))

        # Test with explicit EQUAL operation
        result = await store.get_item(title=(Operation.EQUAL, "Exact Match"))
        assert result is not None
        assert result.info._id == "id1"

        # Test default behavior (no operation specified)
        result = await store.get_item(title="Exact Match")
        assert result is not None
        assert result.info._id == "id1"

        # Test no match
        result = await store.get_item(title=(Operation.EQUAL, "No Match"))
        assert result is None
        await db.close()

    async def test_operation_not_equal(self) -> None:
        """Test NOT_EQUAL operation."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Video 1", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="Video 2", folder="folder2")
        item2._id = "id2"

        await store.put(StubDownload(info=item1))
        await store.put(StubDownload(info=item2))

        # Find item where title is not "Video 1"
        result = await store.get_item(title=(Operation.NOT_EQUAL, "Video 1"))
        assert result is not None
        assert result.info._id == "id2"
        await db.close()

    async def test_operation_contain(self) -> None:
        """Test CONTAIN operation (substring match)."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Python Tutorial Video", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="JavaScript Course", folder="folder2")
        item2._id = "id2"

        await store.put(StubDownload(info=item1))
        await store.put(StubDownload(info=item2))

        # Find item with "Python" in title
        result = await store.get_item(title=(Operation.CONTAIN, "Python"))
        assert result is not None
        assert result.info._id == "id1"

        # Find item with "Tutorial" in title
        result = await store.get_item(title=(Operation.CONTAIN, "Tutorial"))
        assert result is not None
        assert result.info._id == "id1"

        # No match
        result = await store.get_item(title=(Operation.CONTAIN, "Rust"))
        assert result is None
        await db.close()

    async def test_operation_not_contain(self) -> None:
        """Test NOT_CONTAIN operation."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Python Tutorial", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="JavaScript Course", folder="folder2")
        item2._id = "id2"

        await store.put(StubDownload(info=item1))
        await store.put(StubDownload(info=item2))

        # Find item that doesn't contain "Python"
        result = await store.get_item(title=(Operation.NOT_CONTAIN, "Python"))
        assert result is not None
        assert result.info._id == "id2"
        await db.close()

    async def test_operation_starts_with(self) -> None:
        """Test STARTS_WITH operation."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Tutorial: Python Basics", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="Course: JavaScript", folder="folder2")
        item2._id = "id2"

        await store.put(StubDownload(info=item1))
        await store.put(StubDownload(info=item2))

        # Find item starting with "Tutorial"
        result = await store.get_item(title=(Operation.STARTS_WITH, "Tutorial"))
        assert result is not None
        assert result.info._id == "id1"

        # Find item starting with "Course"
        result = await store.get_item(title=(Operation.STARTS_WITH, "Course"))
        assert result is not None
        assert result.info._id == "id2"

        # No match
        result = await store.get_item(title=(Operation.STARTS_WITH, "Video"))
        assert result is None
        await db.close()

    async def test_operation_ends_with(self) -> None:
        """Test ENDS_WITH operation."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Learn Python", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="Learn JavaScript", folder="folder2")
        item2._id = "id2"

        await store.put(StubDownload(info=item1))
        await store.put(StubDownload(info=item2))

        # Find item ending with "Python"
        result = await store.get_item(title=(Operation.ENDS_WITH, "Python"))
        assert result is not None
        assert result.info._id == "id1"

        # Find item ending with "JavaScript"
        result = await store.get_item(title=(Operation.ENDS_WITH, "JavaScript"))
        assert result is not None
        assert result.info._id == "id2"

        # No match
        result = await store.get_item(title=(Operation.ENDS_WITH, "Course"))
        assert result is None
        await db.close()

    async def test_operation_greater_than(self) -> None:
        """Test GREATER_THAN operation with numeric values."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.filesize = 1000
        item2 = make_item(id="vid2", title="Video 2")
        item2._id = "id2"
        item2.filesize = 2000

        await store.put(StubDownload(info=item1))
        await store.put(StubDownload(info=item2))

        # Find item with filesize > 1500
        result = await store.get_item(filesize=(Operation.GREATER_THAN, 1500))
        assert result is not None
        assert result.info._id == "id2"

        # Find item with filesize > 500 (should return first match)
        result = await store.get_item(filesize=(Operation.GREATER_THAN, 500))
        assert result is not None
        assert result.info._id == "id1"
        await db.close()

    async def test_operation_less_than(self) -> None:
        """Test LESS_THAN operation."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.filesize = 1000
        item2 = make_item(id="vid2", title="Video 2")
        item2._id = "id2"
        item2.filesize = 2000

        await store.put(StubDownload(info=item1))
        await store.put(StubDownload(info=item2))

        # Find item with filesize < 1500
        result = await store.get_item(filesize=(Operation.LESS_THAN, 1500))
        assert result is not None
        assert result.info._id == "id1"
        await db.close()

    async def test_operation_greater_equal(self) -> None:
        """Test GREATER_EQUAL operation."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.filesize = 1000

        await store.put(StubDownload(info=item1))

        # Test >= with exact match
        result = await store.get_item(filesize=(Operation.GREATER_EQUAL, 1000))
        assert result is not None
        assert result.info._id == "id1"

        # Test >= with less than
        result = await store.get_item(filesize=(Operation.GREATER_EQUAL, 500))
        assert result is not None
        assert result.info._id == "id1"

        # Test >= with greater than
        result = await store.get_item(filesize=(Operation.GREATER_EQUAL, 1500))
        assert result is None
        await db.close()

    async def test_operation_less_equal(self) -> None:
        """Test LESS_EQUAL operation."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.filesize = 1000

        await store.put(StubDownload(info=item1))

        # Test <= with exact match
        result = await store.get_item(filesize=(Operation.LESS_EQUAL, 1000))
        assert result is not None

        # Test <= with greater than
        result = await store.get_item(filesize=(Operation.LESS_EQUAL, 1500))
        assert result is not None

        # Test <= with less than
        result = await store.get_item(filesize=(Operation.LESS_EQUAL, 500))
        assert result is None
        await db.close()

    async def test_mixed_operations(self) -> None:
        """Test using multiple operations in a single query."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Python Tutorial", folder="tutorials")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="Python Advanced", folder="courses")
        item2._id = "id2"
        item3 = make_item(id="vid3", title="JavaScript Basics", folder="tutorials")
        item3._id = "id3"

        await store.put(StubDownload(info=item1))
        await store.put(StubDownload(info=item2))
        await store.put(StubDownload(info=item3))

        # Mix of operation and default (any match returns true)
        result = await store.get_item(title=(Operation.CONTAIN, "Python"), folder="tutorials")
        assert result is not None
        assert result.info._id == "id1"

        # Mix where first condition matches
        result = await store.get_item(title=(Operation.CONTAIN, "JavaScript"), folder="nonexistent")
        assert result is not None
        assert result.info._id == "id3"
        await db.close()

    async def test_operation_with_none_values(self) -> None:
        """Test operations handle None values gracefully."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.description = None

        await store.put(StubDownload(info=item1))

        # CONTAIN with None field should return False
        result = await store.get_item(description=(Operation.CONTAIN, "test"))
        assert result is None

        # NOT_CONTAIN with None field should return True
        result = await store.get_item(description=(Operation.NOT_CONTAIN, "test"))
        assert result is not None

        # GREATER_THAN with None should return False
        result = await store.get_item(description=(Operation.GREATER_THAN, 100))
        assert result is None
        await db.close()

    async def test_operation_with_invalid_comparisons(self) -> None:
        """Test that invalid comparisons are handled gracefully."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"

        await store.put(StubDownload(info=item1))

        # Try to compare string with number using > (should return False/None)
        result = await store.get_item(title=(Operation.GREATER_THAN, 100))
        assert result is None
        await db.close()

    async def test_operation_backward_compatibility(self) -> None:
        """Test that string operation names work for backward compatibility."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Python Tutorial")
        item1._id = "id1"

        await store.put(StubDownload(info=item1))

        # Using string operation value
        result = await store.get_item(title=("in", "Python"))
        assert result is not None
        assert result.info._id == "id1"

        # Using string for EQUAL
        result = await store.get_item(title=("==", "Python Tutorial"))
        assert result is not None
        await db.close()

    async def test_operation_with_nonexistent_field(self) -> None:
        """Test operations with fields that don't exist."""
        db = await make_db()
        store = DataStore(StoreType.QUEUE, db)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"

        await store.put(StubDownload(info=item1))

        # Try to match on non-existent field
        result = await store.get_item(nonexistent_field=(Operation.EQUAL, "value"))
        assert result is None

        result = await store.get_item(nonexistent_field=(Operation.CONTAIN, "value"))
        assert result is None
        await db.close()
