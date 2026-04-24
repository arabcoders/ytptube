import copy
import logging
from collections import OrderedDict
from collections.abc import Iterable
from enum import Enum

from .downloads import Download
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
    def __init__(self, type: StoreType, connection: SqliteStore):
        self._type = type
        self._connection: SqliteStore = connection
        self._dict: OrderedDict[str, Download] = OrderedDict()

    async def load(self) -> None:
        saved = await self._connection.fetch_saved(str(self._type))
        for key, item in saved:
            self._dict[key] = Download(info=item)

    async def saved_items(self) -> list[tuple[str, ItemDTO]]:
        return await self._connection.fetch_saved(str(self._type))

    async def exists(self, key: str | None = None, url: str | None = None) -> bool:
        if not key and not url:
            msg = "key or url must be provided."
            raise KeyError(msg)

        if key and key in self._dict:
            return True

        if any((key and self._dict[i].info._id == key) or (url and self._dict[i].info.url == url) for i in self._dict):
            return True

        return StoreType.HISTORY == self._type and await self._connection.exists(str(self._type), key=key, url=url)

    async def get(self, key: str | None = None, url: str | None = None) -> Download:
        if not key and not url:
            msg = "key or url must be provided."
            raise KeyError(msg)

        for i in self._dict:
            if (key and self._dict[i].info._id == key) or (url and self._dict[i].info.url == url):
                return self._dict[i]

        if StoreType.HISTORY == self._type and (item := await self._connection.get(str(self._type), key=key, url=url)):
            self._dict[item._id] = Download(info=item)
            return self._dict[item._id]

        msg: str = f"{key=} or {url=} not found."
        raise KeyError(msg)

    async def get_item(self, **kwargs) -> Download | None:
        if not kwargs:
            return None

        for i in self._dict:
            if not self._dict[i].info:
                continue

            info = self._dict[i].info.__dict__

            if any(matches_condition(key, value, info) for key, value in kwargs.items()):
                return self._dict[i]

        if StoreType.HISTORY == self._type and (item := await self._connection.get_item(str(self._type), **kwargs)):
            self._dict[item._id] = Download(info=item)
            return self._dict[item._id]

        return None

    async def get_by_id(self, id: str) -> Download | None:
        val = self._dict.get(id)
        if val or self._type == StoreType.QUEUE:
            return val

        if item := await self._connection.get_by_id(str(self._type), id):
            self._dict[item._id] = Download(info=item)
            return self._dict[id]

        return None

    async def get_many_by_ids(self, ids: Iterable[str]) -> list[tuple[str, Download]]:
        ids_list = list(ids)
        if not ids_list:
            return []

        items: list[tuple[str, Download]] = []
        missing_ids: list[str] = []

        for item_id in ids_list:
            cached = self._dict.get(item_id)
            if cached:
                items.append((item_id, cached))
                continue
            missing_ids.append(item_id)

        if StoreType.HISTORY == self._type and missing_ids:
            loaded = await self._connection.get_many_by_ids(str(self._type), missing_ids)
            for item_id, item in loaded:
                self._dict[item_id] = Download(info=item)

        items.extend((item_id, download) for item_id in ids_list if (download := self._dict.get(item_id)))

        seen: set[str] = set()
        ordered: list[tuple[str, Download]] = []
        for item_id, download in items:
            if item_id in seen:
                continue
            seen.add(item_id)
            ordered.append((item_id, download))
        return ordered

    async def get_many_by_status(self, status_filter: str) -> list[tuple[str, Download]]:
        if StoreType.HISTORY != self._type:
            return []

        items = await self._connection.get_many_by_status(str(self._type), status_filter)
        downloads: list[tuple[str, Download]] = []
        for item_id, item in items:
            self._dict[item_id] = Download(info=item)
            downloads.append((item_id, self._dict[item_id]))
        return downloads

    def items(self):
        return self._dict.items()

    async def put(self, value: Download, no_notify: bool = False) -> Download:
        _ = no_notify
        self._dict[value.info._id] = value
        await self._connection.enqueue_upsert(str(self._type), _strip_transient_fields(value.info))
        return self._dict[value.info._id]

    async def delete(self, key: str) -> None:
        self._dict.pop(key, None)
        await self._connection.enqueue_delete(str(self._type), key)

    def next(self):
        return next(iter(self._dict.items()))

    def empty(self) -> bool:
        return 0 == len(self._dict)

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
    ) -> tuple[list[tuple[str, Download]], int, int, int]:
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

        items, total_items, current_page, total_pages = await self._connection.paginate(
            str(self._type), page, per_page, order, status_filter
        )

        return [(item_id, Download(info=item)) for item_id, item in items], total_items, current_page, total_pages

    async def bulk_delete(self, ids: Iterable[str]) -> int:
        ids_list = list(ids)
        deleted = await self._connection.bulk_delete(str(self._type), ids_list)
        for _id in ids_list:
            self._dict.pop(_id, None)
        return deleted

    async def bulk_delete_by_status(self, status_filter: str) -> int:
        deleted = await self._connection.bulk_delete_by_status(str(self._type), status_filter)
        if deleted > 0:
            self._drop_cached_by_status(status_filter)
        return deleted

    def _drop_cached_by_status(self, status_filter: str) -> None:
        raw_statuses = [entry.strip() for entry in status_filter.split(",") if entry.strip()]
        if not raw_statuses:
            return

        if all(entry.startswith("!") for entry in raw_statuses):
            excluded = {entry[1:].strip() for entry in raw_statuses if entry[1:].strip()}
            if not excluded:
                return

            for item_id, download in list(self._dict.items()):
                if download.info and download.info.status not in excluded:
                    self._dict.pop(item_id, None)
            return

        included = {entry for entry in raw_statuses if not entry.startswith("!")}
        if not included:
            return

        for item_id, download in list(self._dict.items()):
            if download.info and download.info.status in included:
                self._dict.pop(item_id, None)

    async def test(self) -> bool:
        await self._connection.count(str(self._type))
        return True
