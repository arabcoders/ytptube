import asyncio
import contextlib
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import fields
from datetime import UTC, datetime
from email.utils import formatdate

from aiohttp import web
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncConnection

from .Events import EventBus, Events
from .ItemDTO import ItemDTO
from .operations import Operation, matches_condition
from .Services import Services
from .Singleton import ThreadSafe
from .Utils import init_class

LOG: logging.Logger = logging.getLogger(__name__)

ITEM_DTO_FIELDS: set[str] = {f.name for f in fields(ItemDTO)}


class Terminator:
    pass


class _Op:
    """Queued write operation."""

    __slots__ = ("item", "key", "keys", "op", "type_value")

    def __init__(
        self, op: Terminator | str, type_value: str, item: ItemDTO | None, key: str | None, keys: list[str] | None
    ):
        self.op = op
        self.type_value = type_value
        self.item = item
        self.key = key
        self.keys = keys


class SqliteStore(metaclass=ThreadSafe):
    @staticmethod
    def get_instance(db_path: str | None = None) -> "SqliteStore":
        return SqliteStore(db_path=db_path)

    def attach(self, app: web.Application):
        Services.get_instance().add("sqlite_store", self)

        async def handle_event(_, __):
            await self.get_connection()

        EventBus.get_instance().subscribe(Events.STARTED, handle_event, "SqliteStore.get_connection")

        app.on_shutdown.append(self.on_shutdown)

    async def on_shutdown(self, _: web.Application):
        LOG.debug("Shutting down SqliteStore...")
        await self.close()
        LOG.debug("SqliteStore shut down complete.")

    def __init__(self, db_path: str, *, max_pending: int = 200, flush_interval: float = 0.05):
        self._db_path: str = db_path
        self._engine: AsyncEngine | None = None
        self._conn: AsyncConnection | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None
        self._queue: asyncio.Queue[_Op] | None = None
        self._task: asyncio.Task | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._flush_interval: float = flush_interval
        self._max_pending: int = max_pending

    async def __aenter__(self):
        await self.get_connection()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        """
        Return the SQLAlchemy async sessionmaker.

        This allows other parts of the system to create SQLAlchemy sessions
        that share the same database connection/engine.

        Returns:
            async_sessionmaker[AsyncSession]: The sessionmaker instance.

        Raises:
            RuntimeError: If called before connection is initialized.

        """
        if not self._sessionmaker:
            msg = "Database connection not initialized. Call get_connection() first or use within async context."
            raise RuntimeError(msg)
        return self._sessionmaker

    async def fetch_saved(self, type_value: str) -> list[tuple[str, ItemDTO]]:
        await self.get_connection()
        result = await self._conn.execute(
            text(
                'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = :type_value ORDER BY "created_at" ASC'
            ),
            {"type_value": type_value},
        )
        rows = result.mappings().all()

        items: list[tuple[str, ItemDTO]] = []
        for row in rows:
            row_date = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
            data = json.loads(row["data"])
            data.pop("_id", None)
            item = init_class(ItemDTO, data, ITEM_DTO_FIELDS)
            item._id = row["id"]
            item.datetime = formatdate(row_date.replace(tzinfo=UTC).timestamp())
            items.append((row["id"], item))
        return items

    async def exists(self, type_value: str, key: str | None = None, url: str | None = None) -> bool:
        return await self.get(type_value, key=key, url=url) is not None

    async def get(self, type_value: str, key: str | None = None, url: str | None = None) -> bool:
        if not key and not url:
            msg = "key or url must be provided."
            raise KeyError(msg)

        await self.get_connection()

        clauses: list[str] = []
        params: dict[str, str] = {"type_value": type_value}

        if key:
            clauses.append('"id" = :key')
            params["key"] = key

        if url:
            clauses.append("json_extract(data, '$.url') = :url")
            params["url"] = url

        where_clause = " OR ".join(clauses)
        query = (
            f'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = :type_value AND ({where_clause}) LIMIT 1'  # noqa: S608
        )

        result = await self._conn.execute(text(query), params)
        row = result.mappings().first()

        if not row:
            return None

        row_date = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
        data = json.loads(row["data"])
        data.pop("_id", None)
        item = init_class(ItemDTO, data, ITEM_DTO_FIELDS)
        item._id = row["id"]
        item.datetime = formatdate(row_date.replace(tzinfo=UTC).timestamp())
        return item

    async def get_by_id(self, type_value: str, id: str) -> ItemDTO | None:
        await self.get_connection()
        result = await self._conn.execute(
            text('SELECT "id", "data", "created_at" FROM "history" WHERE "type" = :type_value AND "id" = :id'),
            {"type_value": type_value, "id": id},
        )
        row = result.mappings().first()

        if not row:
            return None

        row_date = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
        data = json.loads(row["data"])
        data.pop("_id", None)
        item = init_class(ItemDTO, data, ITEM_DTO_FIELDS)
        item._id = row["id"]
        item.datetime = formatdate(row_date.replace(tzinfo=UTC).timestamp())
        return item

    async def get_item(self, type_value: str, **kwargs) -> ItemDTO | None:
        """
        Return first item of type matching *any* condition.

        Mirrors :meth:`DataStore.get_item` semantics: if any provided condition
        matches (OR logic) return the first row by creation time. Returns None
        when kwargs is empty or no row matches.
        """
        if not kwargs:
            return None

        await self.get_connection()

        clauses: list[str] = []
        params: dict[str, str | float | int] = {"type_value": type_value}
        param_counter = 0

        def _safe_key(key: str) -> str | None:
            return key if key.replace("_", "").isalnum() else None

        for key, raw_value in kwargs.items():
            safe_key = _safe_key(key)
            if not safe_key:
                continue

            if isinstance(raw_value, tuple) and len(raw_value) == 2:
                operation, value = raw_value
            else:
                operation, value = Operation.EQUAL, raw_value

            if isinstance(operation, str):
                try:
                    operation = Operation(operation)
                except ValueError:
                    operation = Operation.EQUAL

            path: str = f"$.{safe_key}"
            json_extract: str = f"json_extract(data, '{path}')"
            param_name: str = f"param_{param_counter}"
            param_counter += 1

            if Operation.EQUAL == operation:
                clauses.append(f"{json_extract} = :{param_name}")
                params[param_name] = value
            elif Operation.NOT_EQUAL == operation:
                clauses.append(f"{json_extract} != :{param_name}")
                params[param_name] = value
            elif Operation.CONTAIN == operation:
                clauses.append(f"{json_extract} LIKE :{param_name} ESCAPE '\\'")
                params[param_name] = f"%{value}%"
            elif Operation.NOT_CONTAIN == operation:
                clauses.append(f"({json_extract} IS NULL OR {json_extract} NOT LIKE :{param_name} ESCAPE '\\')")
                params[param_name] = f"%{value}%"
            elif Operation.STARTS_WITH == operation:
                clauses.append(f"{json_extract} LIKE :{param_name} ESCAPE '\\'")
                params[param_name] = f"{value}%"
            elif Operation.ENDS_WITH == operation:
                clauses.append(f"{json_extract} LIKE :{param_name} ESCAPE '\\'")
                params[param_name] = f"%{value}"
            elif Operation.GREATER_THAN == operation:
                clauses.append(f"{json_extract} > :{param_name}")
                params[param_name] = value
            elif Operation.LESS_THAN == operation:
                clauses.append(f"{json_extract} < :{param_name}")
                params[param_name] = value
            elif Operation.GREATER_EQUAL == operation:
                clauses.append(f"{json_extract} >= :{param_name}")
                params[param_name] = value
            elif Operation.LESS_EQUAL == operation:
                clauses.append(f"{json_extract} <= :{param_name}")
                params[param_name] = value

        if not clauses:
            return None

        where_clause: str = " OR ".join(f"({clause})" for clause in clauses)
        query: str = f'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = :type_value AND ({where_clause}) ORDER BY "created_at" ASC LIMIT 1'  # noqa: S608

        result = await self._conn.execute(text(query), params)
        row = result.mappings().first()

        if not row:
            return None

        row_date = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
        data = json.loads(row["data"])
        data.pop("_id", None)
        item = init_class(ItemDTO, data, ITEM_DTO_FIELDS)
        item._id = row["id"]
        item.datetime = formatdate(row_date.replace(tzinfo=UTC).timestamp())

        return item if any(matches_condition(k, v, item.__dict__) for k, v in kwargs.items()) else None

    async def count(self, type_value: str, status_filter: str | None = None) -> int:
        await self.get_connection()
        where_clauses: list[str] = ['"type" = :type_value']
        params: dict[str, str] = {"type_value": type_value}

        if status_filter:
            if status_filter.startswith("!"):
                status_value = status_filter[1:]
                where_clauses.append("json_extract(data, '$.status') != :status")
                params["status"] = status_value
            else:
                where_clauses.append("json_extract(data, '$.status') = :status")
                params["status"] = status_filter

        where_clause: str = " AND ".join(where_clauses)
        count_query: str = f'SELECT COUNT(*) as count FROM "history" WHERE {where_clause}'  # noqa: S608

        result = await self._conn.execute(text(count_query), params)
        row = result.mappings().first()

        return row["count"] if row else 0

    async def paginate(
        self,
        type_value: str,
        page: int,
        per_page: int,
        order: str,
        status_filter: str | None = None,
    ) -> tuple[list[tuple[str, ItemDTO]], int, int, int]:
        await self.get_connection()
        where_clauses: list[str] = ['"type" = :type_value']
        params: dict[str, str | int] = {"type_value": type_value}

        if status_filter:
            if status_filter.startswith("!"):
                status_value = status_filter[1:]
                where_clauses.append("json_extract(data, '$.status') != :status")
                params["status"] = status_value
            else:
                where_clauses.append("json_extract(data, '$.status') = :status")
                params["status"] = status_filter

        where_clause: str = " AND ".join(where_clauses)
        count_query: str = f'SELECT COUNT(*) as count FROM "history" WHERE {where_clause}'  # noqa: S608

        result = await self._conn.execute(text(count_query), params)
        count_row = result.mappings().first()

        total_items = count_row["count"] if count_row else 0
        total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 1

        if page > total_pages and total_items > 0:
            page = total_pages

        offset: int = (page - 1) * per_page
        params["limit"] = per_page
        params["offset"] = offset

        query: str = f'SELECT "id", "data", "created_at" FROM "history" WHERE {where_clause} ORDER BY "created_at" {order} LIMIT :limit OFFSET :offset'  # noqa: S608

        result = await self._conn.execute(text(query), params)
        rows = result.mappings().all()

        items: list[tuple[str, ItemDTO]] = []
        for row in rows:
            row_date = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
            data = json.loads(row["data"])
            data.pop("_id", None)
            item = init_class(ItemDTO, data, ITEM_DTO_FIELDS)
            item._id = row["id"]
            item.datetime = formatdate(row_date.replace(tzinfo=UTC).timestamp())
            items.append((row["id"], item))

        return items, total_items, page, total_pages

    async def upsert(self, type_value: str, item: ItemDTO) -> None:
        await self.get_connection()
        await self._upsert_now(type_value, item)

    async def delete(self, type_value: str, key: str) -> None:
        await self.get_connection()
        await self._conn.execute(
            text('DELETE FROM "history" WHERE "type" = :type_value AND "id" = :key'),
            {"type_value": type_value, "key": key},
        )
        await self._conn.commit()

    async def bulk_delete(self, type_value: str, keys: Iterable[str]) -> int:
        await self.get_connection()
        keys_list: list[str] = list(keys)
        if not keys_list:
            return 0
        placeholders = ",".join(f":key_{i}" for i in range(len(keys_list)))
        params: dict[str, str] = {"type_value": type_value}
        params.update({f"key_{i}": key for i, key in enumerate(keys_list)})

        result = await self._conn.execute(
            text(f'DELETE FROM "history" WHERE "type" = :type_value AND "id" IN ({placeholders})'),  # noqa: S608
            params,
        )
        await self._conn.commit()
        return result.rowcount if result else 0

    async def enqueue_upsert(self, type_value: str, item: ItemDTO) -> None:
        await self._enqueue(_Op("upsert", type_value, item, None, None))

    async def enqueue_delete(self, type_value: str, key: str) -> None:
        await self._enqueue(_Op("delete", type_value, None, key, None))

    async def enqueue_bulk_delete(self, type_value: str, keys: Iterable[str]) -> None:
        await self._enqueue(_Op("bulk_delete", type_value, None, None, list(keys)))

    async def flush(self) -> None:
        if self._queue:
            await self._queue.join()

    async def shutdown(self) -> None:
        """Flush pending writes and stop writer task."""
        if self._queue:
            try:
                await self._queue.put(_Op(Terminator(), "", None, None, None))
                LOG.debug("Waiting for SqliteStore queue to drain...")
                await asyncio.wait_for(self._queue.join(), timeout=2)
            except TimeoutError:
                LOG.warning("SqliteStore queue did not drain within timeout; forcing writer shutdown.")

        if self._task:
            LOG.debug("Waiting for SqliteStore writer task to finish...")
            if not self._task.done():
                self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(self._task, timeout=2)

        self._task = None
        self._queue = None

    async def close(self) -> None:
        await self.shutdown()

        if self._conn:
            await self._conn.close()
            self._conn = None

        if self._engine:
            await self._engine.dispose()
            self._engine = None

        self._sessionmaker = None

    async def _enqueue(self, op: _Op) -> None:
        self._ensure_worker()
        await self._queue.put(op)

    def _ensure_worker(self) -> None:
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._max_pending)
            self._task = asyncio.create_task(self._writer(), name="sqlite-store-writer")

    async def _writer(self) -> None:
        while True:
            op = await self._queue.get()
            if isinstance(op.op, Terminator):
                self._queue.task_done()
                break
            try:
                async with self._lock:
                    await self._apply(op)
            except Exception as ex:
                LOG.exception(ex)
            finally:
                self._queue.task_done()
                await asyncio.sleep(self._flush_interval)

    async def _apply(self, op: _Op) -> None:
        await self.get_connection()
        if op.op == "upsert" and op.item:
            await self._upsert_now_conn(self._conn, op.type_value, op.item)
            await self._conn.commit()
        elif op.op == "delete" and op.key:
            await self._conn.execute(
                text('DELETE FROM "history" WHERE "type" = :type_value AND "id" = :key'),
                {"type_value": op.type_value, "key": op.key},
            )
            await self._conn.commit()
        elif op.op == "bulk_delete" and op.keys:
            placeholders = ",".join(f":key_{i}" for i in range(len(op.keys)))
            params: dict[str, str] = {"type_value": op.type_value}
            params.update({f"key_{i}": key for i, key in enumerate(op.keys)})
            await self._conn.execute(
                text(f'DELETE FROM "history" WHERE "type" = :type_value AND "id" IN ({placeholders})'),  # noqa: S608
                params,
            )
            await self._conn.commit()

    async def _upsert_now(self, type_value: str, item: ItemDTO) -> None:
        await self.get_connection()
        await self._upsert_now_conn(self._conn, type_value, item)
        await self._conn.commit()

    async def _upsert_now_conn(self, conn, type_value: str, item: ItemDTO) -> None:
        """Helper to upsert using an existing connection."""
        sql = """
        INSERT INTO "history" ("id", "type", "url", "data")
        VALUES (:id, :type, :url, :data)
        ON CONFLICT DO UPDATE SET "type" = :type2, "url" = :url2, "data" = :data2, created_at = :created_at
        """
        encoded = item.json()
        await conn.execute(
            text(sql.strip()),
            {
                "id": item._id,
                "type": type_value,
                "url": item.url,
                "data": encoded,
                "type2": type_value,
                "url2": item.url,
                "data2": encoded,
                "created_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    async def execute_raw(self, query: str, params: dict | tuple | None = None) -> None:
        """Execute raw SQL query (for testing purposes)."""
        await self.get_connection()
        if isinstance(params, tuple):
            # Convert positional params to dict for SQLAlchemy
            # Assuming queries use ? placeholders, we need to count them
            placeholders = query.count("?")
            if placeholders != len(params):
                msg = (
                    f"Parameter count mismatch: query has {placeholders} placeholders but {len(params)} params provided"
                )
                raise ValueError(msg)
            # Create numbered parameters
            param_dict = {f"p{i}": params[i] for i in range(len(params))}
            # Replace ? with :p0, :p1, etc.
            for i in range(len(params)):
                query = query.replace("?", f":p{i}", 1)
            await self._conn.execute(text(query), param_dict)
        elif isinstance(params, dict):
            await self._conn.execute(text(query), params)
        else:
            await self._conn.execute(text(query))
        await self._conn.commit()

    async def fetch_raw(self, query: str, params: dict | tuple | None = None):
        """Fetch results from raw SQL query (for testing purposes)."""
        await self.get_connection()
        if isinstance(params, tuple):
            # Convert positional params to dict for SQLAlchemy
            placeholders = query.count("?")
            if placeholders != len(params):
                msg = (
                    f"Parameter count mismatch: query has {placeholders} placeholders but {len(params)} params provided"
                )
                raise ValueError(msg)
            param_dict = {f"p{i}": params[i] for i in range(len(params))}
            for i in range(len(params)):
                query = query.replace("?", f":p{i}", 1)
            result = await self._conn.execute(text(query), param_dict)
        elif isinstance(params, dict):
            result = await self._conn.execute(text(query), params)
        else:
            result = await self._conn.execute(text(query))
        return result.mappings().all()

    async def get_connection(self) -> AsyncConnection:
        if self._conn:
            return self._conn

        if not self._db_path:
            msg = "No database path specified for SqliteStore."
            raise RuntimeError(msg)

        from app.library import migrate
        from app.main import ROOT_PATH

        if self._db_path.startswith(":memory"):
            db_url: str = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"
        else:
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
            db_url: str = f"sqlite+aiosqlite:///{self._db_path}"

        self._engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False, "uri": self._db_path.startswith(":memory")},
        )
        self._conn = await self._engine.connect()

        if version := await migrate.get_version(self._conn):
            LOG.debug(f"DB Version: '{version}'.")

        await migrate.upgrade(self._conn, ROOT_PATH / "migrations")
        if not version:
            LOG.debug(f"DB Version after initial migration: '{await migrate.get_version(self._conn)}'.")

        await self._conn.execute(text("PRAGMA journal_mode=wal"))
        await self._conn.execute(text("PRAGMA busy_timeout=5000"))
        await self._conn.execute(text("PRAGMA foreign_keys=ON"))
        await self._conn.commit()

        self._sessionmaker = async_sessionmaker(bind=self._engine, class_=AsyncSession, expire_on_commit=False)

        return self._conn
