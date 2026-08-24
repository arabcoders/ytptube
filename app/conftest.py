from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from app.tests.helpers import (
    cleanup_test_run_root,
    get_test_per_run_root,
    get_test_system_temp_root,
    make_test_app,
    reset_current_test_app,
    set_current_test_app,
)

if TYPE_CHECKING:
    from aiohttp import web

Handler = Callable[..., Awaitable[Any]]
FIXTURE_TIMEOUT_SECONDS = 15.0


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config) -> None:
    temp_root = get_test_system_temp_root()
    for env_name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[env_name] = str(temp_root)

    tempfile.tempdir = None

    run_root = get_test_per_run_root()
    if getattr(config.option, "basetemp", None) is None:
        config.option.basetemp = str(run_root / "pytest")

    config._inicache["cache_dir"] = str(run_root / "pytest-cache")
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
        clients.append(client)
        await asyncio.wait_for(client.start_server(), FIXTURE_TIMEOUT_SECONDS)
        previous_apps.append(set_current_test_app(app))
        return client

    try:
        yield factory
    finally:
        first_error: BaseException | None = None
        for previous_app in reversed(previous_apps):
            try:
                reset_current_test_app(previous_app)
            except BaseException as error:
                if first_error is None:
                    first_error = error
        for client in reversed(clients):
            try:
                await asyncio.wait_for(client.close(), FIXTURE_TIMEOUT_SECONDS)
            except BaseException as error:
                if first_error is None:
                    first_error = error
        if first_error is not None:
            raise first_error
