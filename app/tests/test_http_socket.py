from pathlib import Path
from unittest.mock import Mock

import pytest
from aiohttp import web

from app.library.Events import EventBus
from app.library.HttpSocket import HttpSocket
from app.library.Services import Services


class FakeSocket:
    closed = False
    close_reason = None

    async def prepare(self, _: web.Request) -> None:
        return None

    def __aiter__(self) -> "FakeSocket":
        return self

    async def __anext__(self) -> None:
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_disables_socket_compression(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    EventBus._reset_singleton()
    Services._reset_singleton()
    options: dict[str, object] = {}

    def make_socket(**kwargs: object) -> FakeSocket:
        options.update(kwargs)
        return FakeSocket()

    monkeypatch.setattr("app.library.HttpSocket.get_routes", lambda _: {})
    monkeypatch.setattr("app.library.HttpSocket.web.WebSocketResponse", make_socket)

    try:
        socket = HttpSocket(root_path=tmp_path, config=Mock(base_path="", debug=False))
        app = web.Application()
        socket.attach(app)
        route = next(route for route in app.router.routes() if route.method == "GET")

        await route.handler(Mock())

        assert options == {"heartbeat": 10, "compress": False}
    finally:
        EventBus._reset_singleton()
        Services._reset_singleton()
