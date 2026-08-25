from __future__ import annotations

import os
from pathlib import Path

from aiohttp import web

from app.tests.helpers import (
    get_test_per_run_root,
    get_test_system_temp_root,
    make_test_disk_path,
    make_test_temp_dir,
    reset_current_test_app,
    set_test_env,
    set_current_test_app,
    url_for,
)


def test_disk_path_root() -> None:
    path = make_test_disk_path("artifacts", "example.txt")

    assert path.parent.exists()
    assert path.is_relative_to(get_test_per_run_root())


def test_temp_dir_created() -> None:
    path = make_test_temp_dir("helpers")

    assert path.exists()
    assert path.is_dir()
    assert path.is_relative_to(get_test_per_run_root())


def test_tmp_path_root(tmp_path: Path) -> None:
    expected_root = get_test_per_run_root() / "pytest"

    assert tmp_path.is_relative_to(expected_root)
    assert get_test_system_temp_root().is_relative_to(get_test_per_run_root())


def test_env_namespace_reset(monkeypatch) -> None:
    monkeypatch.setenv("YTP_OLD_VALUE", "old")
    monkeypatch.setenv("UNRELATED_VALUE", "kept")

    set_test_env(monkeypatch, {"host": "127.0.0.2", "YTP_FILE_LOGGING": False})

    assert "YTP_OLD_VALUE" not in os.environ
    assert os.environ["YTP_HOST"] == "127.0.0.2"
    assert os.environ["YTP_FILE_LOGGING"] == "false"
    assert os.environ["UNRELATED_VALUE"] == "kept"


def test_app_context_restores() -> None:
    async def handler(request: web.Request) -> web.Response:
        del request
        return web.Response()

    first = web.Application()
    first.router.add_get("/first", handler, name="first")
    second = web.Application()
    second.router.add_get("/second", handler, name="second")

    first_previous = set_current_test_app(first)
    try:
        second_previous = set_current_test_app(second)
        try:
            assert str(url_for("second")) == "/second"
        finally:
            reset_current_test_app(second_previous)

        assert str(url_for("first")) == "/first"
    finally:
        reset_current_test_app(first_previous)
