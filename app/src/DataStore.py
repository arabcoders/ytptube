from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import formatdate
import json
import logging
import sqlite3
from src.Utils import calcDownloadPath
from src.Config import Config
from src.Download import Download
from src.DTO.ItemDTO import ItemDTO


class DataStore:
    """
    Persistent queue using shelve.
    """
    type: str = None
    db_file: str = None
    dict: OrderedDict[str, Download] = None
    config: Config = None

    def __init__(self, type: str, config: Config):
        self.dict = OrderedDict()
        self.type = type
        self.config = config
        self.db_file = self.config.db_file

    def load(self) -> None:
        for id, item in self.saved_items():
            self.dict[id] = Download(
                info=item,
                download_dir=calcDownloadPath(
                    basePath=self.config.download_path,
                    folder=item.folder
                ),
                temp_dir=self.config.temp_path,
                output_template_chapter=self.config.output_template_chapter,
                default_ytdl_opts=self.config.ytdl_options,
            )

    def exists(self, key: str) -> bool:
        return key in self.dict

    def get(self, key: str) -> Download:
        return self.dict[key]

    def items(self) -> list[tuple[str, Download]]:
        return self.dict.items()

    def saved_items(self) -> list[tuple[str, ItemDTO]]:
        items: list[tuple[str, ItemDTO]] = []
        with sqlite3.connect(self.db_file) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute(
                f'SELECT "id", "data", "created_at" FROM "history" WHERE "type" = ? ORDER BY "created_at" ASC',
                (self.type,)
            )

            for row in cursor:
                data: dict = json.loads(row['data'])
                key: str = data.pop('_id')
                item: ItemDTO = ItemDTO(**data)
                item._id = key
                item.datetime = formatdate(datetime.strptime(
                    row['created_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()
                )
                items.append((row['id'], item))

        return items

    def put(self, value: Download) -> None:
        _id: str = value.info._id
        self.dict[_id] = value
        self._updateStoreItem(self.type, value.info)

    def delete(self, key: str) -> None:
        if not key in self.dict:
            return

        del self.dict[key]
        self._deleteStoreItem(key)

    def next(self) -> tuple[str, Download]:
        return next(iter(self.dict.items()))

    def empty(self):
        return not bool(self.dict)

    def _updateStoreItem(self, type: str, item: ItemDTO) -> None:
        sqlStatement = """
        INSERT INTO "history" ("id", "type", "url", "data")
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO UPDATE SET "type" = ?, "url" = ?, "data" = ?
        """

        if hasattr(item, 'datetime'):
            try:
                delattr(item, 'datetime')
            except AttributeError:
                pass

        with sqlite3.connect(self.db_file) as db:
            db.execute(sqlStatement.strip(), (
                item._id,
                type,
                item.url,
                item.json(),
                type,
                item.url,
                item.json(),
            ))

    def _deleteStoreItem(self, key: str) -> None:
        with sqlite3.connect(self.db_file) as db:
            db.execute(
                'DELETE FROM "history" WHERE "type" = ? AND "id" = ?',
                (self.type, key,)
            )
