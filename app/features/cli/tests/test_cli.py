import json
import sqlite3
import stat
from types import SimpleNamespace

import httpx
import pytest

from app.features.cli import main as cli


def config(tmp_path):
    return SimpleNamespace(
        config_path=str(tmp_path), host="0.0.0.0", port=8081, base_path="/prefix/", db_file=str(tmp_path / "db.sqlite")
    )


def test_read_only_config(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    assert cli.main(["info"]) == 0
    assert cli.main(["config", "show"]) == 0
    assert not (tmp_path / "cli.toml").exists()


def test_bad_toml(tmp_path, monkeypatch):
    (tmp_path / "cli.toml").write_text("not valid =")
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    assert cli.main(["info"]) == 1


def test_config_set(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    assert cli.main(["config", "set", "--url", "http://server.test/base", "--token", "ytp_secret"]) == 0
    path = tmp_path / "cli.toml"
    assert cli.tomllib.loads(path.read_text()) == {
        "url": "http://server.test/base/",
        "token": "file:secrets/api_token",
    }
    assert path.stat().st_mode & 0o777 == 0o600
    assert stat.S_IMODE((tmp_path / "secrets").stat().st_mode) == 0o700
    secret = tmp_path / "secrets" / "api_token"
    assert secret.read_text() == "ytp_secret\n"
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    assert "ytp_secret" not in capsys.readouterr().out

    assert cli.main(["config", "show", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"url": "http://server.test/base/", "token_configured": True}


def test_token_prompt_set(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    monkeypatch.setattr(cli, "getpass", lambda prompt: "prompt-key")
    assert cli.main(["config", "set", "--token"]) == 0
    assert (tmp_path / "secrets" / "api_token").read_text() == "prompt-key\n"
    assert cli.tomllib.loads((tmp_path / "cli.toml").read_text())["token"] == "file:secrets/api_token"
    assert "prompt-key" not in capsys.readouterr().out


def test_token_prompt_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    monkeypatch.setattr(cli, "getpass", lambda prompt: "")
    assert cli.main(["config", "set", "--token", ""]) == 1
    assert "API token is required" in capsys.readouterr().err
    assert not (tmp_path / "secrets" / "api_token").exists()


def test_config_url_change(tmp_path, monkeypatch, capsys):
    path = tmp_path / "cli.toml"
    path.write_text('url = "http://old.test/"\ntoken = "old-key"\n')
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    assert cli.main(["config", "set", "--url", "http://old.test"]) == 0
    assert cli.tomllib.loads(path.read_text())["token"] == "file:secrets/api_token"
    assert (tmp_path / "secrets" / "api_token").read_text() == "old-key\n"
    assert cli.main(["config", "set", "--url", "http://new.test"]) == 0
    assert cli.tomllib.loads(path.read_text()) == {"url": "http://new.test/"}
    assert not (tmp_path / "secrets" / "api_token").exists()
    assert "old-key" not in capsys.readouterr().out


def test_config_invalid(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    assert cli.main(["config", "set"]) == 1
    assert cli.main(["config", "set", "--url", "ftp://server.test/"]) == 1
    assert "HTTP(S)" in capsys.readouterr().err
    assert not (tmp_path / "cli.toml").exists()


def test_config_precedence(tmp_path, monkeypatch):
    path = tmp_path / "cli.toml"
    path.write_text('url = "http://file.test/root/"\ntoken = "file-token"\n')
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    monkeypatch.setenv("YTP_API_URL", "http://env.test/")
    monkeypatch.setenv("YTP_API_TOKEN", "env-token")
    calls = []

    def request(method, url, **kwargs):
        calls.append((url, kwargs["headers"]))
        return httpx.Response(200, json={"items": [], "pagination": {"page": 1, "total_pages": 0, "total": 0}})

    monkeypatch.setattr(cli.httpx, "request", request)
    assert cli.main(["tasks", "list"]) == 0
    assert calls[-1] == ("http://env.test/api/tasks/", {"Authorization": "Bearer env-token"})
    assert cli.main(["--url", "https://flag.test/ytp/", "--token", "flag-token", "tasks", "list"]) == 0
    assert calls[-1] == ("https://flag.test/ytp/api/tasks/", {"Authorization": "Bearer flag-token"})
    monkeypatch.delenv("YTP_API_URL")
    monkeypatch.delenv("YTP_API_TOKEN")
    assert cli.main(["tasks", "list"]) == 0
    assert calls[-1] == ("http://file.test/root/api/tasks/", {"Authorization": "Bearer file-token"})
    assert path.read_text() == 'url = "http://file.test/root/"\ntoken = "file-token"\n'


def test_file_token(tmp_path, monkeypatch, capsys):
    (tmp_path / "cli.toml").write_text('url = "http://server.test/"\ntoken = "file:secrets/api_token"\n')
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    assert cli.main(["tasks", "list"]) == 1
    assert "unreadable" in capsys.readouterr().err
    assert cli.main(["config", "set", "--token", "new-key"]) == 0
    calls = []
    monkeypatch.setattr(
        cli.httpx,
        "request",
        lambda method, url, **kwargs: (
            calls.append(kwargs["headers"])
            or httpx.Response(200, json={"items": [], "pagination": {"page": 1, "total_pages": 0, "total": 0}})
        ),
    )
    assert cli.main(["tasks", "list"]) == 0
    assert calls == [{"Authorization": "Bearer new-key"}]


def test_private_secrets(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    directory = tmp_path / "secrets"
    directory.mkdir(mode=0o755)
    secret = directory / "api_token"
    secret.write_text("existing-key\n")
    secret.chmod(0o644)
    assert cli.main(["config", "show"]) == 0
    assert stat.S_IMODE(directory.stat().st_mode) == 0o755
    assert stat.S_IMODE(secret.stat().st_mode) == 0o644
    assert "warning: secret path may be accessible to others" in capsys.readouterr().err
    assert cli.main(["config", "set", "--token", "new-key"]) == 0
    assert stat.S_IMODE(secret.stat().st_mode) == 0o644


def test_secret_symlink(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    directory = tmp_path / "secrets"
    directory.mkdir()
    secret = directory / "api_token"
    secret.symlink_to(tmp_path / "outside")
    assert cli.main(["config", "show"]) == 0
    assert "warning: secret path may be accessible to others" in capsys.readouterr().err
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["--url", "https://example.test/root/", "--token", "secret", "tasks", "list"],
        ["tasks", "--url", "https://example.test/root/", "--token", "secret", "list"],
        ["tasks", "list", "--url", "https://example.test/root/", "--token", "secret"],
    ],
)
def test_connection_options(tmp_path, monkeypatch, argv):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    calls = []

    def request(method, url, **kwargs):
        calls.append((url, kwargs["headers"]))
        return httpx.Response(200, json={"items": [], "pagination": {"page": 1, "total_pages": 0, "total": 0}})

    monkeypatch.setattr(cli.httpx, "request", request)
    assert cli.main(argv) == 0
    assert calls == [("https://example.test/root/api/tasks/", {"Authorization": "Bearer secret"})]


def test_token_prompt_request(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    monkeypatch.setattr(cli, "getpass", lambda prompt: "one-off-key")
    calls = []

    def request(method, url, **kwargs):
        calls.append(kwargs["headers"])
        return httpx.Response(200, json={"items": [], "pagination": {"page": 1, "total_pages": 0, "total": 0}})

    monkeypatch.setattr(cli.httpx, "request", request)
    assert cli.main(["tasks", "list", "--token"]) == 0
    assert calls == [{"Authorization": "Bearer one-off-key"}]


def test_auth_login(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    monkeypatch.setattr(cli, "getpass", lambda prompt: "password")
    client_type = httpx.Client
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/login"):
            assert json.loads(request.content) == {"username": "admin", "password": "password"}
            return httpx.Response(
                200, json={"user": {"id": 1}}, headers={"set-cookie": "ytp_session=temporary; Path=/"}
            )
        assert request.headers.get("cookie") == "ytp_session=temporary"
        if request.url.path.endswith("/api-keys"):
            assert json.loads(request.content) == {"name": "YTPTube CLI"}
            return httpx.Response(201, json={"key": "ytp_secret"})
        return httpx.Response(204)

    monkeypatch.setattr(
        cli.httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs)
    )
    assert cli.main(["config", "login", "--url", "https://example.test/prefix/", "--username", "admin"]) == 0
    assert [request.url.path for request in calls] == [
        "/prefix/api/auth/login",
        "/prefix/api/auth/api-keys",
        "/prefix/api/auth/logout",
    ]
    path = tmp_path / "cli.toml"
    assert cli.tomllib.loads(path.read_text())["token"] == "file:secrets/api_token"
    assert (tmp_path / "secrets" / "api_token").read_text() == "ytp_secret\n"
    assert stat.S_IMODE((tmp_path / "secrets").stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "secrets" / "api_token").stat().st_mode) == 0o600
    assert path.stat().st_mode & 0o777 == 0o600
    assert "ytp_secret" not in capsys.readouterr().out

    seen = []

    def request(method, url, **kwargs):
        seen.append(kwargs["headers"])
        return httpx.Response(200, json={"items": [], "pagination": {"page": 1, "total_pages": 0, "total": 0}})

    monkeypatch.setattr(cli.httpx, "request", request)
    assert cli.main(["tasks", "list"]) == 0
    assert seen == [{"Authorization": "Bearer ytp_secret"}]


def test_auth_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    passwords = iter(("password", "password"))
    monkeypatch.setattr(cli, "getpass", lambda prompt: next(passwords))
    client_type = httpx.Client
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path.endswith("/setup"):
            return httpx.Response(201, json={"user": {"id": 1}}, headers={"set-cookie": "ytp_session=s; Path=/"})
        if request.url.path.endswith("/api-keys"):
            return httpx.Response(201, json={"key": "ytp_new"})
        return httpx.Response(204)

    monkeypatch.setattr(
        cli.httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs)
    )
    assert cli.main(["config", "setup", "--username", "admin", "--name", "Laptop"]) == 0
    assert seen[0] == "/prefix/api/auth/setup"
    assert cli.tomllib.loads((tmp_path / "cli.toml").read_text())["token"] == "file:secrets/api_token"
    assert (tmp_path / "secrets" / "api_token").read_text() == "ytp_new\n"


def test_auth_http(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    monkeypatch.setattr(cli, "getpass", lambda prompt: "password")
    client_type = httpx.Client
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(401, json={"error": "Unauthorized."})

    monkeypatch.setattr(
        cli.httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs)
    )
    assert cli.main(["config", "login", "--url", "http://example.test/", "--username", "admin"]) == 1
    assert seen == ["http://example.test/api/auth/login"]
    assert "Unauthorized" in capsys.readouterr().err


def test_auth_failure(tmp_path, monkeypatch, capsys):
    path = tmp_path / "cli.toml"
    path.write_text('url = "http://127.0.0.1:8081/"\ntoken = "old"\n')
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    monkeypatch.setattr(cli, "getpass", lambda prompt: "wrong")
    client_type = httpx.Client
    monkeypatch.setattr(
        cli.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(lambda request: httpx.Response(401, json={"error": "Unauthorized."})),
            **kwargs,
        ),
    )
    assert cli.main(["config", "login", "--username", "admin"]) == 1
    assert cli.tomllib.loads(path.read_text())["token"] == "old"
    assert "Unauthorized" in capsys.readouterr().err


def test_db_readonly(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("create table data (value text)")
    cfg = config(tmp_path)
    cfg.db_file = str(db)
    monkeypatch.setattr(cli.Config, "get_instance", lambda: cfg)
    assert cli.main(["db", "query", "insert into data values ('x')"]) == 1


def test_db_write(tmp_path, monkeypatch, capsys):
    db = tmp_path / "db.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("create table data (value text)")
    cfg = config(tmp_path)
    cfg.db_file = str(db)
    monkeypatch.setattr(cli.Config, "get_instance", lambda: cfg)
    assert cli.main(["db", "query", "insert into data values ('x')", "--write"]) == 0
    capsys.readouterr()
    with sqlite3.connect(db) as connection:
        assert connection.execute("select value from data").fetchone() == ("x",)

    assert cli.main(["db", "query", "update data set value = 'y'", "--write", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"affected": 1}
    with sqlite3.connect(db) as connection:
        assert connection.execute("select value from data").fetchone() == ("y",)


def test_db_tables(tmp_path, monkeypatch, capsys):
    db = tmp_path / "db.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("create table data (value text)")
    cfg = config(tmp_path)
    cfg.db_file = str(db)
    monkeypatch.setattr(cli.Config, "get_instance", lambda: cfg)
    assert cli.main(["db", "tables", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"name": "data"}]


def test_db_blob(tmp_path, monkeypatch, capsys):
    db = tmp_path / "db.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("create table data (value blob)")
        connection.execute("insert into data values (?)", (b"\x00\xff",))
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    assert cli.main(["db", "query", "select value from data", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"value": "00ff"}]


def test_download_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))

    response = httpx.Response(
        200,
        json={
            "items": [{"id": "1", "status": "queued", "title": "Demo", "cookies": "secret"}],
            "pagination": {"page": 2, "total_pages": 3, "total": 5},
        },
    )

    seen = {}

    def request(method, url, **kwargs):
        seen.update(method=method, url=url, params=kwargs["params"])
        return response

    monkeypatch.setattr(cli.httpx, "request", request)
    assert cli.main(["downloads", "list", "--page", "2", "--json"]) == 0
    assert seen["params"] == {"type": "queue", "page": 2, "per_page": 50, "order": "DESC"}
    assert json.loads(capsys.readouterr().out)["items"][0]["cookies"] == "secret"


def test_api_error_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    monkeypatch.setattr(
        cli.httpx,
        "request",
        lambda *args, **kwargs: httpx.Response(401, json={"error": "Unauthorized.", "code": "auth"}),
    )
    assert cli.main(["tasks", "list", "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == {"error": "Unauthorized.", "code": "auth"}


def test_api_not_modified(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    seen = {}

    def request(method, url, **kwargs):
        seen.update(method=method, path=httpx.URL(url).path, body=kwargs["json"])
        return httpx.Response(304)

    monkeypatch.setattr(cli.httpx, "request", request)
    assert cli.main(["downloads", "update", "history-1", "--data", '{"status":"paused"}', "--json"]) == 0
    assert seen == {"method": "POST", "path": "/prefix/api/history/history-1", "body": {"status": "paused"}}
    assert json.loads(capsys.readouterr().out) is None


def test_download_batch_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    response = {"items": {"status": "error", "missing": "not found"}, "deleted": 0}
    monkeypatch.setattr(cli.httpx, "request", lambda *args, **kwargs: httpx.Response(200, json=response))
    assert cli.main(["downloads", "batch", "missing", "--delete", "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == response


def test_download_batch_status_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.Config, "get_instance", lambda: config(tmp_path))
    response = {"status": "error", "missing": "not found"}
    monkeypatch.setattr(cli.httpx, "request", lambda *args, **kwargs: httpx.Response(200, json=response))
    assert cli.main(["downloads", "batch", "missing", "--cancel", "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == response
