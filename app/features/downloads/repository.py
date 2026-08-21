from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from sqlalchemy import Integer, delete, func, or_, select
from sqlalchemy.dialects.sqlite import insert

from app.features.core.models import utcnow
from app.features.downloads.models import DownloadModel
from app.library.log import get_logger
from app.library.operations import Operation, matches_condition
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from contextlib import AbstractAsyncContextManager

    from aiohttp import web
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

    from app.features.downloads.items import ItemDTO

    SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

LOG = get_logger()


def _status_clause(status_filter: str | None) -> ColumnElement[bool] | None:
    entries: list[str] = [entry.strip() for entry in (status_filter or "").split(",") if entry.strip()]
    if not entries:
        return None
    path = func.json_extract(DownloadModel.data, "$.status")
    if all(entry.startswith("!") for entry in entries):
        values: list[str] = [entry[1:].strip() for entry in entries if entry[1:].strip()]
        return path.not_in(values) if values else None
    values: list[str] = [entry for entry in entries if not entry.startswith("!")]
    return path.in_(values) if values else None


class _Operation:
    def __init__(self, kind: str, type_value: str, model: DownloadModel | None = None, key: str | None = None) -> None:
        self.kind, self.type_value, self.model, self.key = kind, type_value, model, key


class _Stop:
    pass


