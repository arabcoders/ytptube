from __future__ import annotations

import logging
from typing import Generator
from unittest.mock import AsyncMock

import pytest
from app.library.config import Config
from app.routes.api import images
from app.tests.helpers import url_for


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
async def test_bg_log_redact(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    config = Config.get_instance()
    config.pictures_backends = ["https://user:pass@example.com/bg.jpg?apitoken=secret#frag"]

    class DummyCache:
        def has(self, _key: str) -> bool:
            return False

        async def aset(self, **_kwargs) -> None:
            return None

    outbound = AsyncMock()
    outbound.request.side_effect = RuntimeError("boom")

    monkeypatch.setattr(images, "get_async_client", lambda **_kwargs: outbound)
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

    async def handler(request):
        return await images.get_background(request, config, DummyCache())

    test_client_app = await test_client({"get_background": handler})
    with caplog.at_level(logging.ERROR):
        response = await test_client_app.get(url_for("get_background"))

    assert response.status == 500
    record = next(
        record
        for record in caplog.records
        if record.name == images.LOG.name
        and record.getMessage().startswith("Failed to request random background image")
    )
    assert "apitoken=secret" not in record.getMessage()
    assert "user:pass@" not in record.getMessage()
    assert getattr(record, "url", None) == "https://redacted:redacted@example.com/bg.jpg?redacted#redacted"
    assert getattr(record, "exception_type", None) == "RuntimeError"
