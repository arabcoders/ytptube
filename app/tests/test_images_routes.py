from __future__ import annotations

import logging
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
async def test_bg_log_redact(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    config.pictures_backends = ["https://user:pass@example.com/bg.jpg?apitoken=secret#frag"]
    req = make_mocked_request("GET", "/api/random/background")

    class DummyCache:
        def has(self, _key: str) -> bool:
            return False

        async def aset(self, **_kwargs) -> None:
            return None

    client = AsyncMock()
    client.request.side_effect = RuntimeError("boom")

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

    with caplog.at_level(logging.ERROR):
        response = await images.get_background(req, config, DummyCache())

    assert response.status == web.HTTPInternalServerError.status_code
    record = next(record for record in caplog.records if record.name == images.LOG.name)
    assert "apitoken=secret" not in record.getMessage()
    assert "user:pass@" not in record.getMessage()
    assert record.url == "https://redacted:redacted@example.com/bg.jpg?redacted#redacted"
    assert record.exception_type == "RuntimeError"
