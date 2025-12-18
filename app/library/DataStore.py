import asyncio
import copy
import logging
from collections import OrderedDict
from collections.abc import Iterable
from enum import Enum

from .Download import Download
from .ItemDTO import ItemDTO
from .operations import matches_condition
from .sqlite_store import SqliteStore

LOG = logging.getLogger("datastore")


class StoreType(str, Enum):
    HISTORY = "done"
    QUEUE = "queue"

    @classmethod
    def all(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def from_value(cls, value: str) -> "StoreType":
        for member in cls:
            if member.value == value:
                return member
        msg = f"Invalid StoreType value: {value}"
        raise ValueError(msg)

    def __str__(self) -> str:  # pragma: no cover
        return self.value


def _strip_transient_fields(item: ItemDTO) -> ItemDTO:
    stored = copy.deepcopy(item)
    if hasattr(stored, "datetime"):
        try:
            delattr(stored, "datetime")
        except AttributeError:
            pass
    if stored.status == "finished" and hasattr(stored, "live_in"):
        try:
            delattr(stored, "live_in")
        except AttributeError:
            pass
    return stored


class DataStore:
    """
    In-memory queue cache + optional write-behind to persistence.
    History reads go straight to persistence.
    """

    def __init__(self, type: StoreType, connection: SqliteStore):
        self._type = type
        self._connection: SqliteStore = connection
        self._dict: OrderedDict[str, Download] = OrderedDict()

    # cache helpers
    async def load(self) -> None:
        saved = await self._connection.fetch_saved(str(self._type))
        for key, item in saved:
            self._dict[key] = Download(info=item)

    async def saved_items(self) -> list[tuple[str, ItemDTO]]:
        return await self._connection.fetch_saved(str(self._type))

    def exists(self, key: str | None = None, url: str | None = None) -> bool:
        if not key and not url:
            msg = "key or url must be provided."
            raise KeyError(msg)
        if key and key in self._dict:
            return True
        return any(
            (key and self._dict[i].info._id == key) or (url and self._dict[i].info.url == url) for i in self._dict
        )

    def get(self, key: str | None = None, url: str | None = None) -> Download:
        if not key and not url:
            msg = "key or url must be provided."
            raise KeyError(msg)
        for i in self._dict:
            if (key and self._dict[i].info._id == key) or (url and self._dict[i].info.url == url):
                return self._dict[i]
        msg: str = f"{key=} or {url=} not found."
        raise KeyError(msg)

    def get_item(self, **kwargs) -> Download | None:
        if not kwargs:
            return None
        for i in self._dict:
            if not self._dict[i].info:
                continue
            info = self._dict[i].info.__dict__
            if any(matches_condition(key, value, info) for key, value in kwargs.items()):
                return self._dict[i]
        return None

    async def get_by_id(self, id: str) -> Download | None:
        val = self._dict.get(id)
        if val or self._type == StoreType.QUEUE:
            return val

        if item := await self._connection.get_by_id(str(self._type), id):
            download = Download(info=item)
            self._dict[id] = download
            return download

        return None

    def items(self):
        return self._dict.items()

    async def put(self, value: Download, no_notify: bool = False) -> Download:
        _ = no_notify
        self._dict[value.info._id] = value
        asyncio.create_task(self._connection.enqueue_upsert(str(self._type), _strip_transient_fields(value.info)))
        return value

    def delete(self, key: str) -> None:
        self._dict.pop(key, None)
        asyncio.create_task(self._connection.enqueue_delete(str(self._type), key))

    def next(self):
        return next(iter(self._dict.items()))

    def empty(self) -> bool:
        return not bool(self._dict)

    def has_downloads(self) -> bool:
        return any(self._dict[key].info.auto_start and self._dict[key].started() is False for key in self._dict)

    def get_next_download(self) -> Download | None:
        for key in self._dict:
            ref = self._dict[key]
            if ref.info.auto_start and not ref.started() and not ref.is_cancelled():
                return ref
        return None

    async def get_total_count(self, status_filter: str | None = None) -> int:
        return await self._connection.count(str(self._type), status_filter=status_filter)

    async def get_items_paginated(
        self, page: int = 1, per_page: int = 50, order: str = "DESC", status_filter: str | None = None
    ):
        if page < 1:
            msg = "page must be >= 1"
            raise ValueError(msg)
        if per_page < 1:
            msg = "per_page must be >= 1"
            raise ValueError(msg)
        order = order.upper()
        if order not in ("ASC", "DESC"):
            msg = f"order must be 'ASC' or 'DESC', got '{order}'"
            raise ValueError(msg)
        return await self._connection.paginate(str(self._type), page, per_page, order, status_filter)

    async def bulk_delete(self, ids: Iterable[str]) -> int:
        deleted = await self._connection.bulk_delete(str(self._type), ids)
        for _id in ids:
            self._dict.pop(_id, None)
        return deleted

    async def test(self) -> bool:
        await self._connection.count(str(self._type))
        return True
