import copy
import json
from collections import OrderedDict
from datetime import UTC, datetime
from email.utils import formatdate
from sqlite3 import Connection

from .config import Config
from .Download import Download
from .ItemDTO import ItemDTO
from .Utils import clean_item


class DataStore:
    """
    Persistent queue.
    """

    type: str = None
    dict: OrderedDict[str, Download] = None
    config: Config = None

    connection: Connection

    def __init__(self, type: str, connection: Connection):
        self.dict = OrderedDict()
        self.type = type
        self.config = Config.get_instance()
        self.connection = connection

    def load(self) -> None:
        for id, item in self.saved_items():
            self.dict.update({id: Download(info=item)})

    def exists(self, key: str | None = None, url: str | None = None) -> bool:
        if not key and not url:
            msg = "key or url must be provided."
            raise KeyError(msg)

        if key and key in self.dict:
            return True

        return any((key and self.dict[i].info._id == key) or (url and self.dict[i].info.url == url) for i in self.dict)

    def get(self, key: str, url: str | None = None) -> Download:
        if not key and not url:
            msg = "key or url must be provided."
            raise KeyError(msg)

        for i in self.dict:
            if (key and self.dict[i].info._id == key) or (url and self.dict[i].info.url == url):
                return self.dict[i]

        msg = f"{key=} or {url=} not found."
        raise KeyError(msg)

    def get_by_id(self, id: str) -> Download | None:
        return self.dict.get(id, None)

    def items(self) -> list[tuple[str, Download]]:
        return self.dict.items()

    def saved_items(self) -> list[tuple[str, ItemDTO]]:
        items: list[tuple[str, ItemDTO]] = []

        cursor = self.connection.execute(
            'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = ? ORDER BY "created_at" ASC', (self.type,)
        )

        for row in cursor:
            rowDate = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
            data, _ = clean_item(json.loads(row["data"]), keys=ItemDTO.removed_fields())
            data.pop("_id", None)
            item: ItemDTO = ItemDTO(**data)
            item._id = row["id"]
            item.datetime = formatdate(rowDate.replace(tzinfo=UTC).timestamp())
            items.append((row["id"], item))

        return items

    def put(self, value: Download) -> Download:
        self.dict.update({value.info._id: value})
        self._update_store_item(self.type, value.info)

        return self.dict[value.info._id]

    def delete(self, key: str) -> None:
        self.dict.pop(key, None)
        self._delete_store_item(key)

    def next(self) -> tuple[str, Download]:
        return next(iter(self.dict.items()))

    def empty(self):
        return not bool(self.dict)

    def has_downloads(self):
        if 0 == len(self.dict):
            return False

        return any(self.dict[key].started() is False for key in self.dict)

    def get_next_download(self) -> Download:
        for key in self.dict:
            if self.dict[key].started() is False and self.dict[key].is_cancelled() is False:
                return self.dict[key]

        return None

    async def test(self) -> bool:
        self.connection.execute('SELECT "id" FROM "history" LIMIT 1').fetchone()
        return True

    def _update_store_item(self, type: str, item: ItemDTO) -> None:
        sqlStatement = """
        INSERT INTO "history" ("id", "type", "url", "data")
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO UPDATE SET "type" = ?, "url" = ?, "data" = ?, created_at = ?
        """

        stored = copy.deepcopy(item)

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

        self.connection.execute(
            sqlStatement.strip(),
            (
                stored._id,
                type,
                stored.url,
                stored.json(),
                type,
                stored.url,
                stored.json(),
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    def _delete_store_item(self, key: str) -> None:
        self.connection.execute(
            'DELETE FROM "history" WHERE "type" = ? AND "id" = ?',
            (
                self.type,
                key,
            ),
        )
