import asyncio
import copy
import json
import logging
from collections import OrderedDict
from datetime import UTC, datetime
from email.utils import formatdate
from enum import Enum
from sqlite3 import Connection

from .Download import Download
from .ItemDTO import ItemDTO
from .Utils import init_class

LOG = logging.getLogger("datastore")


class StoreType(str, Enum):
    HISTORY = "done"
    QUEUE = "queue"

    @classmethod
    def all(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def from_value(cls, value: str) -> "StoreType":
        """
        Returns the StoreType enum member corresponding to the given value.

        Args:
            value (str): The value to match against the enum members.

        Returns:
            StoreType: The enum member that matches the value.

        Raises:
            ValueError: If the value does not match any member.

        """
        for member in cls:
            if member.value == value:
                return member

        msg = f"Invalid StoreType value: {value}"
        raise ValueError(msg)

    def __str__(self) -> str:
        return self.value


class DataStore:
    """
    Persistent queue.
    """

    _type: StoreType = None
    """Type of the store, e.g., DONE, QUEUE, PENDING."""

    _dict: OrderedDict[str, Download] = None
    """Ordered dictionary to store Download objects."""

    _connection: Connection
    """SQLite connection to the database."""

    def __init__(self, type: StoreType, connection: Connection):
        self._dict = OrderedDict()
        self._type = type
        self._connection = connection

    def load(self) -> None:
        for id, item in self.saved_items():
            self._dict.update({id: Download(info=item)})

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

    def get_by_id(self, id: str) -> Download | None:
        return self._dict.get(id, None)

    def items(self) -> list[tuple[str, Download]]:
        return self._dict.items()

    def saved_items(self) -> list[tuple[str, ItemDTO]]:
        items: list[tuple[str, ItemDTO]] = []

        cursor = self._connection.execute(
            'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = ? ORDER BY "created_at" ASC',
            (str(self._type),),
        )

        for row in cursor:
            rowDate = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
            data: dict = json.loads(row["data"])
            data.pop("_id", None)
            item: ItemDTO = init_class(ItemDTO, data)
            item._id = row["id"]
            item.datetime = formatdate(rowDate.replace(tzinfo=UTC).timestamp())
            items.append((row["id"], item))

        return items

    def put(self, value: Download, no_notify: bool = False) -> Download:
        if "error" == value.info.status and not no_notify:
            from app.library.Events import EventBus, Events

            asyncio.create_task(EventBus.get_instance().emit(Events.ITEM_ERROR, value.info), name="emit_item_error")

        self._dict.update({value.info._id: value})
        self._update_store_item(self._type, value.info)

        return self._dict[value.info._id]

    def delete(self, key: str) -> None:
        self._dict.pop(key, None)
        self._delete_store_item(key)

    def next(self) -> tuple[str, Download]:
        return next(iter(self._dict.items()))

    def empty(self):
        return not bool(self._dict)

    def has_downloads(self):
        if 0 == len(self._dict):
            return False

        return any(self._dict[key].info.auto_start and self._dict[key].started() is False for key in self._dict)

    def get_next_download(self) -> Download:
        for key in self._dict:
            ref = self._dict[key]
            if ref.info.auto_start and ref.started() is False and ref.is_cancelled() is False:
                return ref

        return None

    async def test(self) -> bool:
        self._connection.execute('SELECT "id" FROM "history" LIMIT 1').fetchone()
        return True

    def _update_store_item(self, type: StoreType, item: ItemDTO) -> None:
        sqlStatement = """
        INSERT INTO "history" ("id", "type", "url", "data")
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO UPDATE SET "type" = ?, "url" = ?, "data" = ?, created_at = ?
        """

        stored: ItemDTO = copy.deepcopy(item)

        if hasattr(stored, "datetime"):
            try:
                delattr(stored, "datetime")
            except AttributeError:
                pass

        if hasattr(stored, "live_in") and stored.status == "finished":
            try:
                delattr(stored, "live_in")
            except AttributeError:
                pass

        encoded: str = stored.json()

        self._connection.execute(
            sqlStatement.strip(),
            (
                stored._id,
                str(type),
                stored.url,
                encoded,
                str(type),
                stored.url,
                encoded,
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    def _delete_store_item(self, key: str) -> None:
        self._connection.execute('DELETE FROM "history" WHERE "type" = ? AND "id" = ?', (str(self._type), key))
