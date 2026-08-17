from __future__ import annotations

from pathlib import Path

import pytest

from app.library.config import Config


@pytest.fixture
def config_env(monkeypatch, tmp_path: Path):
    Config._reset_singleton()
    config_path = tmp_path / "config"
    config_path.mkdir()
    monkeypatch.setenv("YTP_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YTP_FILE_LOGGING", "false")
    monkeypatch.delenv("YTP_DISABLE_AUTH", raising=False)
    yield
    Config._reset_singleton()


def test_native_auth_default(config_env) -> None:
    assert Config.get_instance(is_native=True).disable_auth


def test_native_auth_explicit(config_env, monkeypatch) -> None:
    monkeypatch.setenv("YTP_DISABLE_AUTH", "false")
    assert not Config.get_instance(is_native=True).disable_auth


def test_server_auth_default(config_env) -> None:
    assert not Config.get_instance().disable_auth
