import asyncio
import sqlite3
from contextlib import closing
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.pool import StaticPool

from app.library import migrate
from app.library.sqlite_store import SqliteStore
from app.main import ROOT_PATH
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


@pytest_asyncio.fixture
async def revision_store(tmp_path):
    SqliteStore._reset_singleton()
    store = SqliteStore.get_instance(db_path=str(tmp_path / "database.db"), no_auto_migration=True)
    try:
        async with asyncio.timeout(10):
            yield store
    finally:
        try:
            async with asyncio.timeout(5):
                await store.close()
        finally:
            SqliteStore._reset_singleton()


@pytest.mark.asyncio
@pytest.mark.parametrize(("no_auto_migration", "empty"), [(False, False), (True, False), (True, True)])
async def test_database_bootstrap(tmp_path, no_auto_migration, empty):
    SqliteStore._reset_singleton()
    db_path = tmp_path / "database.db"
    if empty:
        db_path.touch()
    store = SqliteStore.get_instance(db_path=str(db_path), no_auto_migration=no_auto_migration)
    try:
        async with asyncio.timeout(10):
            conn = await store.get_connection()
            latest = max(m.get_version() for m in migrate.load_migrations(ROOT_PATH / "migrations"))
            assert await migrate.get_version(conn) == latest
            assert await store.fetch_raw("SELECT name FROM sqlite_master WHERE name = 'history'")
    finally:
        try:
            async with asyncio.timeout(5):
                await store.close()
        finally:
            SqliteStore._reset_singleton()


@pytest.mark.asyncio
async def test_current_revision(revision_store, monkeypatch):
    latest = max(m.get_version() for m in migrate.load_migrations(ROOT_PATH / "migrations"))
    with closing(sqlite3.connect(revision_store._db_path)) as db, db:
        db.execute("CREATE TABLE migration_version (version TEXT)")
        db.execute("INSERT INTO migration_version VALUES (?)", (latest,))
        for operation in ("INSERT", "UPDATE", "DELETE"):
            db.execute(
                f"CREATE TRIGGER block_{operation} BEFORE {operation} ON migration_version "
                "BEGIN SELECT RAISE(ABORT, 'migration revision is read-only'); END"
            )
    upgrade = AsyncMock(side_effect=AssertionError("Unexpected migration"))
    monkeypatch.setattr(migrate, "upgrade", upgrade)

    conn = await revision_store.get_connection()

    assert await migrate.get_version(conn) == latest
    assert revision_store.sessionmaker() is not None
    await revision_store.execute_raw("CREATE TABLE usable (id INTEGER)")
    await revision_store.execute_raw("INSERT INTO usable VALUES (1)")
    assert await revision_store.fetch_raw("SELECT id FROM usable") == [{"id": 1}]
    upgrade.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("version", ["0", "20000101000000", "99991231235959"])
async def test_refuses_revision(revision_store, monkeypatch, version):
    with closing(sqlite3.connect(revision_store._db_path)) as db, db:
        db.execute("CREATE TABLE migration_version (version TEXT)")
        db.execute("INSERT INTO migration_version VALUES (?)", (version,))
    upgrade = AsyncMock(side_effect=AssertionError("Unexpected migration"))
    monkeypatch.setattr(migrate, "upgrade", upgrade)

    for _ in range(2):
        with pytest.raises(RuntimeError, match="expected .*Start without --no-auto-migration"):
            await revision_store.get_connection()
        assert revision_store._conn is None
        assert revision_store._engine is None
        with pytest.raises(RuntimeError, match="not initialized"):
            revision_store.sessionmaker()

    with closing(sqlite3.connect(revision_store._db_path)) as db:
        tables = db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        assert tables == [("migration_version",)]
        assert db.execute("SELECT version FROM migration_version").fetchall() == [(version,)]
    upgrade.assert_not_awaited()