class DownloadsRepository(metaclass=Singleton):
    def __init__(
        self, session: SessionFactory | None = None, *, max_pending: int = 200, flush_interval: float = 0.05
    ) -> None:
        self.session = session or self._default_session
        self._max_pending = max_pending
        self._flush_interval = flush_interval
        self._queue: asyncio.Queue[_Operation | _Stop] | None = None
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    def get_instance() -> DownloadsRepository:
        return DownloadsRepository()

    @staticmethod
    def _default_session() -> AbstractAsyncContextManager[AsyncSession]:
        from app.features.core.deps import get_session

        return get_session()

    def attach(self, app: web.Application) -> None:
        app.on_shutdown.append(self.on_shutdown)

    async def on_shutdown(self, _: web.Application) -> None:
        await self.shutdown()

    async def fetch_saved(self, type_value: str) -> list[tuple[str, ItemDTO]]:
        async with self.session() as session:
            query = select(DownloadModel).where(DownloadModel.type == type_value)
            if type_value == "queue":
                position = func.json_extract(DownloadModel.data, "$.queue_position")
                query = query.order_by(position.is_(None), position.cast(Integer), DownloadModel.created_at)
            else:
                query = query.order_by(DownloadModel.created_at)
            result = await session.execute(query)
            return [(model.id, model.to_item()) for model in result.scalars()]

    async def get(self, type_value: str, key: str | None = None, url: str | None = None) -> ItemDTO | None:
        if not key and not url:
            msg = "key or url must be provided."
            raise KeyError(msg)
        clauses = []
        if key:
            clauses.append(DownloadModel.id == key)
        if url:
            clauses.append(func.json_extract(DownloadModel.data, "$.url") == url)
        async with self.session() as session:
            result = await session.execute(
                select(DownloadModel).where(DownloadModel.type == type_value, or_(*clauses)).limit(1)
            )
            model = result.scalar_one_or_none()
            return model.to_item() if model else None

    async def exists(self, type_value: str, key: str | None = None, url: str | None = None) -> bool:
        return await self.get(type_value, key, url) is not None

    async def get_by_id(self, type_value: str, id: str) -> ItemDTO | None:
        return await self.get(type_value, key=id)

    async def get_many_by_ids(self, type_value: str, ids: Iterable[str]) -> list[tuple[str, ItemDTO]]:
        ids = list(ids)
        if not ids:
            return []
        async with self.session() as session:
            result = await session.execute(
                select(DownloadModel).where(DownloadModel.type == type_value, DownloadModel.id.in_(ids))
            )
            found = {model.id: model.to_item() for model in result.scalars()}
        return [(id, found[id]) for id in ids if id in found]

    async def get_many_by_status(self, type_value: str, status_filter: str) -> list[tuple[str, ItemDTO]]:
        async with self.session() as session:
            query = select(DownloadModel).where(DownloadModel.type == type_value)
            if (clause := _status_clause(status_filter)) is not None:
                query = query.where(clause)
            result = await session.execute(query.order_by(DownloadModel.created_at.desc()))
            return [(model.id, model.to_item()) for model in result.scalars()]

    async def get_item(self, type_value: str, **kwargs: tuple | str | float | bool) -> ItemDTO | None:
        if not kwargs:
            return None
        clauses = []
        for key, raw in kwargs.items():
            if not key.replace("_", "").isalnum():
                continue
            operation, value = raw if isinstance(raw, tuple) and len(raw) == 2 else (Operation.EQUAL, raw)
            if isinstance(operation, str):
                try:
                    operation = Operation(operation)
                except ValueError:
                    operation = Operation.EQUAL
            field = func.json_extract(DownloadModel.data, f"$.{key}")
            if operation == Operation.EQUAL:
                clause = field == value
            elif operation == Operation.NOT_EQUAL:
                clause = field != value
            elif operation == Operation.CONTAIN:
                clause = field.like(f"%{value}%", escape="\\")
            elif operation == Operation.NOT_CONTAIN:
                clause = or_(field.is_(None), ~field.like(f"%{value}%", escape="\\"))
            elif operation == Operation.STARTS_WITH:
                clause = field.like(f"{value}%", escape="\\")
            elif operation == Operation.ENDS_WITH:
                clause = field.like(f"%{value}", escape="\\")
            elif operation == Operation.GREATER_THAN:
                clause = field > value
            elif operation == Operation.LESS_THAN:
                clause = field < value
            elif operation == Operation.GREATER_EQUAL:
                clause = field >= value
            elif operation == Operation.LESS_EQUAL:
                clause = field <= value
            else:
                continue
            clauses.append(clause)
        if not clauses:
            return None
        async with self.session() as session:
            result = await session.execute(
                select(DownloadModel)
                .where(DownloadModel.type == type_value, or_(*clauses))
                .order_by(DownloadModel.created_at)
                .limit(1)
            )
            model = result.scalar_one_or_none()
        if model is None:
            return None
        item = model.to_item()
        return item if any(matches_condition(key, value, item.__dict__) for key, value in kwargs.items()) else None

    async def count(self, type_value: str, status_filter: str | None = None) -> int:
        async with self.session() as session:
            query = select(func.count()).select_from(DownloadModel).where(DownloadModel.type == type_value)
            if (clause := _status_clause(status_filter)) is not None:
                query = query.where(clause)
            return int((await session.execute(query)).scalar_one())

    async def paginate(
        self, type_value: str, page: int, per_page: int, order: str, status_filter: str | None = None
    ) -> tuple[list[tuple[str, ItemDTO]], int, int, int]:
        total = await self.count(type_value, status_filter)
        pages = (total + per_page - 1) // per_page if total else 1
        page = min(page, pages) if total else page
        async with self.session() as session:
            query = select(DownloadModel).where(DownloadModel.type == type_value)
            if (clause := _status_clause(status_filter)) is not None:
                query = query.where(clause)
            query = (
                query.order_by(DownloadModel.created_at.asc() if order == "ASC" else DownloadModel.created_at.desc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
            result = await session.execute(query)
            return [(model.id, model.to_item()) for model in result.scalars()], total, page, pages

    async def enqueue_upsert(self, type_value: str, model: DownloadModel) -> None:
        await self._enqueue(_Operation("upsert", type_value, model=model))

    async def enqueue_delete(self, type_value: str, key: str) -> None:
        await self._enqueue(_Operation("delete", type_value, key=key))

    async def flush(self) -> None:
        if self._queue:
            await self._queue.join()

    async def bulk_delete(self, type_value: str, keys: Iterable[str]) -> int:
        await self.flush()
        keys = list(keys)
        if not keys:
            return 0
        async with self.session() as session:
            result = await session.execute(
                delete(DownloadModel).where(DownloadModel.type == type_value, DownloadModel.id.in_(keys))
            )
            await session.commit()
            return getattr(result, "rowcount", 0) or 0

    async def bulk_delete_by_status(self, type_value: str, status_filter: str) -> int:
        await self.flush()
        async with self.session() as session:
            query = delete(DownloadModel).where(DownloadModel.type == type_value)
            if (clause := _status_clause(status_filter)) is not None:
                query = query.where(clause)
            result = await session.execute(query)
            await session.commit()
            return getattr(result, "rowcount", 0) or 0

    async def _enqueue(self, operation: _Operation) -> None:
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._max_pending)
            self._task = asyncio.create_task(self._writer(), name="downloads-writer")
        await self._queue.put(operation)

    async def _writer(self) -> None:
        while self._queue:
            operation = await self._queue.get()
            try:
                if isinstance(operation, _Stop):
                    return
                async with self._lock:
                    await self._apply(operation)
            except Exception:
                LOG.exception("Failed to apply queued download write.")
            finally:
                self._queue.task_done()
                await asyncio.sleep(self._flush_interval)

    async def _apply(self, operation: _Operation) -> None:
        async with self.session() as session:
            if operation.kind == "delete":
                await session.execute(
                    delete(DownloadModel).where(
                        DownloadModel.type == operation.type_value, DownloadModel.id == operation.key
                    )
                )
            elif operation.model:
                model = operation.model
                values = {
                    "id": model.id,
                    "type": model.type,
                    "url": model.url,
                    "data": model.data,
                    "created_at": utcnow().replace(microsecond=0),
                }
                statement = (
                    insert(DownloadModel)
                    .values(**values)
                    .on_conflict_do_update(set_={key: values[key] for key in ("type", "url", "data", "created_at")})
                )
                await session.execute(statement)
            await session.commit()

    async def shutdown(self) -> None:
        if self._queue:
            await self._queue.put(_Stop())
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._queue.join(), timeout=2)
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._queue = None
        self._task = None
