import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import ClientTimeout, web
from aiohttp.test_utils import TestClient, TestServer

from app import _add_package_paths, main
from app.library.config import Config
from app.library.HttpAPI import HttpAPI
from app.tests.helpers import set_test_env


def test_adds_package_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    set_test_env(monkeypatch, {"config_path": config, "python_path": os.pathsep.join((str(first), str(second)))})
    monkeypatch.setattr(sys, "path", ["bundled"])

    _add_package_paths()

    user_site = config / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
    assert sys.path == [str(first), str(second), str(user_site), "bundled"]


def test_ignores_missing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    set_test_env(monkeypatch, {"python_path": os.pathsep.join((str(tmp_path / "missing"), str(existing)))})
    monkeypatch.setattr(sys, "path", ["bundled"])

    _add_package_paths()

    assert sys.path == [str(existing), "bundled"]


def test_moves_existing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    external = tmp_path / "external"
    external.mkdir()
    set_test_env(monkeypatch, {"python_path": external})
    monkeypatch.setattr(sys, "path", ["bundled", str(external)])

    _add_package_paths()

    assert sys.path == [str(external), "bundled"]


def test_ignores_package_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config"
    config.mkdir()
    user_site = config / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
    user_site.write_text("not a directory")
    set_test_env(monkeypatch, {"config_path": config})
    monkeypatch.setattr(sys, "path", ["bundled"])

    _add_package_paths()

    assert sys.path == ["bundled"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("setting", "limit"), [(None, 5_242_880), (1, 1_048_576), (2, 2_097_152)])
async def test_request_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setting: int | None, limit: int
) -> None:
    set_test_env(monkeypatch, {"config_path": tmp_path, "file_logging": False})
    if setting is not None:
        monkeypatch.setenv("YTP_MAX_REQUEST_SIZE", str(setting))
    monkeypatch.setattr(Config, "app_path", Config.app_path)
    monkeypatch.setattr(main.Main, "on_shutdown", AsyncMock())
    monkeypatch.setattr(main, "Services", Mock())
    monkeypatch.setattr(main, "HttpAPI", Mock())
    monkeypatch.setattr(main, "HttpSocket", Mock())
    Config._reset_singleton()
    try:
        app = main.Main()._app
        api = HttpAPI.__new__(HttpAPI)

        async def read(request: web.Request) -> web.Response:
            await request.read()
            return web.Response(status=204)

        async def handler(request: web.Request) -> web.StreamResponse:
            return await api._handle(read, request)

        app.router.add_post("/", handler)
        timeout = ClientTimeout(total=5)
        async with asyncio.timeout(15), TestClient(TestServer(app)) as client:
            assert (await client.post("/", data=b"x" * limit, timeout=timeout)).status == 204
            response = await client.post("/", data=b"x" * (limit + 1), timeout=timeout)
            assert response.status == 413
            assert (await response.json())["code"] == "REQUEST_TOO_LARGE"
    finally:
        Config._reset_singleton()


@pytest.mark.parametrize("setting", [-1, 0])
def test_clamps_request_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, setting: int
) -> None:
    set_test_env(monkeypatch, {"config_path": tmp_path, "file_logging": False, "max_request_size": setting})
    Config._reset_singleton()
    try:
        assert Config.get_instance().max_request_size == 1
        assert f"YTP_MAX_REQUEST_SIZE={setting} is below the minimum. Using 1 MiB." in caplog.messages
    finally:
        Config._reset_singleton()
