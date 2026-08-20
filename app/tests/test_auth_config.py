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
    monkeypatch.delenv("YTP_AUTH_SESSION_DAYS", raising=False)
    monkeypatch.delenv("YTP_TRUSTED_PROXIES", raising=False)
    yield
    Config._reset_singleton()


def test_native_auth_default(config_env) -> None:
    assert Config.get_instance(is_native=True).disable_auth


def test_native_auth_explicit(config_env, monkeypatch) -> None:
    monkeypatch.setenv("YTP_DISABLE_AUTH", "false")
    assert not Config.get_instance(is_native=True).disable_auth


def test_server_auth_default(config_env) -> None:
    assert not Config.get_instance().disable_auth


def test_session_override(config_env, monkeypatch) -> None:
    monkeypatch.setenv("YTP_AUTH_SESSION_DAYS", "45")
    assert Config.get_instance().auth_session_days == 45


def test_session_minimum(config_env, monkeypatch) -> None:
    monkeypatch.setenv("YTP_AUTH_SESSION_DAYS", "0")
    with pytest.raises(ValueError):
        Config.get_instance()


def test_proxy_override(config_env, monkeypatch) -> None:
    monkeypatch.setenv("YTP_TRUSTED_PROXIES", "10.0.0.0/24")
    assert Config.get_instance().trusted_proxies == "10.0.0.0/24"
