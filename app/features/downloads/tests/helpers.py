from __future__ import annotations

from typing import Any

from app.features.downloads.repository import DownloadsRepository
from app.library.sqlite_store import SqliteStore


class RepositoryDatabase:
    def __init__(self, store: SqliteStore, repository: DownloadsRepository) -> None:
        self._store = store
        self._repository = repository

    def __getattr__(self, name: str) -> Any:
        return getattr(self._repository, name)

    @property
    def _conn(self):
        return self._store._conn

    async def execute_raw(self, query: str, params: dict | tuple | None = None) -> None:
        await self._store.execute_raw(query, params)

    async def fetch_raw(self, query: str, params: dict | tuple | None = None):
        return await self._store.fetch_raw(query, params)

    async def close(self) -> None:
        await self._repository.shutdown()
        await self._store.close()
