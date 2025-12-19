import asyncio
import contextlib
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import fields
from datetime import UTC, datetime
from email.utils import formatdate

import aiosqlite
from aiohttp import web

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
        app.on_shutdown.append(self.on_shutdown)

    async def on_shutdown(self, _: web.Application):
        LOG.debug("Shutting down SqliteStore...")
        await self.close()
        LOG.debug("SqliteStore shut down complete.")

    def __init__(self, db_path: str, *, max_pending: int = 200, flush_interval: float = 0.05):
        self._db_path: str = db_path
        self._conn: aiosqlite.Connection | None = None
        self._queue: asyncio.Queue[_Op] | None = None
        self._task: asyncio.Task | None = None
        self._flush_interval: float = flush_interval
        self._max_pending: int = max_pending
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "SqliteStore":
        await self._ensure_conn()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def fetch_saved(self, type_value: str) -> list[tuple[str, ItemDTO]]:
        await self._ensure_conn()
        cursor = await self._conn.execute(
            'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = ? ORDER BY "created_at" ASC',
            (type_value,),
        )
        items: list[tuple[str, ItemDTO]] = []
        async with cursor:
            async for row in cursor:
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

        await self._ensure_conn()

        clauses: list[str] = []
        params: list[str] = []

        if key:
            clauses.append('"id" = ?')
            params.append(key)

        if url:
            clauses.append("json_extract(data, '$.url') = ?")
            params.append(url)

        where_clause = " OR ".join(clauses)
        query = f'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = ? AND ({where_clause}) LIMIT 1'  # noqa: S608
        cursor = await self._conn.execute(query, (type_value, *params))
        row = await cursor.fetchone()
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
        await self._ensure_conn()
        cursor = await self._conn.execute(
            'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = ? AND "id" = ?',
            (type_value, id),
        )
        row = await cursor.fetchone()
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

        await self._ensure_conn()

        clauses: list[str] = []
        params: list[str | float | int] = []

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

            path = f"$.{safe_key}"
            json_extract = f"json_extract(data, '{path}')"

            if Operation.EQUAL == operation:
                clauses.append(f"{json_extract} = ?")
                params.append(value)
            elif Operation.NOT_EQUAL == operation:
                clauses.append(f"{json_extract} != ?")
                params.append(value)
            elif Operation.CONTAIN == operation:
                clauses.append(f"{json_extract} LIKE ? ESCAPE '\\'")
                params.append(f"%{value}%")
            elif Operation.NOT_CONTAIN == operation:
                clauses.append(f"({json_extract} IS NULL OR {json_extract} NOT LIKE ? ESCAPE '\\')")
                params.append(f"%{value}%")
            elif Operation.STARTS_WITH == operation:
                clauses.append(f"{json_extract} LIKE ? ESCAPE '\\'")
                params.append(f"{value}%")
            elif Operation.ENDS_WITH == operation:
                clauses.append(f"{json_extract} LIKE ? ESCAPE '\\'")
                params.append(f"%{value}")
            elif Operation.GREATER_THAN == operation:
                clauses.append(f"{json_extract} > ?")
                params.append(value)
            elif Operation.LESS_THAN == operation:
                clauses.append(f"{json_extract} < ?")
                params.append(value)
            elif Operation.GREATER_EQUAL == operation:
                clauses.append(f"{json_extract} >= ?")
                params.append(value)
            elif Operation.LESS_EQUAL == operation:
                clauses.append(f"{json_extract} <= ?")
                params.append(value)

        if not clauses:
            return None

        where_clause = " OR ".join(f"({clause})" for clause in clauses)
        query = f'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = ? AND ({where_clause}) ORDER BY "created_at" ASC LIMIT 1'  # noqa: S608
        cursor = await self._conn.execute(query, (type_value, *params))
        row = await cursor.fetchone()
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
        await self._ensure_conn()
        where_clauses = ['"type" = ?']
        query_params: list[str] = [type_value]

        if status_filter:
            if status_filter.startswith("!"):
                status_value = status_filter[1:]
                where_clauses.append("json_extract(data, '$.status') != ?")
                query_params.append(status_value)
            else:
                where_clauses.append("json_extract(data, '$.status') = ?")
                query_params.append(status_filter)

        where_clause = " AND ".join(where_clauses)
        count_query = f'SELECT COUNT(*) as count FROM "history" WHERE {where_clause}'  # noqa: S608
        cursor = await self._conn.execute(count_query, tuple(query_params))
        row = await cursor.fetchone()
        return row["count"] if row else 0

    async def paginate(
        self,
        type_value: str,
        page: int,
        per_page: int,
        order: str,
        status_filter: str | None = None,
    ) -> tuple[list[tuple[str, ItemDTO]], int, int, int]:
        await self._ensure_conn()
        where_clauses = ['"type" = ?']
        query_params: list[str | int] = [type_value]

        if status_filter:
            if status_filter.startswith("!"):
                status_value = status_filter[1:]
                where_clauses.append("json_extract(data, '$.status') != ?")
                query_params.append(status_value)
            else:
                where_clauses.append("json_extract(data, '$.status') = ?")
                query_params.append(status_filter)

        where_clause = " AND ".join(where_clauses)
        count_query = f'SELECT COUNT(*) as count FROM "history" WHERE {where_clause}'  # noqa: S608
        count_cursor = await self._conn.execute(count_query, tuple(query_params))
        count_row = await count_cursor.fetchone()
        total_items = count_row["count"] if count_row else 0
        total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 1

        if page > total_pages and total_items > 0:
            page = total_pages

        offset = (page - 1) * per_page
        query_params.extend([per_page, offset])

        cursor = await self._conn.execute(
            f'SELECT "id", "data", "created_at" FROM "history" WHERE {where_clause} ORDER BY "created_at" {order} LIMIT ? OFFSET ?',  # noqa: S608
            tuple(query_params),
        )

        items: list[tuple[str, ItemDTO]] = []
        async with cursor:
            async for row in cursor:
                row_date = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
                data = json.loads(row["data"])
                data.pop("_id", None)
                item = init_class(ItemDTO, data, ITEM_DTO_FIELDS)
                item._id = row["id"]
                item.datetime = formatdate(row_date.replace(tzinfo=UTC).timestamp())
                items.append((row["id"], item))

        return items, total_items, page, total_pages

    async def upsert(self, type_value: str, item: ItemDTO) -> None:
        await self._ensure_conn()
        await self._upsert_now(type_value, item)

    async def delete(self, type_value: str, key: str) -> None:
        await self._ensure_conn()
        await self._conn.execute('DELETE FROM "history" WHERE "type" = ? AND "id" = ?', (type_value, key))

    async def bulk_delete(self, type_value: str, keys: Iterable[str]) -> int:
        await self._ensure_conn()
        keys_list = list(keys)
        if not keys_list:
            return 0
        placeholders = ",".join("?" for _ in keys_list)
        params = [type_value, *keys_list]
        cur = await self._conn.execute(
            f'DELETE FROM "history" WHERE "type" = ? AND "id" IN ({placeholders})',  # noqa: S608
            tuple(params),
        )
        return cur.rowcount if cur else 0

    async def commit(self) -> None:
        if self._conn:
            await self._conn.commit()

    async def enqueue_upsert(self, type_value: str, item: ItemDTO) -> None:
        await self._enqueue(_Op("upsert", type_value, item, None, None))

    async def enqueue_delete(self, type_value: str, key: str) -> None:
        await self._enqueue(_Op("delete", type_value, None, key, None))

    async def enqueue_bulk_delete(self, type_value: str, keys: Iterable[str]) -> None:
        await self._enqueue(_Op("bulk_delete", type_value, None, None, list(keys)))

    async def flush(self) -> None:
        if self._queue:
            await self._queue.join()
        if self._conn:
            await self._conn.commit()

    async def shutdown(self) -> None:
        """Flush pending writes, stop writer task, and commit."""
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

        if self._conn:
            LOG.debug("Committing final changes to SqliteStore...")
            await self._conn.commit()

        self._task = None
        self._queue = None

    async def close(self) -> None:
        await self.shutdown()
        if self._conn:
            LOG.debug("Closing SqliteStore connection...")
            await self._conn.close()
            self._conn = None

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
        await self._ensure_conn()
        if op.op == "upsert" and op.item:
            await self._upsert_now(op.type_value, op.item)
        elif op.op == "delete" and op.key:
            await self._conn.execute('DELETE FROM "history" WHERE "type" = ? AND "id" = ?', (op.type_value, op.key))
        elif op.op == "bulk_delete" and op.keys:
            placeholders = ",".join("?" for _ in op.keys)
            params = [op.type_value, *op.keys]
            await self._conn.execute(
                f'DELETE FROM "history" WHERE "type" = ? AND "id" IN ({placeholders})',  # noqa: S608
                tuple(params),
            )
        await self._conn.commit()

    async def _upsert_now(self, type_value: str, item: ItemDTO) -> None:
        await self._ensure_conn()
        sql = """
        INSERT INTO "history" ("id", "type", "url", "data")
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO UPDATE SET "type" = ?, "url" = ?, "data" = ?, created_at = ?
        """
        encoded = item.json()
        await self._conn.execute(
            sql.strip(),
            (
                item._id,
                type_value,
                item.url,
                encoded,
                type_value,
                item.url,
                encoded,
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    async def _ensure_conn(self) -> None:
        if self._conn:
            return

        if not self._db_path:
            msg = "No database path specified for SqliteStore."
            raise RuntimeError(msg)

        from app.library import migrate
        from app.main import ROOT_PATH

        if not self._db_path.startswith(":memory"):
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)

        self._conn = await aiosqlite.connect(database=self._db_path, isolation_level=None)
        self._conn.row_factory = aiosqlite.Row
        version = await migrate.get_version(self._conn)
        if version:
            LOG.debug(f"DB Version: '{version}'.")

        await migrate.upgrade(self._conn, ROOT_PATH / "migrations")
        if not version:
            version = await migrate.get_version(self._conn)
            LOG.debug(f"DB Version after initial migration: '{version}'.")

        await self._conn.execute("PRAGMA journal_mode=wal")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.commit()
