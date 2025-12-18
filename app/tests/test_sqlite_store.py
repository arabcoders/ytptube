from datetime import UTC, datetime, timedelta

import pytest

from app.library.ItemDTO import ItemDTO
from app.library.sqlite_store import SqliteStore


async def make_store() -> SqliteStore:
    """Create an isolated in-memory SqliteStore instance with schema."""
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=":memory:")
    await store._ensure_conn()
    assert store._conn is not None
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
            'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (?, ?, ?, ?, ?)',
            (itm._id, "history", itm.url, encoded, created_at),
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
async def test_on_shutdown_closes_connection():
    store = await make_store()
    await store.enqueue_upsert("queue", make_item(1))
    await store.flush()

    await store.on_shutdown(None)
    assert store._conn is None


