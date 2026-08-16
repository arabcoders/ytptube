from __future__ import annotations

import pytest
import pytest_asyncio

from app.features.tasks import router
from app.features.tasks.definitions.results import TaskFailure, TaskResult
from app.features.tasks.repository import TasksRepository
from app.library.encoder import Encoder
from app.library.sqlite_store import SqliteStore
from app.tests.helpers import make_in_memory_db_path, url_for


@pytest_asyncio.fixture
async def repo():
    TasksRepository._reset_singleton()
    SqliteStore._reset_singleton()

    store = SqliteStore(db_path=make_in_memory_db_path("tasks-router"))
    await store.get_connection()

    repository = TasksRepository.get_instance()

    yield repository

    await store.close()
    TasksRepository._reset_singleton()
    SqliteStore._reset_singleton()


@pytest.fixture(autouse=True)
def patch_get_info(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_get_info(_url: str, _preset: str) -> tuple[None, None]:
        return (None, None)

    monkeypatch.setattr(router, "_get_info", _fake_get_info)


class _Notify:
    def emit(self, *_args, **_kwargs) -> None:
        return None


class _Handler:
    def __init__(self, matched: bool | dict[str, bool]) -> None:
        self._matched = matched

    async def inspect(self, *, url: str, preset: str | None = None, static_only: bool = False, **_kwargs):
        del preset, static_only

        if isinstance(self._matched, dict):
            matched = self._matched.get(url, False)
        else:
            matched = self._matched

        if matched:
            return TaskResult(metadata={"matched": True, "handler": "TestHandler"})

        return TaskFailure(message="No handler", metadata={"matched": False, "handler": None})


@pytest.mark.asyncio
async def test_add_requires_timer(repo, test_client) -> None:
    async def handler(request):
        return await router.tasks_add(request, repo, Encoder(), _Notify(), _Handler(matched=False))

    client = await test_client({"tasks_add": handler})
    response = await client.post(url_for("tasks_add"), json={"name": "No Timer", "url": "https://example.com/channel"})

    assert response.status == 400
    assert "requires a timer" in await response.text()
    assert await repo.all() == []


@pytest.mark.asyncio
async def test_add_all_or_nothing(repo, test_client) -> None:
    async def handler(request):
        return await router.tasks_add(
            request,
            repo,
            Encoder(),
            _Notify(),
            _Handler({"https://example.com/first": True, "https://example.com/second": False}),
        )

    client = await test_client({"tasks_add": handler})
    response = await client.post(
        url_for("tasks_add"),
        json=[
            {"name": "First", "url": "https://example.com/first"},
            {"url": "https://example.com/second"},
        ],
    )

    assert response.status == 400
    assert "requires a timer" in await response.text()
    assert await repo.all() == []


@pytest.mark.asyncio
async def test_add_allows_handler_only(repo, test_client) -> None:
    async def handler(request):
        return await router.tasks_add(request, repo, Encoder(), _Notify(), _Handler(matched=True))

    client = await test_client({"tasks_add": handler})
    response = await client.post(url_for("tasks_add"), json={"name": "Handler Only", "url": "https://example.com/feed"})

    assert response.status == 200
    items = await repo.all()
    assert len(items) == 1
    assert items[0].name == "Handler Only"


@pytest.mark.asyncio
async def test_update_requires_timer(repo, test_client) -> None:
    item = await repo.create({"name": "Needs Timer", "url": "https://example.com/a", "timer": "0 0 * * *"})

    async def handler(request):
        return await router.tasks_update(request, repo, Encoder(), _Notify(), _Handler(matched=False))

    client = await test_client({"tasks_update": handler})
    response = await client.put(
        url_for("tasks_update", id=str(item.id)),
        json={"name": item.name, "url": item.url, "timer": "", "preset": "", "folder": "", "template": "", "cli": ""},
    )

    assert response.status == 400
    refreshed = await repo.get(item.id)
    assert refreshed is not None
    assert refreshed.timer == "0 0 * * *"


@pytest.mark.asyncio
async def test_patch_requires_timer(repo, test_client) -> None:
    item = await repo.create({"name": "Patch Timer", "url": "https://example.com/b", "timer": "0 0 * * *"})

    async def handler(request):
        return await router.tasks_patch(request, repo, Encoder(), _Notify(), _Handler(matched=False))

    client = await test_client({"tasks_patch": handler})
    response = await client.patch(url_for("tasks_patch", id=str(item.id)), json={"timer": ""})

    assert response.status == 400
    refreshed = await repo.get(item.id)
    assert refreshed is not None
    assert refreshed.timer == "0 0 * * *"


@pytest.mark.asyncio
async def test_patch_url(repo, test_client) -> None:
    item = await repo.create({"name": "Patch URL", "url": "https://example.com/old", "timer": "0 0 * * *"})

    async def handler(request):
        return await router.tasks_patch(request, repo, Encoder(), _Notify(), _Handler(matched=True))

    client = await test_client({"tasks_patch": handler})
    response = await client.patch(url_for("tasks_patch", id=str(item.id)), json={"url": "not-a-url"})

    assert response.status == 400
    refreshed = await repo.get(item.id)
    assert refreshed is not None
    assert refreshed.url == "https://example.com/old"


@pytest.mark.asyncio
async def test_patch_requires_timer_disabled(repo, test_client) -> None:
    item = await repo.create({"name": "Disabled Handler", "url": "https://example.com/c", "timer": "0 0 * * *"})

    async def handler(request):
        return await router.tasks_patch(request, repo, Encoder(), _Notify(), _Handler(matched=True))

    client = await test_client({"tasks_patch": handler})
    response = await client.patch(url_for("tasks_patch", id=str(item.id)), json={"timer": "", "handler_enabled": False})

    assert response.status == 400
    assert "handler is disabled" in await response.text()
