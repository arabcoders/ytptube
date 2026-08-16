from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any

import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from app.tests.helpers import (
    cleanup_test_run_root,
    get_test_run_root,
    get_test_system_temp_root,
    make_test_app,
    reset_current_test_app,
    set_current_test_app,
)

if TYPE_CHECKING:
    from aiohttp import web

Handler = Callable[..., Awaitable[Any]]


def pytest_configure(config) -> None:
    temp_root = get_test_system_temp_root()
    for env_name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[env_name] = str(temp_root)

    tempfile.tempdir = None

    if getattr(config.option, "basetemp", None) is None:
        config.option.basetemp = str(get_test_run_root() / "pytest")

    os.environ["YTP_FILE_LOGGING"] = "false"


def pytest_unconfigure(config) -> None:
    del config
    os.environ.pop("YTP_FILE_LOGGING", None)
    cleanup_test_run_root()


@pytest_asyncio.fixture
async def test_client() -> AsyncIterator[Callable[[Mapping[str, Handler] | None], Awaitable[TestClient]]]:
    clients: list[TestClient] = []
    previous_apps: list[web.Application | None] = []

    async def factory(handlers: Mapping[str, Handler] | None = None) -> TestClient:
        app = make_test_app(handlers)
        client = TestClient(TestServer(app))
        await client.start_server()
        clients.append(client)
        previous_apps.append(set_current_test_app(app))
        return client

    try:
        yield factory
    finally:
        for previous_app in reversed(previous_apps):
            reset_current_test_app(previous_app)
        for client in reversed(clients):
            await client.close()
