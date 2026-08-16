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


def _patch_thread(monkeypatch: pytest.MonkeyPatch, module: Any, config: Config, url: str) -> dict[str, bool]:
    seen = {"to_thread": False, "validate": False}

    def fake_validate_url(next_url: str, allow_internal: bool = False) -> bool:
        seen["validate"] = True
        assert next_url == url
        assert allow_internal is config.allow_internal_urls
        raise ValueError("Invalid hostname.")

    async def fake_to_thread(func, *args, **kwargs):
        seen["to_thread"] = True
        return func(*args, **kwargs)

    monkeypatch.setattr(module, "validate_url", fake_validate_url)
    monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
    return seen


@pytest.mark.asyncio
async def test_inspect_thread(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    seen = _patch_thread(monkeypatch, tasks_router, config, "https://bad.example/task")

    async def handler(request):
        return await tasks_router.task_handler_inspect(request, handler=None, encoder=None, config=config)

    client = await test_client({"task_handler_inspect": handler})
    response = await client.post(url_for("task_handler_inspect"), json={"url": "https://bad.example/task"})

    assert response.status == 400
    assert (await response.json())["error"] == "Invalid hostname."
    assert seen == {"to_thread": True, "validate": True}


@pytest.mark.asyncio
async def test_conditions_thread(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    seen = _patch_thread(monkeypatch, conditions_router, config, "https://bad.example/cond")

    async def handler(request):
        return await conditions_router.conditions_test(request, encoder=None, cache=None, config=config)

    client = await test_client({"condition_test": handler})
    response = await client.post(
        url_for("condition_test"), json={"url": "https://bad.example/cond", "condition": "title ~= 'x'"}
    )

    assert response.status == 400
    assert (await response.json())["error"] == "Invalid hostname."
    assert seen == {"to_thread": True, "validate": True}


@pytest.mark.asyncio
async def test_info_thread(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    seen = _patch_thread(monkeypatch, ytdlp_router, config, "https://bad.example/info")

    async def handler(request):
        return await ytdlp_router.get_info(request, cache=None, config=config)

    client = await test_client({"get_info": handler})
    response = await client.get(url_for("get_info", query={"url": "https://bad.example/info"}))

    assert response.status == 400
    assert (await response.json())["error"] == "Invalid hostname."
    assert seen == {"to_thread": True, "validate": True}


@pytest.mark.asyncio
async def test_archive_ids_thread(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    seen = _patch_thread(monkeypatch, ytdlp_router, config, "https://bad.example/archive")

    async def handler(request):
        return await ytdlp_router.get_archive_ids(request, config)

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
    assert seen == {"to_thread": True, "validate": True}
