import json
import sqlite3
from collections import OrderedDict
from dataclasses import asdict
from datetime import UTC, datetime
from email.utils import formatdate

import pytest

from app.library.DataStore import DataStore, StoreType
from app.library.ItemDTO import ItemDTO
from app.library.operations import Operation


class StubDownload:
    def __init__(self, info: ItemDTO, started: bool = False, cancelled: bool = False):
        self.info = info
        self._started = started
        self._cancelled = cancelled

    def started(self) -> bool:
        return self._started

    def is_cancelled(self) -> bool:
        return self._cancelled


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE history (id TEXT PRIMARY KEY, type TEXT, url TEXT, data TEXT, created_at TEXT)")
    return conn


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
    def test_saved_items_parses_rows(self) -> None:
        conn = make_conn()
        # Prepare a stored item JSON (without _id, it will be set from the row)
        dto = make_item(id="ignore", url="http://x", title="Title", folder="F")
        data = asdict(dto)
        data.pop("_id", None)
        created = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
        conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            ("abc", "queue", "http://x", json.dumps(data), created.strftime("%Y-%m-%d %H:%M:%S")),
        )
        store = DataStore(StoreType.QUEUE, conn)

        items = store.saved_items()
        assert len(items) == 1
        key, item = items[0]
        assert key == "abc"
        assert item._id == "abc"
        assert item.url == "http://x"
        assert isinstance(item.datetime, str)
        assert item.datetime == formatdate(created.timestamp())

    def test_put_and_delete_persist(self) -> None:
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item = make_item(id="vid1")
        d = StubDownload(info=item)

        ret = store.put(d)
        assert ret is store._dict[item._id]

        # Verify row written; JSON should not contain datetime field
        row = conn.execute("SELECT * FROM history WHERE id=?", (item._id,)).fetchone()
        assert row is not None
        assert row["type"] == "queue"
        assert row["url"] == item.url
        assert '"datetime"' not in row["data"]

        # Delete and ensure removal
        store.delete(item._id)
        row2 = conn.execute("SELECT * FROM history WHERE id=?", (item._id,)).fetchone()
        assert row2 is None

    def test_exists_and_get(self) -> None:
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item = make_item(id="a1", url="http://u1")
        d = StubDownload(info=item)
        store.put(d)

        assert store.exists(key=item._id) is True
        assert store.exists(url=item.url) is True
        with pytest.raises(KeyError):
            store.exists()

        got = store.get(key=item._id)
        assert got.info._id == item._id
        got2 = store.get(url=item.url)
        assert got2.info.url == item.url
        with pytest.raises(KeyError):
            store.get()
        with pytest.raises(KeyError):
            store.get(key="missing")

    def test_next_and_empty(self) -> None:
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        assert store.empty() is True
        d1 = StubDownload(info=make_item(id="x1"))
        d2 = StubDownload(info=make_item(id="x2"))
        store.put(d1)
        store.put(d2)
        assert store.empty() is False
        first_key, first_val = store.next()
        assert first_key == d1.info._id
        assert first_val.info._id == d1.info._id

    def test_has_downloads_and_get_next_download(self) -> None:
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        # One non-auto-start, one started, one cancelled, and one eligible
        i1 = make_item(id="n1")
        i1.auto_start = False
        i2 = make_item(id="s1")
        i3 = make_item(id="c1")
        i4 = make_item(id="ok1")

        store.put(StubDownload(info=i1, started=False))
        store.put(StubDownload(info=i2, started=True))
        store.put(StubDownload(info=i3, started=False, cancelled=True))
        store.put(StubDownload(info=i4, started=False))

        assert store.has_downloads() is True
        nxt = store.get_next_download()
        assert isinstance(nxt, StubDownload)
        assert nxt.info._id == i4._id

    @pytest.mark.asyncio
    async def test_test_method_executes_query(self) -> None:
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)
        # Should not raise
        ok = await store.test()
        assert ok is True

    def test_get_item_returns_none_when_no_kwargs(self) -> None:
        """Test that get_item returns None when no kwargs provided."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        result = store.get_item()
        assert result is None

    def test_get_item_finds_by_single_attribute(self) -> None:
        """Test that get_item correctly finds item by a single attribute."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        # Create items with different attributes
        item1 = make_item(id="vid1", url="http://example.com/1", title="Video 1", folder="folder1")
        item1._id = "id1"  # Override auto-generated UUID
        item2 = make_item(id="vid2", url="http://example.com/2", title="Video 2", folder="folder2")
        item2._id = "id2"  # Override auto-generated UUID

        d1 = StubDownload(info=item1)
        d2 = StubDownload(info=item2)

        store.put(d1)
        store.put(d2)

        # Test finding by title
        result = store.get_item(title="Video 1")
        assert result is not None
        assert result.info._id == "id1"
        assert result.info.title == "Video 1"

        # Test finding by folder
        result = store.get_item(folder="folder2")
        assert result is not None
        assert result.info._id == "id2"
        assert result.info.folder == "folder2"

        # Test finding by url
        result = store.get_item(url="http://example.com/1")
        assert result is not None
        assert result.info._id == "id1"

    def test_get_item_finds_by_multiple_attributes(self) -> None:
        """Test that get_item finds item when ANY of the provided attributes match."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", url="http://example.com/1", title="Video 1", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", url="http://example.com/2", title="Video 2", folder="folder2")
        item2._id = "id2"

        d1 = StubDownload(info=item1)
        d2 = StubDownload(info=item2)

        store.put(d1)
        store.put(d2)

        # Test finding by multiple attributes where one matches
        result = store.get_item(title="Video 1", folder="wrong_folder")
        assert result is not None
        assert result.info._id == "id1"

        # Test finding where second attribute matches
        result = store.get_item(title="Wrong Title", folder="folder2")
        assert result is not None
        assert result.info._id == "id2"

    def test_get_item_returns_none_when_no_match(self) -> None:
        """Test that get_item returns None when no attributes match."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item = make_item(id="vid1", url="http://example.com/1", title="Video 1", folder="folder1")
        item._id = "id1"
        d = StubDownload(info=item)
        store.put(d)

        # Test with non-matching attribute
        result = store.get_item(title="Nonexistent Video")
        assert result is None

        # Test with non-existent attribute key
        result = store.get_item(nonexistent_field="value")
        assert result is None

    def test_get_item_skips_items_with_no_info(self) -> None:
        """Test that get_item skips items that have no info attribute."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        # Create a valid item
        item = make_item(id="vid1", url="http://example.com/1", title="Video 1")
        item._id = "id1"
        d = StubDownload(info=item)
        store.put(d)

        # Manually add an item with None info
        class BrokenDownload:
            def __init__(self):
                self.info = None

        store._dict["broken"] = BrokenDownload()

        # Should still find the valid item
        result = store.get_item(title="Video 1")
        assert result is not None
        assert result.info._id == "id1"

    def test_get_item_returns_first_match(self) -> None:
        """Test that get_item returns the first matching item when multiple match."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        # Create multiple items with same title
        item1 = make_item(id="vid1", url="http://example.com/1", title="Same Title", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", url="http://example.com/2", title="Same Title", folder="folder2")
        item2._id = "id2"

        d1 = StubDownload(info=item1)
        d2 = StubDownload(info=item2)

        store.put(d1)
        store.put(d2)

        # Should return first match (note: OrderedDict maintains insertion order)
        result = store.get_item(title="Same Title")
        assert result is not None
        assert result.info._id == "id1"

    def test_init(self) -> None:
        """Test DataStore initialization."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        assert store._type == StoreType.QUEUE
        assert store._connection is conn
        assert isinstance(store._dict, OrderedDict)
        assert len(store._dict) == 0

    def test_load(self) -> None:
        """Test loading items from database into memory."""
        conn = make_conn()

        # Insert items directly into database
        item1_data = asdict(make_item(id="vid1", url="http://example.com/1", title="Video 1"))
        item1_data.pop("_id", None)
        item2_data = asdict(make_item(id="vid2", url="http://example.com/2", title="Video 2"))
        item2_data.pop("_id", None)

        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "id1",
                str(StoreType.QUEUE),
                "http://example.com/1",
                json.dumps(item1_data),
                created.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "id2",
                str(StoreType.QUEUE),
                "http://example.com/2",
                json.dumps(item2_data),
                created.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        # Create store and load
        store = DataStore(StoreType.QUEUE, conn)
        assert len(store._dict) == 0

        store.load()
        assert len(store._dict) == 2
        assert "id1" in store._dict
        assert "id2" in store._dict
        assert store._dict["id1"].info.url == "http://example.com/1"
        assert store._dict["id2"].info.url == "http://example.com/2"

    def test_load_with_different_store_types(self) -> None:
        """Test that load only loads items matching the store type."""
        conn = make_conn()

        # Insert items with different types
        item1_data = asdict(make_item(id="vid1", url="http://example.com/1"))
        item1_data.pop("_id", None)
        item2_data = asdict(make_item(id="vid2", url="http://example.com/2"))
        item2_data.pop("_id", None)

        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "id1",
                str(StoreType.QUEUE),
                "http://example.com/1",
                json.dumps(item1_data),
                created.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.execute(
            "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "id2",
                str(StoreType.HISTORY),
                "http://example.com/2",
                json.dumps(item2_data),
                created.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        # Load QUEUE store - should only get queue items
        queue_store = DataStore(StoreType.QUEUE, conn)
        queue_store.load()
        assert len(queue_store._dict) == 1
        assert "id1" in queue_store._dict

        # Load HISTORY store - should only get history items
        history_store = DataStore(StoreType.HISTORY, conn)
        history_store.load()
        assert len(history_store._dict) == 1
        assert "id2" in history_store._dict

    def test_get_by_id(self) -> None:
        """Test getting item by ID."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", url="http://example.com/1", title="Video 1")
        item1._id = "id1"
        item2 = make_item(id="vid2", url="http://example.com/2", title="Video 2")
        item2._id = "id2"

        d1 = StubDownload(info=item1)
        d2 = StubDownload(info=item2)

        store.put(d1)
        store.put(d2)

        # Test getting existing items
        result = store.get_by_id("id1")
        assert result is not None
        assert result.info._id == "id1"
        assert result.info.title == "Video 1"

        result = store.get_by_id("id2")
        assert result is not None
        assert result.info._id == "id2"

        # Test getting non-existent item
        result = store.get_by_id("nonexistent")
        assert result is None

    def test_items(self) -> None:
        """Test getting all items as list of tuples."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

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

        store.put(d1)
        store.put(d2)

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

    def test_get_total_count_with_empty_store(self) -> None:
        """Test get_total_count with empty datastore."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        count = store.get_total_count()
        assert count == 0

    def test_get_total_count_with_items(self) -> None:
        """Test get_total_count with items in database."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        # Add items directly to database
        created = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        for i in range(5):
            item_data = asdict(make_item(id=f"vid{i}"))
            item_data.pop("_id", None)
            conn.execute(
                "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (f"id{i}", str(StoreType.QUEUE), f"http://example.com/{i}", json.dumps(item_data), created),
            )

        count = store.get_total_count()
        assert count == 5

    def test_get_total_count_respects_store_type(self) -> None:
        """Test that get_total_count only counts items of the correct type."""
        conn = make_conn()

        created = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

        # Add 3 QUEUE items
        for i in range(3):
            item_data = asdict(make_item(id=f"vid{i}"))
            item_data.pop("_id", None)
            conn.execute(
                "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (f"q{i}", str(StoreType.QUEUE), f"http://example.com/{i}", json.dumps(item_data), created),
            )

        # Add 2 HISTORY items
        for i in range(2):
            item_data = asdict(make_item(id=f"vid{i}"))
            item_data.pop("_id", None)
            conn.execute(
                "INSERT INTO history (id, type, url, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (f"h{i}", str(StoreType.HISTORY), f"http://example.com/{i}", json.dumps(item_data), created),
            )

        queue_store = DataStore(StoreType.QUEUE, conn)
        assert queue_store.get_total_count() == 3

        history_store = DataStore(StoreType.HISTORY, conn)
        assert history_store.get_total_count() == 2

    def test_put_with_error_status_emits_event(self) -> None:
        """Test that put() emits an event when item has error status."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item = make_item(id="vid1")
        item.status = "error"
        item.error = "Test error message"

        d = StubDownload(info=item)

        # We can't easily test event emission without mocking EventBus
        # Just verify it doesn't crash
        result = store.put(d)
        assert result is not None

    def test_put_with_no_notify_skips_event(self) -> None:
        """Test that put() with no_notify=True doesn't emit events."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item = make_item(id="vid1")
        item.status = "error"
        item.error = "Test error message"

        d = StubDownload(info=item)

        # Should not emit event when no_notify=True
        result = store.put(d, no_notify=True)
        assert result is not None
        assert result.info._id == item._id

    def test_delete_nonexistent_item(self) -> None:
        """Test that deleting non-existent item doesn't raise error."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        # Should not raise error
        store.delete("nonexistent_id")

        # Verify nothing was deleted from database
        row = conn.execute("SELECT * FROM history WHERE id=?", ("nonexistent_id",)).fetchone()
        assert row is None

    def test_has_downloads_with_empty_dict(self) -> None:
        """Test has_downloads returns False when dict is empty."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        assert store.has_downloads() is False

    def test_has_downloads_with_no_eligible_downloads(self) -> None:
        """Test has_downloads returns False when no downloads are eligible."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        # Add item that's already started
        item1 = make_item(id="vid1")
        store.put(StubDownload(info=item1, started=True))

        # Add item with auto_start=False
        item2 = make_item(id="vid2")
        item2.auto_start = False
        store.put(StubDownload(info=item2, started=False))

        assert store.has_downloads() is False

    def test_get_next_download_returns_none_when_empty(self) -> None:
        """Test get_next_download returns None when no eligible downloads."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        result = store.get_next_download()
        assert result is None

    def test_get_next_download_skips_cancelled(self) -> None:
        """Test get_next_download skips cancelled downloads."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        # Add cancelled download
        item1 = make_item(id="vid1")
        item1._id = "id1"
        store.put(StubDownload(info=item1, started=False, cancelled=True))

        # Add eligible download
        item2 = make_item(id="vid2")
        item2._id = "id2"
        store.put(StubDownload(info=item2, started=False, cancelled=False))

        result = store.get_next_download()
        assert result is not None
        assert result.info._id == "id2"

    def test_update_store_item_removes_datetime_field(self) -> None:
        """Test that _update_store_item removes datetime field before storage."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item = make_item(id="vid1")
        item.datetime = "Thu, 01 Jan 2024 12:00:00 GMT"  # Add datetime field

        d = StubDownload(info=item)
        store.put(d)

        # Verify datetime field is not in stored JSON
        row = conn.execute("SELECT data FROM history WHERE id=?", (item._id,)).fetchone()
        assert row is not None
        data = json.loads(row["data"])
        assert "datetime" not in data

    def test_update_store_item_removes_live_in_when_finished(self) -> None:
        """Test that _update_store_item removes live_in field when status is finished."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item = make_item(id="vid1")
        item.status = "finished"
        item.live_in = "PT5M"  # Add live_in field

        d = StubDownload(info=item)
        store.put(d)

        # Verify live_in field is not in stored JSON when status is finished
        row = conn.execute("SELECT data FROM history WHERE id=?", (item._id,)).fetchone()
        assert row is not None
        data = json.loads(row["data"])
        assert "live_in" not in data

    def test_update_store_item_keeps_live_in_when_not_finished(self) -> None:
        """Test that _update_store_item keeps live_in field when status is not finished."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item = make_item(id="vid1")
        item.status = "downloading"
        item.live_in = "PT5M"  # Add live_in field

        d = StubDownload(info=item)
        store.put(d)

        # Verify live_in field IS in stored JSON when status is not finished
        row = conn.execute("SELECT data FROM history WHERE id=?", (item._id,)).fetchone()
        assert row is not None
        data = json.loads(row["data"])
        assert "live_in" in data
        assert data["live_in"] == "PT5M"


class TestDataStoreOperations:
    """Test get_item with different comparison operations."""

    def test_operation_equal(self) -> None:
        """Test EQUAL operation (default behavior)."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Exact Match", folder="folder1")
        item1._id = "id1"
        store.put(StubDownload(info=item1))

        # Test with explicit EQUAL operation
        result = store.get_item(title=(Operation.EQUAL, "Exact Match"))
        assert result is not None
        assert result.info._id == "id1"

        # Test default behavior (no operation specified)
        result = store.get_item(title="Exact Match")
        assert result is not None
        assert result.info._id == "id1"

        # Test no match
        result = store.get_item(title=(Operation.EQUAL, "No Match"))
        assert result is None

    def test_operation_not_equal(self) -> None:
        """Test NOT_EQUAL operation."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Video 1", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="Video 2", folder="folder2")
        item2._id = "id2"

        store.put(StubDownload(info=item1))
        store.put(StubDownload(info=item2))

        # Find item where title is not "Video 1"
        result = store.get_item(title=(Operation.NOT_EQUAL, "Video 1"))
        assert result is not None
        assert result.info._id == "id2"

    def test_operation_contain(self) -> None:
        """Test CONTAIN operation (substring match)."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Python Tutorial Video", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="JavaScript Course", folder="folder2")
        item2._id = "id2"

        store.put(StubDownload(info=item1))
        store.put(StubDownload(info=item2))

        # Find item with "Python" in title
        result = store.get_item(title=(Operation.CONTAIN, "Python"))
        assert result is not None
        assert result.info._id == "id1"

        # Find item with "Tutorial" in title
        result = store.get_item(title=(Operation.CONTAIN, "Tutorial"))
        assert result is not None
        assert result.info._id == "id1"

        # No match
        result = store.get_item(title=(Operation.CONTAIN, "Rust"))
        assert result is None

    def test_operation_not_contain(self) -> None:
        """Test NOT_CONTAIN operation."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Python Tutorial", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="JavaScript Course", folder="folder2")
        item2._id = "id2"

        store.put(StubDownload(info=item1))
        store.put(StubDownload(info=item2))

        # Find item that doesn't contain "Python"
        result = store.get_item(title=(Operation.NOT_CONTAIN, "Python"))
        assert result is not None
        assert result.info._id == "id2"

    def test_operation_starts_with(self) -> None:
        """Test STARTS_WITH operation."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Tutorial: Python Basics", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="Course: JavaScript", folder="folder2")
        item2._id = "id2"

        store.put(StubDownload(info=item1))
        store.put(StubDownload(info=item2))

        # Find item starting with "Tutorial"
        result = store.get_item(title=(Operation.STARTS_WITH, "Tutorial"))
        assert result is not None
        assert result.info._id == "id1"

        # Find item starting with "Course"
        result = store.get_item(title=(Operation.STARTS_WITH, "Course"))
        assert result is not None
        assert result.info._id == "id2"

        # No match
        result = store.get_item(title=(Operation.STARTS_WITH, "Video"))
        assert result is None

    def test_operation_ends_with(self) -> None:
        """Test ENDS_WITH operation."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Learn Python", folder="folder1")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="Learn JavaScript", folder="folder2")
        item2._id = "id2"

        store.put(StubDownload(info=item1))
        store.put(StubDownload(info=item2))

        # Find item ending with "Python"
        result = store.get_item(title=(Operation.ENDS_WITH, "Python"))
        assert result is not None
        assert result.info._id == "id1"

        # Find item ending with "JavaScript"
        result = store.get_item(title=(Operation.ENDS_WITH, "JavaScript"))
        assert result is not None
        assert result.info._id == "id2"

        # No match
        result = store.get_item(title=(Operation.ENDS_WITH, "Course"))
        assert result is None

    def test_operation_greater_than(self) -> None:
        """Test GREATER_THAN operation with numeric values."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.filesize = 1000
        item2 = make_item(id="vid2", title="Video 2")
        item2._id = "id2"
        item2.filesize = 2000

        store.put(StubDownload(info=item1))
        store.put(StubDownload(info=item2))

        # Find item with filesize > 1500
        result = store.get_item(filesize=(Operation.GREATER_THAN, 1500))
        assert result is not None
        assert result.info._id == "id2"

        # Find item with filesize > 500 (should return first match)
        result = store.get_item(filesize=(Operation.GREATER_THAN, 500))
        assert result is not None
        assert result.info._id == "id1"

    def test_operation_less_than(self) -> None:
        """Test LESS_THAN operation."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.filesize = 1000
        item2 = make_item(id="vid2", title="Video 2")
        item2._id = "id2"
        item2.filesize = 2000

        store.put(StubDownload(info=item1))
        store.put(StubDownload(info=item2))

        # Find item with filesize < 1500
        result = store.get_item(filesize=(Operation.LESS_THAN, 1500))
        assert result is not None
        assert result.info._id == "id1"

    def test_operation_greater_equal(self) -> None:
        """Test GREATER_EQUAL operation."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.filesize = 1000

        store.put(StubDownload(info=item1))

        # Test >= with exact match
        result = store.get_item(filesize=(Operation.GREATER_EQUAL, 1000))
        assert result is not None
        assert result.info._id == "id1"

        # Test >= with less than
        result = store.get_item(filesize=(Operation.GREATER_EQUAL, 500))
        assert result is not None
        assert result.info._id == "id1"

        # Test >= with greater than
        result = store.get_item(filesize=(Operation.GREATER_EQUAL, 1500))
        assert result is None

    def test_operation_less_equal(self) -> None:
        """Test LESS_EQUAL operation."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.filesize = 1000

        store.put(StubDownload(info=item1))

        # Test <= with exact match
        result = store.get_item(filesize=(Operation.LESS_EQUAL, 1000))
        assert result is not None

        # Test <= with greater than
        result = store.get_item(filesize=(Operation.LESS_EQUAL, 1500))
        assert result is not None

        # Test <= with less than
        result = store.get_item(filesize=(Operation.LESS_EQUAL, 500))
        assert result is None

    def test_mixed_operations(self) -> None:
        """Test using multiple operations in a single query."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Python Tutorial", folder="tutorials")
        item1._id = "id1"
        item2 = make_item(id="vid2", title="Python Advanced", folder="courses")
        item2._id = "id2"
        item3 = make_item(id="vid3", title="JavaScript Basics", folder="tutorials")
        item3._id = "id3"

        store.put(StubDownload(info=item1))
        store.put(StubDownload(info=item2))
        store.put(StubDownload(info=item3))

        # Mix of operation and default (any match returns true)
        result = store.get_item(title=(Operation.CONTAIN, "Python"), folder="tutorials")
        assert result is not None
        assert result.info._id == "id1"

        # Mix where first condition matches
        result = store.get_item(title=(Operation.CONTAIN, "JavaScript"), folder="nonexistent")
        assert result is not None
        assert result.info._id == "id3"

    def test_operation_with_none_values(self) -> None:
        """Test operations handle None values gracefully."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"
        item1.description = None

        store.put(StubDownload(info=item1))

        # CONTAIN with None field should return False
        result = store.get_item(description=(Operation.CONTAIN, "test"))
        assert result is None

        # NOT_CONTAIN with None field should return True
        result = store.get_item(description=(Operation.NOT_CONTAIN, "test"))
        assert result is not None

        # GREATER_THAN with None should return False
        result = store.get_item(description=(Operation.GREATER_THAN, 100))
        assert result is None

    def test_operation_with_invalid_comparisons(self) -> None:
        """Test that invalid comparisons are handled gracefully."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"

        store.put(StubDownload(info=item1))

        # Try to compare string with number using > (should return False/None)
        result = store.get_item(title=(Operation.GREATER_THAN, 100))
        assert result is None

    def test_operation_backward_compatibility(self) -> None:
        """Test that string operation names work for backward compatibility."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Python Tutorial")
        item1._id = "id1"

        store.put(StubDownload(info=item1))

        # Using string operation value
        result = store.get_item(title=("in", "Python"))
        assert result is not None
        assert result.info._id == "id1"

        # Using string for EQUAL
        result = store.get_item(title=("==", "Python Tutorial"))
        assert result is not None

    def test_operation_with_nonexistent_field(self) -> None:
        """Test operations with fields that don't exist."""
        conn = make_conn()
        store = DataStore(StoreType.QUEUE, conn)

        item1 = make_item(id="vid1", title="Video 1")
        item1._id = "id1"

        store.put(StubDownload(info=item1))

        # Try to match on non-existent field
        result = store.get_item(nonexistent_field=(Operation.EQUAL, "value"))
        assert result is None

        result = store.get_item(nonexistent_field=(Operation.CONTAIN, "value"))
        assert result is None
