import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from email.utils import formatdate

import pytest

from app.library.DataStore import DataStore, StoreType
from app.library.ItemDTO import ItemDTO


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
    conn.execute(
        "CREATE TABLE history (id TEXT PRIMARY KEY, type TEXT, url TEXT, data TEXT, created_at TEXT)"
    )
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
