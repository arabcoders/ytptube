from collections import OrderedDict
import copy
from datetime import datetime, timezone
from email.utils import formatdate
import json
import sqlite3
from Utils import calcDownloadPath
from Config import Config
from Download import Download
from ItemDTO import ItemDTO


class DataStore:
    """
    Persistent queue.
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
            self.dict.update({id: Download(
                info=item,
                download_dir=calcDownloadPath(
                    basePath=self.config.download_path,
                    folder=item.folder
                ),
                temp_dir=self.config.temp_path,
                output_template_chapter=self.config.output_template_chapter,
                default_ytdl_opts=self.config.ytdl_options)
            })

    def exists(self, key: str = None, url: str = None) -> bool:
        if not key and not url:
            raise KeyError('key or url must be provided')

        if key and key in self.dict:
            return True

        for i in self.dict:
            if (key and self.dict[i].info._id == key) or (url and self.dict[i].info.url == url):
                return True

        return False

    def get(self, key: str, url: str = None) -> Download:
        if not key and not url:
            raise KeyError('key or url must be provided.')

        for i in self.dict:
            if (key and self.dict[i].info._id == key) or (url and self.dict[i].info.url == url):
                return self.dict[i]

        raise KeyError(f'{key=} or {url=} not found.')

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

    def put(self, value: Download) -> Download:
        # for key in self.dict:
        #     if self.dict[key].info.url == value.info.url:
        #         value.info._id = key
        #         return

        self.dict.update({value.info._id: value})
        self._updateStoreItem(self.type, value.info)

        return self.dict[value.info._id]

    def delete(self, key: str) -> None:
        self.dict.pop(key, None)
        self._deleteStoreItem(key)

    def next(self) -> tuple[str, Download]:
        return next(iter(self.dict.items()))

    def empty(self):
        return not bool(self.dict)

    def hasDownloads(self):
        if 0 == len(self.dict):
            return False

        for key in self.dict:
            if self.dict[key].started() is False:
                return True

        return False

    def getNextDownload(self) -> Download:
        for key in self.dict:
            if self.dict[key].started() is False and self.dict[key].is_canceled() is False:
                return self.dict[key]

        return None

    def _updateStoreItem(self, type: str, item: ItemDTO) -> None:
        sqlStatement = """
        INSERT INTO "history" ("id", "type", "url", "data")
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO UPDATE SET "type" = ?, "url" = ?, "data" = ?, created_at = ?
        """

        stored = copy.deepcopy(item)

        if hasattr(stored, 'datetime'):
            try:
                delattr(stored, 'datetime')
            except AttributeError:
                pass

        if hasattr(stored, 'live_in') and stored.status == 'finished':
            try:
                delattr(stored, 'live_in')
            except AttributeError:
                pass

        with sqlite3.connect(self.db_file) as db:
            db.execute(sqlStatement.strip(), (
                stored._id,
                type,
                stored.url,
                stored.json(),
                type,
                stored.url,
                stored.json(),
                datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            ))

    def _deleteStoreItem(self, key: str) -> None:
        with sqlite3.connect(self.db_file) as db:
            db.execute(
                'DELETE FROM "history" WHERE "type" = ? AND "id" = ?',
                (self.type, key,)
            )
