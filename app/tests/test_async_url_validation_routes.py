from __future__ import annotations

from typing import Any, Generator

import pytest

from app.features.conditions import router as conditions_router
from app.features.tasks import router as tasks_router
from app.features.ytdlp import router as ytdlp_router
from app.library.config import Config
from app.tests.helpers import url_for


@pytest.fixture(autouse=True)
def reset_config() -> Generator[None, None, None]:
    Config._reset_singleton()
    yield
    Config._reset_singleton()


def _reject_url(monkeypatch: pytest.MonkeyPatch, module: Any, url: str) -> dict[str, bool]:
    seen = {"validate": False}

    def reject(next_url: str) -> bool:
        seen["validate"] = True
        assert next_url == url
        raise ValueError("Invalid hostname.")

    monkeypatch.setattr(module, "validate_url", reject)
    return seen


@pytest.mark.asyncio
async def test_inspect_validation(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    seen = _reject_url(monkeypatch, tasks_router, "https://bad.example/task")

    async def handler(request):
        return await tasks_router.task_handler_inspect(request, handler=None, encoder=None)

    client = await test_client({"task_handler_inspect": handler})
    response = await client.post(url_for("task_handler_inspect"), json={"url": "https://bad.example/task"})

    assert response.status == 400
    assert (await response.json())["error"] == "Invalid hostname."
    assert seen == {"validate": True}


@pytest.mark.asyncio
async def test_conditions_validation(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    seen = _reject_url(monkeypatch, conditions_router, "https://bad.example/cond")

    async def handler(request):
        return await conditions_router.conditions_test(request, encoder=None, cache=None, config=config)

    client = await test_client({"condition_test": handler})
    response = await client.post(
        url_for("condition_test"), json={"url": "https://bad.example/cond", "condition": "title ~= 'x'"}
    )

    assert response.status == 400
    assert (await response.json())["error"] == "Invalid hostname."
    assert seen == {"validate": True}


@pytest.mark.asyncio
async def test_info_validation(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    seen = _reject_url(monkeypatch, ytdlp_router, "https://bad.example/info")

    async def handler(request):
        return await ytdlp_router.get_info(request, cache=None, config=config)

    client = await test_client({"get_info": handler})
    response = await client.get(url_for("get_info", query={"url": "https://bad.example/info"}))

    assert response.status == 400
    assert (await response.json())["error"] == "Invalid hostname."
    assert seen == {"validate": True}


@pytest.mark.asyncio
async def test_archive_validation(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    seen = _reject_url(monkeypatch, ytdlp_router, "https://bad.example/archive")

    async def handler(request):
        return await ytdlp_router.get_archive_ids(request)

    client = await test_client({"get_archive_ids": handler})
    response = await client.post(url_for("get_archive_ids"), json=["https://bad.example/archive"])

    assert response.status == 200
    assert await response.json() == [
        {
            "index": 0,
            "url": "https://bad.example/archive",
            "id": None,
            "ie_key": None,
            "archive_id": None,
            "error": "Invalid hostname.",
        }
    ]
    assert seen == {"validate": True}
