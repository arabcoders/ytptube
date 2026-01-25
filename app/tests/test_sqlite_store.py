from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.library.ItemDTO import ItemDTO
from app.library.operations import Operation
from app.library.sqlite_store import SqliteStore


async def make_store() -> SqliteStore:
    """Create an isolated in-memory SqliteStore instance with schema."""
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=":memory:")
    await store.get_connection()
    assert store._engine is not None, "Engine should be initialized after _ensure_conn"
    return store


def make_item(idx: int, *, status: str = "finished") -> ItemDTO:
    return ItemDTO(
        id=f"vid{idx}",
        title=f"Video {idx}",
        url=f"https://example.com/{idx}",
        folder="/downloads",
        status=status,
    )


@pytest.mark.asyncio
async def test_sessionmaker_returns_valid_sessionmaker() -> None:
    """Test that sessionmaker() returns a working async_sessionmaker."""
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=":memory:")

    # Ensure connection is initialized
    await store.get_connection()

    # Get sessionmaker
    sessionmaker = store.sessionmaker()
    assert sessionmaker is not None, "Sessionmaker should not be None after connection initialization"

    # Verify we can create a session
    async with sessionmaker() as session:
        assert session is not None, "Session should be created successfully"

    await store.close()


@pytest.mark.asyncio
async def test_sessionmaker_raises_before_init() -> None:
    """Test that sessionmaker() raises error before connection initialization."""
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=":memory:")

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        store.sessionmaker()

    await store.close()


@pytest.mark.asyncio
async def test_sqlalchemy_engine_disposed_on_close() -> None:
    """Test that SQLAlchemy engine is properly disposed on close."""
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=":memory:")

    await store.get_connection()
    assert store._engine is not None, "Engine should be created"
    assert store._sessionmaker is not None, "Sessionmaker should be created"

    await store.close()
    assert store._engine is None, "Engine should be None after close"
    assert store._sessionmaker is None, "Sessionmaker should be None after close"


@pytest.mark.asyncio
async def test_enqueue_upsert_and_fetch_saved():
    store = await make_store()
    item = make_item(1)

    await store.enqueue_upsert("queue", item)
    await store.flush()

    saved = await store.fetch_saved("queue")
    assert len(saved) == 1
    key, loaded = saved[0]
    assert key == item._id
    assert loaded.title == item.title
    await store.close()


@pytest.mark.asyncio
async def test_delete_and_bulk_delete():
    store = await make_store()
    items = [make_item(i) for i in range(3)]
    for itm in items:
        await store.enqueue_upsert("queue", itm)
    await store.flush()

    await store.enqueue_delete("queue", items[0]._id)
    await store.enqueue_bulk_delete("queue", [items[1]._id])
    await store.flush()

    remaining = await store.fetch_saved("queue")
    assert len(remaining) == 1
    assert remaining[0][0] == items[2]._id
    await store.close()


@pytest.mark.asyncio
async def test_count_with_status_filters():
    store = await make_store()
    finished_items = [make_item(i, status="finished") for i in range(2)]
    pending_items = [make_item(i + 10, status="pending") for i in range(3)]

    for itm in finished_items + pending_items:
        await store.enqueue_upsert("history", itm)
    await store.flush()

    assert await store.count("history", status_filter="finished") == 2
    assert await store.count("history", status_filter="pending") == 3
    assert await store.count("history", status_filter="!finished") == 3
    await store.close()


