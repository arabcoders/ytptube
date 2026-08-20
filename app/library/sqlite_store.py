import os
from urllib.parse import quote_plus

from aiohttp import web
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.library.Events import EventBus, Events
from app.library.log import get_logger
from app.library.Services import Services
from app.library.Singleton import ThreadSafe

LOG = get_logger()


def _memory_db_url(db_path: str) -> str:
    if db_path == ":memory:":
        return "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"
    memory_name = db_path[len(":memory:") :].lstrip(":") or "default"
    return f"sqlite+aiosqlite:///file:{quote_plus(memory_name)}?mode=memory&cache=shared&uri=true"


class SqliteStore(metaclass=ThreadSafe):
    @staticmethod
    def get_instance(db_path: str | None = None) -> "SqliteStore":
        return SqliteStore(db_path=db_path)

    def __init__(self, db_path: str | None):
        self._db_path = db_path
        self._engine: AsyncEngine | None = None
        self._conn: AsyncConnection | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def attach(self, app: web.Application) -> None:
        Services.get_instance().add("sqlite_store", self)

        async def handle_event(_, __):
            await self.get_connection()

        EventBus.get_instance().subscribe(Events.STARTED, handle_event, "SqliteStore.get_connection")
        app.on_shutdown.append(self.on_shutdown)

    async def on_shutdown(self, _: web.Application) -> None:
        await self.close()

    async def __aenter__(self):
        await self.get_connection()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        if not self._sessionmaker:
            msg = "Database connection not initialized. Call get_connection() first or use within async context."
            raise RuntimeError(msg)
        return self._sessionmaker

    async def execute_raw(self, query: str, params: dict | tuple | None = None) -> None:
        conn = await self.get_connection()
        if isinstance(params, tuple):
            if query.count("?") != len(params):
                msg = "Parameter count mismatch"
                raise ValueError(msg)
            values = {f"p{i}": value for i, value in enumerate(params)}
            for i in range(len(params)):
                query = query.replace("?", f":p{i}", 1)
            await conn.execute(text(query), values)
        else:
            await conn.execute(text(query), params or {})
        await conn.commit()

    async def fetch_raw(self, query: str, params: dict | tuple | None = None):
        conn = await self.get_connection()
        if isinstance(params, tuple):
            if query.count("?") != len(params):
                msg = "Parameter count mismatch"
                raise ValueError(msg)
            values = {f"p{i}": value for i, value in enumerate(params)}
            for i in range(len(params)):
                query = query.replace("?", f":p{i}", 1)
            result = await conn.execute(text(query), values)
        else:
            result = await conn.execute(text(query), params or {})
        return result.mappings().all()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
        if self._engine:
            await self._engine.dispose()
            self._engine = None
        self._sessionmaker = None

    async def get_connection(self) -> AsyncConnection:
        if self._conn:
            return self._conn
        if not self._db_path:
            msg = "No database path specified for SqliteStore."
            raise RuntimeError(msg)

        from app.library import migrate
        from app.main import ROOT_PATH

        if self._db_path.startswith(":memory"):
            db_url = _memory_db_url(self._db_path)
        else:
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
            db_url = f"sqlite+aiosqlite:///{self._db_path}"
        self._engine = create_async_engine(
            db_url, echo=False, connect_args={"check_same_thread": False, "uri": self._db_path.startswith(":memory")}
        )
        self._conn = await self._engine.connect()
        version = await migrate.get_version(self._conn)
        await migrate.upgrade(self._conn, ROOT_PATH / "migrations")
        if version:
            LOG.debug("Database schema version is '%s'.", version)
        await self._conn.execute(text("PRAGMA journal_mode=wal"))
        await self._conn.execute(text("PRAGMA busy_timeout=5000"))
        await self._conn.execute(text("PRAGMA foreign_keys=ON"))
        await self._conn.commit()
        self._sessionmaker = async_sessionmaker(bind=self._engine, class_=AsyncSession, expire_on_commit=False)
        return self._conn
