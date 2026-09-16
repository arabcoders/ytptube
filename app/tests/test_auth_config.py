from __future__ import annotations

import re
from pathlib import Path

import platformdirs
import pytest

from app.library.config import Config
from app.tests.helpers import set_test_env


@pytest.fixture
def config_env(monkeypatch, tmp_path: Path):
    Config._reset_singleton()
    config_path = tmp_path / "config"
    config_path.mkdir()
    set_test_env(monkeypatch, {"config_path": config_path, "file_logging": False})
    yield config_path
    Config._reset_singleton()


def test_native_auth_default(config_env) -> None:
    assert Config.get_instance(is_native=True).disable_auth


def test_native_auth_explicit(config_env, monkeypatch) -> None:
    monkeypatch.setenv("YTP_DISABLE_AUTH", "false")
    assert not Config.get_instance(is_native=True).disable_auth


def test_server_auth_default(config_env) -> None:
    assert not Config.get_instance().disable_auth


def test_native_cors_default(config_env) -> None:
    assert Config.get_instance(is_native=True).cors_origins == ""


def test_native_cors_explicit(config_env, monkeypatch) -> None:
    monkeypatch.setenv("YTP_CORS_ORIGINS", "*")
    assert Config.get_instance(is_native=True).cors_origins == "*"


def test_server_cors_default(config_env) -> None:
    assert Config.get_instance().cors_origins == "*"


def test_native_path_defaults(config_env, monkeypatch, tmp_path: Path) -> None:
    cache_path = tmp_path / "cache"
    download_path = tmp_path / "downloads"
    monkeypatch.setattr(platformdirs, "user_cache_dir", lambda *_: str(cache_path))
    monkeypatch.setattr(platformdirs, "user_downloads_dir", lambda: str(download_path))

    config = Config.get_instance(is_native=True)

    assert config.temp_path == str(cache_path)
    assert config.download_path == str(download_path)
    assert config.host == "127.0.0.1"
    assert not config.access_log


