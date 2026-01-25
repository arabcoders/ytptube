from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.library.sqlite_store import SqliteStore


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    async with SqliteStore.get_instance().sessionmaker()() as session:
        yield session