@pytest.mark.asyncio
async def test_paginate_order_and_bounds():
    store = await make_store()
    base = datetime(2024, 1, 1, tzinfo=UTC)
    _list: list[ItemDTO] = []
    for i in range(15):
        itm = make_item(i)
        encoded = itm.json()
        created_at = (base + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
        _list.append(itm)
        await store._conn.execute(
            text(
                'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (:id, :type, :url, :data, :created_at)'
            ),
            {"id": itm._id, "type": "history", "url": itm.url, "data": encoded, "created_at": created_at},
        )
    await store._conn.commit()

    items, total, page, total_pages = await store.paginate("history", page=1, per_page=5, order="ASC")
    assert total == 15
    assert page == 1
    assert total_pages == 3
    assert items[0][0] == _list[0]._id

    items_desc, *_ = await store.paginate("history", page=1, per_page=3, order="DESC")
    assert len(items_desc) == 3
    assert items_desc[0][0] == _list[14]._id
    await store.close()


@pytest.mark.asyncio
async def test_get_by_id():
    store = await make_store()
    item = make_item(99)
    await store.enqueue_upsert("queue", item)
    await store.flush()
    assert item._id == (await store.get_by_id("queue", item._id))._id
    await store.close()


@pytest.mark.asyncio
async def test_shutdown_closes_worker_queue():
    store = await make_store()
    await store.enqueue_upsert("queue", make_item(99))
    await store.shutdown()
    assert store._queue is None
    await store.close()


@pytest.mark.asyncio
async def test_enqueue_delete_removes_row():
    store = await make_store()
    item = make_item(5)
    await store.enqueue_upsert("queue", item)
    await store.flush()

    await store.enqueue_delete("queue", item._id)
    await store.flush()

    rows = await store.fetch_saved("queue")
    assert rows == []
    await store.close()


@pytest.mark.asyncio
async def test_enqueue_bulk_delete_returns_count_and_bulk_path():
    store = await make_store()
    items = [make_item(i) for i in range(3)]
    for itm in items:
        await store.enqueue_upsert("history", itm)
    await store.flush()

    await store.enqueue_bulk_delete("history", [items[0]._id, items[1]._id])
    await store.flush()

    remaining = await store.fetch_saved("history")
    assert len(remaining) == 1
    assert remaining[0][0] == items[2]._id

    # direct bulk_delete should report affected rows
    count = await store.bulk_delete("history", [items[2]._id])
    assert count == 1
    await store.close()


@pytest.mark.asyncio
async def test_paginate_out_of_range_returns_last_page():
    store = await make_store()
    for i in range(7):
        await store.enqueue_upsert("history", make_item(i))
    await store.flush()

    items, total, page, total_pages = await store.paginate("history", page=10, per_page=3, order="DESC")
    assert total == 7
    assert total_pages == 3
    assert page == 3
    assert len(items) == 1
    await store.close()


@pytest.mark.asyncio
async def test_get_item_returns_none_without_kwargs():
    store = await make_store()
    await store.enqueue_upsert("queue", make_item(1))
    await store.flush()

    result = await store.get_item("queue")
    assert result is None
    await store.close()


@pytest.mark.asyncio
async def test_get_item_matches_conditions():
    store = await make_store()
    first = make_item(1, status="finished")
    second = make_item(2, status="pending")

    await store.enqueue_upsert("queue", first)
    await store.enqueue_upsert("queue", second)
    await store.flush()

    # equality match
    match_equal = await store.get_item("queue", title=first.title)
    assert match_equal is not None
    assert match_equal._id == first._id

    # NOT_EQUAL should find the second item
    match_not_equal = await store.get_item("queue", status=(Operation.NOT_EQUAL, "finished"))
    assert match_not_equal is not None
    assert match_not_equal._id == second._id

    # CONTAIN should find first created (first)
    match_contain = await store.get_item("queue", title=(Operation.CONTAIN, "Video"))
    assert match_contain is not None
    assert match_contain._id == first._id

    # No match returns None
    no_match = await store.get_item("queue", title=(Operation.CONTAIN, "does-not-exist"))
    assert no_match is None
    await store.close()


@pytest.mark.asyncio
async def test_on_shutdown_closes_connection():
    store = await make_store()
    await store.enqueue_upsert("queue", make_item(1))
    await store.flush()

    await store.on_shutdown(None)
    assert store._conn is None
    # Note: on_shutdown already closes the connection, so no need to call close() again


@pytest.mark.asyncio
async def test_exists_and_get_by_key_and_url():
    store = await make_store()
    item = make_item(42)
    await store.enqueue_upsert("queue", item)
    await store.flush()

    assert await store.exists("queue", key=item._id) is True
    assert await store.exists("queue", url=item.url) is True

    fetched_by_key = await store.get("queue", key=item._id)
    assert fetched_by_key is not None
    assert fetched_by_key._id == item._id

    fetched_by_url = await store.get("queue", url=item.url)
    assert fetched_by_url is not None
    assert fetched_by_url._id == item._id

    assert await store.exists("queue", key="missing") is False
    assert await store.get("queue", key="missing") is None
    await store.close()


@pytest.mark.asyncio
async def test_exists_and_get_raise_without_key_or_url():
    store = await make_store()
    with pytest.raises(KeyError):
        await store.exists("queue")
    with pytest.raises(KeyError):
        await store.get("queue")
    await store.close()
