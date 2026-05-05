from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from app.features.tasks import router
from app.features.tasks.definitions.results import TaskFailure, TaskResult
from app.features.tasks.repository import TasksRepository
from app.library.encoder import Encoder
from app.library.sqlite_store import SqliteStore
from app.tests.helpers import make_in_memory_db_path


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


def _json_request(method: str, path: str, payload: object, *, match_info: dict[str, str] | None = None) -> web.Request:
    request = make_mocked_request(method, path, match_info=match_info or {}, app=SimpleNamespace())

    async def _json() -> object:
        return payload

    request.json = _json  # type: ignore[attr-defined]
    return request


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
async def test_add_requires_timer_without_handler(repo) -> None:
    request = _json_request(
        "POST",
        "/api/tasks/",
        {"name": "No Timer", "url": "https://example.com/channel"},
    )

    response = await router.tasks_add(request, repo, Encoder(), _Notify(), _Handler(matched=False))

    assert response.status == web.HTTPBadRequest.status_code
    assert b"requires a timer" in response.body
    assert await repo.list() == []


@pytest.mark.asyncio
async def test_add_all_or_nothing(repo) -> None:
    request = _json_request(
        "POST",
        "/api/tasks/",
        [
            {"name": "First", "url": "https://example.com/first"},
            {"url": "https://example.com/second"},
        ],
    )

    response = await router.tasks_add(
        request,
        repo,
        Encoder(),
        _Notify(),
        _Handler({"https://example.com/first": True, "https://example.com/second": False}),
    )

    assert response.status == web.HTTPBadRequest.status_code
    assert b"requires a timer" in response.body
    assert await repo.list() == []


@pytest.mark.asyncio
async def test_add_allows_handler_only(repo) -> None:
    request = _json_request(
        "POST",
        "/api/tasks/",
        {"name": "Handler Only", "url": "https://example.com/feed"},
    )

    response = await router.tasks_add(request, repo, Encoder(), _Notify(), _Handler(matched=True))

    assert response.status == web.HTTPOk.status_code
    items = await repo.list()
    assert len(items) == 1
    assert items[0].name == "Handler Only"


@pytest.mark.asyncio
async def test_update_requires_timer_without_handler(repo) -> None:
    item = await repo.create({"name": "Needs Timer", "url": "https://example.com/a", "timer": "0 0 * * *"})

    request = _json_request(
        "PUT",
        f"/api/tasks/{item.id}",
        {"name": item.name, "url": item.url, "timer": "", "preset": "", "folder": "", "template": "", "cli": ""},
        match_info={"id": str(item.id)},
    )

    response = await router.tasks_update(request, repo, Encoder(), _Notify(), _Handler(matched=False))

    assert response.status == web.HTTPBadRequest.status_code
    refreshed = await repo.get(item.id)
    assert refreshed is not None
    assert refreshed.timer == "0 0 * * *"


@pytest.mark.asyncio
async def test_patch_requires_timer_without_handler(repo) -> None:
    item = await repo.create({"name": "Patch Timer", "url": "https://example.com/b", "timer": "0 0 * * *"})

    request = _json_request(
        "PATCH",
        f"/api/tasks/{item.id}",
        {"timer": ""},
        match_info={"id": str(item.id)},
    )

    response = await router.tasks_patch(request, repo, Encoder(), _Notify(), _Handler(matched=False))

    assert response.status == web.HTTPBadRequest.status_code
    refreshed = await repo.get(item.id)
    assert refreshed is not None
    assert refreshed.timer == "0 0 * * *"


@pytest.mark.asyncio
async def test_patch_requires_timer_when_handler_disabled(repo) -> None:
    item = await repo.create({"name": "Disabled Handler", "url": "https://example.com/c", "timer": "0 0 * * *"})

    request = _json_request(
        "PATCH",
        f"/api/tasks/{item.id}",
        {"timer": "", "handler_enabled": False},
        match_info={"id": str(item.id)},
    )

    response = await router.tasks_patch(request, repo, Encoder(), _Notify(), _Handler(matched=True))

    assert response.status == web.HTTPBadRequest.status_code
    assert b"handler is disabled" in response.body
