from __future__ import annotations

import json
from typing import Any, Generator

import pytest

from app.features.conditions import router as conditions_router
from app.features.tasks import router as tasks_router
from app.features.ytdlp import router as ytdlp_router
from app.library.config import Config


@pytest.fixture(autouse=True)
def reset_config() -> Generator[None, None, None]:
    Config._reset_singleton()
    yield
    Config._reset_singleton()


class _Req:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.body_exists = payload is not None

    async def json(self) -> Any:
        return self._payload


class _InspectReq(_Req):
    query: dict[str, str] = {}
    match_info: dict[str, str] = {}


class _QueryReq:
    def __init__(self, query: dict[str, str]) -> None:
        self.query = query


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
async def test_inspect_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    request = _InspectReq({"url": "https://bad.example/task"})
    seen = _patch_thread(monkeypatch, tasks_router, config, "https://bad.example/task")

    response = await tasks_router.task_handler_inspect(request, handler=None, encoder=None, config=config)

    assert response.status == 400
    assert json.loads(response.body.decode("utf-8")) == {"error": "Invalid hostname."}
    assert seen == {"to_thread": True, "validate": True}


@pytest.mark.asyncio
async def test_conditions_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    request = _Req({"url": "https://bad.example/cond", "condition": "title ~= 'x'"})
    seen = _patch_thread(monkeypatch, conditions_router, config, "https://bad.example/cond")

    response = await conditions_router.conditions_test(request, encoder=None, cache=None, config=config)

    assert response.status == 400
    assert json.loads(response.body.decode("utf-8")) == {"error": "Invalid hostname."}
    assert seen == {"to_thread": True, "validate": True}


@pytest.mark.asyncio
async def test_info_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    request = _QueryReq({"url": "https://bad.example/info"})
    seen = _patch_thread(monkeypatch, ytdlp_router, config, "https://bad.example/info")

    response = await ytdlp_router.get_info(request, cache=None, config=config)

    assert response.status == 400
    assert json.loads(response.body.decode("utf-8")) == {
        "status": False,
        "message": "Invalid hostname.",
        "error": "Invalid hostname.",
    }
    assert seen == {"to_thread": True, "validate": True}


@pytest.mark.asyncio
async def test_archive_ids_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    request = _Req(["https://bad.example/archive"])
    seen = _patch_thread(monkeypatch, ytdlp_router, config, "https://bad.example/archive")

    response = await ytdlp_router.get_archive_ids(request, config)

    assert response.status == 200
    assert json.loads(response.body.decode("utf-8")) == [
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
