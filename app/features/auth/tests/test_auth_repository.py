from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.features.auth.repository import AuthRepository
from app.library.sqlite_store import SqliteStore
from app.tests.helpers import make_in_memory_db_path

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest_asyncio.fixture
async def repo() -> AsyncIterator[AuthRepository]:
    AuthRepository._reset_singleton()
    SqliteStore._reset_singleton()
    store = SqliteStore(db_path=make_in_memory_db_path("auth-repository"))
    await store.get_connection()
    repository = AuthRepository.get_instance()
    yield repository
    await store.close()
    AuthRepository._reset_singleton()
    SqliteStore._reset_singleton()


@pytest.mark.asyncio
async def test_empty_user_creation(repo: AuthRepository) -> None:
    owner = await repo.create_user("owner", "hash", require_empty=True)
    blocked = await repo.create_user("blocked", "hash", require_empty=True)
    duplicate = await repo.create_user("owner", "hash")

    assert owner is not None
    assert blocked is None
    assert duplicate is None


@pytest.mark.asyncio
async def test_key_owner_scope(repo: AuthRepository) -> None:
    owner = await repo.create_user("owner", "hash")
    other = await repo.create_user("other", "hash")
    assert owner is not None and other is not None
    key = await repo.create_key(owner.id, "browser", "digest", "hint")

    match = await repo.user_from_key("digest")
    assert match is not None
    assert match[0].id == owner.id
    assert (await repo.keys(owner.id))[0].last_used_at is not None
    assert await repo.delete_key(other.id, key.id) is False
    assert await repo.delete_key(owner.id, key.id) is True
