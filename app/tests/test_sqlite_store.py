import asyncio

import pytest
from sqlalchemy.pool import StaticPool

from app.library.sqlite_store import SqliteStore
from app.tests.helpers import make_in_memory_db_path


@pytest.mark.asyncio
async def test_sessionmaker_ready() -> None:
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=make_in_memory_db_path("sessionmaker"))
    await store.get_connection()

    sessionmaker = store.sessionmaker()
    assert sessionmaker is not None
    async with sessionmaker() as session:
        assert session is not None
    await store.close()


@pytest.mark.asyncio
async def test_sessionmaker_raises_before_init() -> None:
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=make_in_memory_db_path("sessionmaker-before-init"))
    with pytest.raises(RuntimeError):
        store.sessionmaker()
    await store.close()


@pytest.mark.asyncio
async def test_sqlalchemy_engine_disposed_close() -> None:
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=make_in_memory_db_path("engine-close"))
    await store.get_connection()
    assert store._engine is not None
    assert store._sessionmaker is not None

    await store.close()
    assert store._engine is None
    assert store._sessionmaker is None


@pytest.mark.asyncio
async def test_memory_databases_are_isolated() -> None:
    SqliteStore._reset_singleton()
    first = SqliteStore.get_instance(db_path=":memory:named-a")
    await first.get_connection()
    await first.execute_raw(
        'INSERT INTO "history" ("id", "type", "url", "data", "created_at") VALUES (?, ?, ?, ?, ?)',
        (
            "first",
            "queue",
            "https://example.com/a",
            '{"id":"a","title":"A","url":"https://example.com/a","folder":"/downloads","status":"finished"}',
            "2024-01-01 00:00:00",
        ),
    )
    await first.close()

    SqliteStore._reset_singleton()
    second = SqliteStore.get_instance(db_path=":memory:named-b")
    await second.get_connection()
    rows = await second.fetch_raw('SELECT "id" FROM "history" WHERE "id" = ?', ("first",))
    assert rows == []
    await second.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("db_path", [":memory:", ":memory:named"])
async def test_memory_pool(db_path: str) -> None:
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=db_path)
    try:
        async with asyncio.timeout(5):
            await store.get_connection()
            assert store._engine is not None
            assert isinstance(store._engine.pool, StaticPool)
    finally:
        try:
            async with asyncio.timeout(5):
                await store.close()
        finally:
            SqliteStore._reset_singleton()
