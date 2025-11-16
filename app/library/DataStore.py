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
from .operations import matches_condition
from .Utils import init_class

LOG: logging.Logger = logging.getLogger("datastore")


class StoreType(str, Enum):
    HISTORY: str = "done"
    QUEUE: str = "queue"

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

    def __init__(self, type: StoreType, connection: Connection):
        self._dict: OrderedDict[str, Download] = OrderedDict()
        "The dictionary of items."
        self._type: StoreType = type
        "The type of the datastore."
        self._connection: Connection = connection
        "The database connection."

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

    def get_item(self, **kwargs) -> Download | None:
        """
        Get a specific item from the datastore based on provided attributes with optional operations.

        Args:
            **kwargs: Arbitrary keyword arguments representing attributes of the ItemDTO.
                Each value can be either:
                - A direct value (defaults to EQUAL operation): {"title": "test"}
                - A tuple of (Operation, value): {"title": (Operation.CONTAIN, "test")}

                If no attributes are provided, the method returns None.
                If any attribute matches, the corresponding Download object is returned.

        Returns:
            Download | None: The requested item if found, otherwise None.

        Examples:
            # Direct equality check (default)
            store.get_item(title="Video 1")

            # Using operations
            store.get_item(title=(Operation.CONTAIN, "test"))
            store.get_item(id=(Operation.EQUAL, "123"), status=(Operation.NOT_EQUAL, "error"))

            # Mixed usage
            store.get_item(title=(Operation.CONTAIN, "test"), folder="downloads")

        """
        if not kwargs:
            return None

        for i in self._dict:
            if not self._dict[i].info:
                continue

            info = self._dict[i].info.__dict__
            if any(matches_condition(key, value, info) for key, value in kwargs.items()):
                return self._dict[i]

        return None

    def get_by_id(self, id: str) -> Download | None:
        return self._dict.get(id, None)

    def items(self) -> OrderedDict[tuple[str, Download]]:
        return self._dict.items()

    def saved_items(self) -> list[tuple[str, ItemDTO]]:
        items: list[tuple[str, ItemDTO]] = []

        cursor = self._connection.execute(
            'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = ? ORDER BY "created_at" ASC',
            (str(self._type),),
        )

        for row in cursor:
            rowDate: datetime = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
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

            EventBus.get_instance().emit(Events.ITEM_ERROR, value.info)

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

    def get_total_count(self) -> int:
        """
        Get the total count of items in the datastore.

        Returns:
            int: The total number of items in the datastore.

        """
        cursor = self._connection.execute(
            'SELECT COUNT(*) as count FROM "history" WHERE "type" = ?',
            (str(self._type),),
        )
        row = cursor.fetchone()
        return row["count"] if row else 0

    def get_items_paginated(
        self,
        page: int = 1,
        per_page: int = 50,
        order: str = "DESC",
        status_filter: str | None = None,
    ) -> tuple[list[tuple[str, ItemDTO]], int, int, int]:
        """
        Get paginated items from the datastore.

        Args:
            page (int): The page number (1-indexed). Defaults to 1.
            per_page (int): Number of items per page. Defaults to 50.
            order (str): Sort order - 'ASC' or 'DESC'. Defaults to 'DESC' (newest first).
            status_filter (str | None): Optional status filter. Can be a status value (e.g., 'finished')
                to include only that status, or prefixed with '!' (e.g., '!finished') to exclude that status.

        Returns:
            tuple[list[tuple[str, ItemDTO]], int, int, int]: A tuple containing:
                - List of (id, ItemDTO) tuples for the requested page
                - Total number of items
                - Current page number
                - Total number of pages

        Raises:
            ValueError: If page < 1 or per_page < 1

        """
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

        order = "ASC" if order == "ASC" else "DESC"

        # Build SQL query with status filter if provided
        where_clauses = ['"type" = ?']
        query_params: list = [str(self._type)]

        if status_filter:
            # Check if it's an exclusion filter (starts with !)
            if status_filter.startswith("!"):
                status_value = status_filter[1:]
                where_clauses.append("json_extract(data, '$.status') != ?")
                query_params.append(status_value)
            else:
                where_clauses.append("json_extract(data, '$.status') = ?")
                query_params.append(status_filter)

        where_clause = " AND ".join(where_clauses)

        # Get total count with filter
        count_query = f'SELECT COUNT(*) as count FROM "history" WHERE {where_clause}'  # noqa: S608
        count_result = self._connection.execute(count_query, tuple(query_params)).fetchone()
        total_items: int = count_result["count"] if count_result else 0
        total_pages: int = (total_items + per_page - 1) // per_page if total_items > 0 else 1

        # Ensure page is within valid range.
        if page > total_pages and total_items > 0:
            page = total_pages

        offset = (page - 1) * per_page

        items: list[tuple[str, ItemDTO]] = []

        query_params.extend([per_page, offset])

        cursor = self._connection.execute(
            f'SELECT "id", "data", "created_at" FROM "history" WHERE {where_clause} ORDER BY "created_at" {order} LIMIT ? OFFSET ?',  # noqa: S608
            tuple(query_params),
        )

        for row in cursor:
            rowDate: datetime = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
            data: dict = json.loads(row["data"])
            data.pop("_id", None)
            item: ItemDTO = init_class(ItemDTO, data)
            item._id = row["id"]
            item.datetime = formatdate(rowDate.replace(tzinfo=UTC).timestamp())
            items.append((row["id"], item))

        return items, total_items, page, total_pages

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
