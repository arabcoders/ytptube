from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

import app
from app import local
from app.library.config import Config
from app.tests.helpers import set_test_env


@pytest.fixture
def native_env(monkeypatch, tmp_path: Path):
    Config._reset_singleton()
    config_path = tmp_path / "config"
    set_test_env(
        monkeypatch,
        {
            "config_path": config_path,
            "temp_path": tmp_path / "temp",
            "download_path": tmp_path / "downloads",
            "file_logging": False,
        },
    )
    monkeypatch.setattr(app, "_add_package_paths", lambda _: None)
    yield config_path
    Config._reset_singleton()
    os.environ.pop("YTP_PORT", None)
    os.environ.pop("YTP_NO_BROWSER", None)


def test_random_port_persisted(native_env: Path, monkeypatch) -> None:
    sock = MagicMock()
    sock.__enter__.return_value.getsockname.return_value = ("127.0.0.1", 49152)
    start = Mock()
    monkeypatch.setattr(local.socket, "socket", Mock(return_value=sock))
    monkeypatch.setattr(local, "app_start", start)
    monkeypatch.setattr("sys.argv", ["local.py", "--no-browser"])

    local.main()

    sock.__enter__.return_value.bind.assert_called_once_with(("127.0.0.1", 0))
    start.assert_called_once_with("127.0.0.1", 49152)
    assert (native_env / ".env").read_text(encoding="utf-8") == "YTP_PORT=49152\n"


def test_configured_port_preserved(native_env: Path, monkeypatch) -> None:
    (native_env / ".env").parent.mkdir(parents=True)
    (native_env / ".env").write_text("YTP_PORT=9000\nYTP_NO_BROWSER=true\n", encoding="utf-8")
    start = Mock()
    browser = Mock()
    monkeypatch.setattr(local.socket, "socket", lambda *_: pytest.fail("socket should not be opened"))
    monkeypatch.setattr(local, "app_start", start)
    monkeypatch.setattr(local, "open_browser_when_ready", browser)
    monkeypatch.setattr("sys.argv", ["local.py"])

    local.main()

    start.assert_called_once_with("127.0.0.1", 9000)
    browser.assert_not_called()
