from __future__ import annotations

from typing import Generator
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from app.library.config import Config
from app.routes.api import images


@pytest.fixture(autouse=True)
def reset_config() -> Generator[None, None, None]:
    Config._reset_singleton()
    yield
    Config._reset_singleton()


class _Resp:
    def __init__(self, *, status_code: int = 200, content: bytes = b"img", content_type: str = "image/jpeg") -> None:
        self.status_code = status_code
        self.content = content
        self.headers = {"Content-Type": content_type}


@pytest.mark.asyncio
async def test_thumb_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    req = make_mocked_request("GET", "/api/thumbnail?url=https://example.com/a.jpg")
    req._rel_url = req._rel_url.with_query({"url": "https://example.com/a.jpg"})

    seen = {"to_thread": False, "validate": False}

    def fake_validate_url(url: str, allow_internal: bool = False) -> bool:
        seen["validate"] = True
        assert url == "https://example.com/a.jpg"
        assert allow_internal is config.allow_internal_urls
        return True

    async def fake_to_thread(func, *args, **kwargs):
        seen["to_thread"] = True
        return func(*args, **kwargs)

    client = AsyncMock()
    client.request.return_value = _Resp()

    monkeypatch.setattr(images, "validate_url", fake_validate_url)
    monkeypatch.setattr(images.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(images, "get_async_client", lambda **_kwargs: client)
    monkeypatch.setattr(images, "resolve_curl_transport", lambda: False)
    monkeypatch.setattr(images, "build_request_headers", lambda **_kwargs: {})
    monkeypatch.setattr(images.Globals, "get_random_agent", staticmethod(lambda: "agent"))
    monkeypatch.setattr(
        images.YTDLPOpts,
        "get_instance",
        staticmethod(
            lambda: type(
                "Opts",
                (),
                {
                    "preset": lambda self, name: self,
                    "get_all": lambda self: {},
                },
            )()
        ),
    )

    response = await images.get_thumbnail(req, config)

    assert response.status == web.HTTPOk.status_code
    assert seen["to_thread"] is True
    assert seen["validate"] is True
    client.request.assert_awaited_once()


@pytest.mark.asyncio
async def test_thumb_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    req = make_mocked_request("GET", "/api/thumbnail?url=https://bad.example/a.jpg")
    req._rel_url = req._rel_url.with_query({"url": "https://bad.example/a.jpg"})

    def fake_validate_url(_url: str, allow_internal: bool = False) -> bool:
        assert allow_internal is config.allow_internal_urls
        raise ValueError("Invalid hostname.")

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(images, "validate_url", fake_validate_url)
    monkeypatch.setattr(images.asyncio, "to_thread", fake_to_thread)

    response = await images.get_thumbnail(req, config)

    assert response.status == web.HTTPForbidden.status_code
    assert response.text == '{"error": "Invalid hostname."}'