def test_native_config_path(config_env, monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "native"
    monkeypatch.delenv("YTP_CONFIG_PATH")
    monkeypatch.setattr(platformdirs, "user_config_dir", lambda *_: str(config_path))

    assert Config.get_instance(is_native=True).config_path == str(config_path)


def test_native_env_file(config_env: Path, monkeypatch) -> None:
    env_file = config_env / ".env"
    env_file.write_text(
        "YTP_HOST=127.0.0.2\nYTP_ACCESS_LOG=true\nYTP_CORS_ORIGINS=https://local.example\nYTP_NO_BROWSER=true\n",
        encoding="utf-8",
    )
    try:
        config = Config.get_instance(is_native=True)
        assert config.host == "127.0.0.2"
        assert config.access_log
        assert config.cors_origins == "https://local.example"
        assert config.no_browser
    finally:
        for key in ("YTP_HOST", "YTP_ACCESS_LOG", "YTP_CORS_ORIGINS", "YTP_NO_BROWSER"):
            monkeypatch.delenv(key, raising=False)


def test_process_env_precedence(config_env: Path, monkeypatch) -> None:
    (config_env / ".env").write_text("YTP_HOST=127.0.0.2\n", encoding="utf-8")
    monkeypatch.setenv("YTP_HOST", "127.0.0.3")

    assert Config.get_instance(is_native=True).host == "127.0.0.3"


def test_runtime_mode_conflict(config_env) -> None:
    Config.get_instance(is_native=False)

    with pytest.raises(RuntimeError, match="different runtime mode"):
        Config.get_instance(is_native=True)


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


def test_filename_trim_config(config_env, monkeypatch) -> None:
    monkeypatch.setenv("YTP_FILENAME_TRIM", "END")
    monkeypatch.setenv("YTP_FILENAME_TRIM_REGEXES", r'["^\\d+", "\\[[^][]*\\]"]')

    config = Config.get_instance()

    assert config.filename_trim == "end"
    assert tuple(pattern.pattern for pattern in config.filename_trim_regexes) == (r"^\d+", r"\[[^][]*\]")
    assert all(isinstance(pattern, re.Pattern) for pattern in config.filename_trim_regexes)


def test_filename_trim_mode(config_env, monkeypatch) -> None:
    monkeypatch.setenv("YTP_FILENAME_TRIM", "sideways")

    with pytest.raises(ValueError, match="filename_trim"):
        Config.get_instance()


def test_external_auth(config_env: Path, monkeypatch) -> None:
    (config_env / "config.toml").write_text(
        """[auth]
external_user = 'owner'
[auth.oidc]
issuer = 'https://issuer.example'
client_id = 'client'
client_secret = 'secret'
redirect_uri = 'https://app.example/callback'
[auth.remote_user]
enabled = true
trusted_proxies = ['10.0.0.0/24']
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("YTP_EXTERNAL_AUTH", "ignored")

    config = Config.get_instance()

    assert config.external_auth.external_user == "owner"
    assert config.external_auth.oidc is not None
    assert config.external_auth.oidc.client_id == "client"
    assert config.external_auth.remote_user.header == "Remote-User"
    assert str(config.external_auth.remote_user.trusted_proxies[0]) == "10.0.0.0/24"


def test_external_auth_custom(config_env: Path) -> None:
    (config_env / "config.toml").write_text(
        """[auth]
external_user = ' owner '
[auth.remote_user]
enabled = true
header = 'X-Remote_User'
trusted_proxies = ['192.0.2.0/24', '2001:db8::/32']
""",
        encoding="utf-8",
    )

    remote = Config.get_instance().external_auth

    assert remote.external_user == "owner"
    assert remote.remote_user.header == "X-Remote_User"
    assert tuple(str(proxy) for proxy in remote.remote_user.trusted_proxies) == ("192.0.2.0/24", "2001:db8::/32")


def test_external_auth_disabled(config_env) -> None:
    config = Config.get_instance()

    assert config.external_auth.external_user is None
    assert config.external_auth.oidc is None
    assert not config.external_auth.remote_user.enabled


@pytest.mark.parametrize(
    "content, message",
    [
        ("[auth.oidc]\nissuer = 'x'\n", "auth.oidc"),
        ("[auth.remote_user]\nenabled = true\n", "trusted_proxies"),
        ("[auth.remote_user]\nheader = 'Bad Header'\n", "HTTP token"),
        ("[auth.remote_user]\nenabled = true\ntrusted_proxies = ['bad']\n", "valid CIDRs"),
        ("[auth.remote_user]\nenabled = true\ntrusted_proxies = ['10.0.0.0/24']\n", "external_user"),
    ],
)
def test_external_auth_invalid(config_env: Path, content: str, message: str) -> None:
    (config_env / "config.toml").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        Config.get_instance()


def test_external_auth_toml(config_env: Path) -> None:
    (config_env / "config.toml").write_text("[auth\n", encoding="utf-8")

    with pytest.raises(ValueError, match="TOML"):
        Config.get_instance()


@pytest.mark.parametrize(
    "content, message",
    [
        ("auth = 'value'\n", "auth must be a table"),
        ("[auth]\nexternal_user = true\n", "external_user"),
        ("[auth.oidc]\nissuer = []\n", "auth.oidc"),
        ("[auth.remote_user]\nenabled = 'yes'\n", "enabled"),
        ("[auth.remote_user]\ntrusted_proxies = ['10.0.0.0/24', 1]\n", "trusted_proxies"),
    ],
)
def test_external_auth_types(config_env: Path, content: str, message: str) -> None:
    (config_env / "config.toml").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        Config.get_instance()


@pytest.mark.parametrize("field", ["external_user", "issuer", "client_id", "client_secret", "redirect_uri"])
def test_external_auth_blank(config_env: Path, field: str) -> None:
    content = "[auth]\nexternal_user = 'owner'\n[auth.oidc]\n"
    values = {"issuer": "x", "client_id": "x", "client_secret": "x", "redirect_uri": "x"}
    values[field] = "   "
    if field == "external_user":
        content = "[auth]\nexternal_user = '   '\n[auth.oidc]\n"
    else:
        content += "\n".join(f"{key} = '{value}'" for key, value in values.items()) + "\n"
    (config_env / "config.toml").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):
        Config.get_instance()


def test_external_auth_env(config_env: Path, monkeypatch) -> None:
    for key, value in {
        "YTP_OIDC_ISSUER": "https://env.example",
        "YTP_REMOTE_USER_HEADER": "X-Env",
        "YTP_EXTERNAL_USER": "env-user",
    }.items():
        monkeypatch.setenv(key, value)

    auth = Config.get_instance().external_auth

    assert auth.external_user is None
    assert auth.oidc is None
    assert auth.remote_user.header == "Remote-User"


@pytest.mark.parametrize("value", ['["("]', '"^x"', '["x", 1]'])
def test_filename_trim_regex(config_env, monkeypatch, value: str) -> None:
    monkeypatch.setenv("YTP_FILENAME_TRIM_REGEXES", value)

    with pytest.raises(ValueError, match="filename_trim|regular expression"):
        Config.get_instance()
