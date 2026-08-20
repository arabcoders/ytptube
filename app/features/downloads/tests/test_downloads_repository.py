from __future__ import annotations

from datetime import UTC, datetime
from collections.abc import AsyncGenerator
from email.utils import formatdate

import pytest
import pytest_asyncio

from app.features.downloads.repository import DownloadsRepository
from app.library.DataStore import StoreType
from app.library.ItemDTO import ItemDTO
from app.library.sqlite_store import SqliteStore


@pytest_asyncio.fixture
async def repository() -> AsyncGenerator[DownloadsRepository, None]:
    SqliteStore._reset_singleton()
    DownloadsRepository._reset_singleton()
    store = SqliteStore.get_instance(db_path=":memory:downloads-tests")
    await store.get_connection()
    repository = DownloadsRepository(session=lambda: store.sessionmaker()())
    yield repository
    await repository.shutdown()
    await store.close()
    SqliteStore._reset_singleton()
    DownloadsRepository._reset_singleton()


def make_item(url: str, position: int | None = None) -> ItemDTO:
    return ItemDTO(id=url, title=url, url=url, folder="", queue_position=position)


@pytest.mark.asyncio
async def test_round_trip(repository: DownloadsRepository) -> None:
    item = make_item("https://example.test/item")
    model = item.to_download_model(StoreType.HISTORY.value)
    assert "datetime" not in model.data
    await repository.enqueue_upsert(StoreType.HISTORY.value, model)
    await repository.flush()

    loaded = await repository.get(StoreType.HISTORY.value, url=item.url)
    assert loaded is not None
    assert loaded._id == item._id
    assert loaded.datetime == formatdate(model.created_at.timestamp())


@pytest.mark.asyncio
async def test_queue_order(repository: DownloadsRepository) -> None:
    first = make_item("https://example.test/first", 2)
    second = make_item("https://example.test/second", 1)
    old = make_item("https://example.test/old")
    for item in (first, second, old):
        model = item.to_download_model(StoreType.QUEUE.value)
        model.created_at = datetime.now(UTC)
        await repository.enqueue_upsert(StoreType.QUEUE.value, model)
    await repository.flush()

    saved = await repository.fetch_saved(StoreType.QUEUE.value)
    assert [item.url for _, item in saved] == [second.url, first.url, old.url]


@pytest.mark.asyncio
async def test_crud_filters(repository: DownloadsRepository) -> None:
    items = [make_item(f"https://example.test/{index}") for index in range(3)]
    for item in items:
        item.status = "finished" if item.id != items[2].id else "pending"
        await repository.enqueue_upsert(StoreType.HISTORY.value, item.to_download_model(StoreType.HISTORY.value))
    await repository.flush()

    assert await repository.exists(StoreType.HISTORY.value, key=items[0]._id)
    loaded = await repository.get_many_by_ids(StoreType.HISTORY.value, [items[2]._id, items[0]._id])
    assert [item_id for item_id, _ in loaded] == [items[2]._id, items[0]._id]
    assert len(await repository.get_many_by_status(StoreType.HISTORY.value, "finished")) == 2
    assert len(await repository.get_many_by_status(StoreType.HISTORY.value, "!finished")) == 1


@pytest.mark.asyncio
async def test_conditions_pages(repository: DownloadsRepository) -> None:
    for index in range(5):
        item = make_item(f"https://example.test/{index}")
        item.title = f"Video {index}"
        await repository.enqueue_upsert(StoreType.HISTORY.value, item.to_download_model(StoreType.HISTORY.value))
    await repository.flush()

    match = await repository.get_item(StoreType.HISTORY.value, title=("in", "Video"), missing="x")
    assert match is not None and match.title == "Video 0"
    items, total, page, pages = await repository.paginate(StoreType.HISTORY.value, 99, 2, "DESC")
    assert len(items) == 1 and total == 5 and page == 3 and pages == 3


@pytest.mark.asyncio
async def test_url_conflict(repository: DownloadsRepository) -> None:
    first = make_item("https://example.test/same")
    second = make_item(first.url)
    await repository.enqueue_upsert(StoreType.HISTORY.value, first.to_download_model(StoreType.HISTORY.value))
    await repository.flush()
    await repository.enqueue_upsert(StoreType.HISTORY.value, second.to_download_model(StoreType.HISTORY.value))
    await repository.flush()

    loaded = await repository.get(StoreType.HISTORY.value, url=first.url)
    assert loaded is not None and loaded._id == first._id


@pytest.mark.asyncio
async def test_delete_writes(repository: DownloadsRepository) -> None:
    items = [make_item(f"https://example.test/delete/{index}") for index in range(3)]
    for item in items:
        await repository.enqueue_upsert(StoreType.QUEUE.value, item.to_download_model(StoreType.QUEUE.value))
    await repository.flush()
    await repository.enqueue_delete(StoreType.QUEUE.value, items[0]._id)
    assert await repository.bulk_delete(StoreType.QUEUE.value, [items[1]._id]) == 1
    assert [key for key, _ in await repository.fetch_saved(StoreType.QUEUE.value)] == [items[2]._id]


@pytest.mark.asyncio
async def test_pagination_order(repository: DownloadsRepository) -> None:
    for index in range(7):
        item = make_item(f"https://example.test/page/{index}")
        model = item.to_download_model(StoreType.HISTORY.value)
        model.created_at = datetime(2024, 1, 1, 0, index, tzinfo=UTC)
        await repository.enqueue_upsert(StoreType.HISTORY.value, model)
    await repository.flush()
    items, total, page, pages = await repository.paginate(StoreType.HISTORY.value, 10, 3, "DESC")
    assert len(items) == 1 and total == 7 and page == 3 and pages == 3


@pytest.mark.asyncio
async def test_operation_fallback(repository: DownloadsRepository) -> None:
    item = make_item("https://example.test/operation")
    item.title = "A title"
    await repository.enqueue_upsert(StoreType.HISTORY.value, item.to_download_model(StoreType.HISTORY.value))
    await repository.flush()
    assert await repository.get_item(StoreType.HISTORY.value, title=("invalid", "A title")) is not None
    assert await repository.get_item(StoreType.HISTORY.value, **{"bad.key": "A title"}) is None


@pytest.mark.asyncio
async def test_status_delete(repository: DownloadsRepository) -> None:
    for status in ("finished", "pending", "skip"):
        item = make_item(f"https://example.test/status/{status}")
        item.status = status
        await repository.enqueue_upsert(StoreType.HISTORY.value, item.to_download_model(StoreType.HISTORY.value))
    await repository.flush()
    assert await repository.bulk_delete_by_status(StoreType.HISTORY.value, "finished,skip") == 2
    assert await repository.count(StoreType.HISTORY.value) == 1


@pytest.mark.asyncio
async def test_id_lookup(repository: DownloadsRepository) -> None:
    item = make_item("https://example.test/id")
    await repository.enqueue_upsert(StoreType.QUEUE.value, item.to_download_model(StoreType.QUEUE.value))
    await repository.flush()
    loaded = await repository.get_by_id(StoreType.QUEUE.value, item._id)
    assert loaded is not None and loaded._id == item._id


@pytest.mark.asyncio
async def test_lookup_requires_key(repository: DownloadsRepository) -> None:
    with pytest.raises(KeyError):
        await repository.get(StoreType.QUEUE.value)


@pytest.mark.asyncio
async def test_missing_item(repository: DownloadsRepository) -> None:
    assert await repository.get_item(StoreType.HISTORY.value, title="missing") is None


@pytest.mark.asyncio
async def test_store_separation(repository: DownloadsRepository) -> None:
    item = make_item("https://example.test/separate")
    await repository.enqueue_upsert(StoreType.QUEUE.value, item.to_download_model(StoreType.QUEUE.value))
    await repository.flush()
    assert await repository.get(StoreType.HISTORY.value, url=item.url) is None
    assert await repository.get(StoreType.QUEUE.value, url=item.url) is not None


@pytest.mark.asyncio
async def test_negative_statuses(repository: DownloadsRepository) -> None:
    for status in ("one", "two", "three"):
        item = make_item(f"https://example.test/negative/{status}")
        item.status = status
        await repository.enqueue_upsert(StoreType.HISTORY.value, item.to_download_model(StoreType.HISTORY.value))
    await repository.flush()
    assert len(await repository.get_many_by_status(StoreType.HISTORY.value, "!one,!two")) == 1


@pytest.mark.asyncio
async def test_bulk_ids(repository: DownloadsRepository) -> None:
    item = make_item("https://example.test/bulk")
    await repository.enqueue_upsert(StoreType.HISTORY.value, item.to_download_model(StoreType.HISTORY.value))
    await repository.flush()
    assert await repository.bulk_delete(StoreType.HISTORY.value, [item._id, "missing"]) == 1


@pytest.mark.asyncio
async def test_shutdown_drains(repository: DownloadsRepository) -> None:
    item = make_item("https://example.test/shutdown")
    await repository.enqueue_upsert(StoreType.QUEUE.value, item.to_download_model(StoreType.QUEUE.value))
    await repository.shutdown()
    assert repository._queue is None


@pytest.mark.asyncio
async def test_unknown_operation(repository: DownloadsRepository) -> None:
    item = make_item("https://example.test/unknown")
    await repository.enqueue_upsert(StoreType.HISTORY.value, item.to_download_model(StoreType.HISTORY.value))
    await repository.flush()
    assert await repository.get_item(StoreType.HISTORY.value, url=("bad", item.url)) is not None


@pytest.mark.asyncio
async def test_empty_ids(repository: DownloadsRepository) -> None:
    assert await repository.get_many_by_ids(StoreType.HISTORY.value, []) == []
    assert await repository.bulk_delete(StoreType.HISTORY.value, []) == 0
