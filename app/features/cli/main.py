from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
import tomllib
from getpass import getpass
from pathlib import Path
from urllib.parse import quote

import httpx

from app.features.cli import downloads, operations, resources
from app.library.config import Config
from app.library.Utils import resolve_secret


def _settings(config: Config) -> tuple[dict[str, str], Path]:
    path = Path(config.config_path) / "cli.toml"
    if not path.exists():
        return {}, path
    try:
        with path.open("rb") as file:
            values = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        message = f"invalid CLI configuration: {exc}"
        raise ValueError(message) from exc
    if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in values.items()):
        message = "invalid CLI configuration: values must be strings"
        raise ValueError(message)
    return values, path


def _default_url(config: Config) -> str:
    host = config.host if config.host not in {"0.0.0.0", "::", ""} else "127.0.0.1"
    try:
        if ipaddress.ip_address(host).version == 6:
            host = f"[{host}]"
    except ValueError:
        if ":" in host:
            host = "127.0.0.1"
    base = config.base_path if config.base_path.startswith("/") else f"/{config.base_path}"
    return f"http://{host}:{config.port}{base}"


def _token_input(value: str | None) -> str | None:
    if value is None or value:
        return value
    token = getpass("API token: ").strip()
    if not token:
        message = "API token is required"
        raise ValueError(message)
    return token


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli",
        description="Manage ytptube from the command line (source: uv run cli.py).",
    )
    parser.add_argument("--url", help="Server URL (overrides saved configuration and YTP_API_URL)")
    parser.add_argument("--token", nargs="?", const="", help="API token (prompts if the value is omitted)")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Print the response as JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    def output(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--json",
            dest="json_output",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Print the response as JSON",
        )
        command.add_argument("--url", default=argparse.SUPPRESS, help="Server URL for this request")
        command.add_argument(
            "--token",
            nargs="?",
            const="",
            default=argparse.SUPPRESS,
            help="API token (prompts if the value is omitted)",
        )

    downloads.register(sub, output)
    resources.register(sub, output)
    operations.register(sub, output)
    cli_config = sub.add_parser(
        "config",
        help="Manage the server URL and API token.",
        description="View or save the server URL and API token, or create an API key.",
    )
    output(cli_config)
    config_sub = cli_config.add_subparsers(dest="config_command", required=True)
    show_config = config_sub.add_parser(
        "show",
        help="Show saved connection settings.",
        description="Show the saved server URL and whether an API token is configured.",
    )
    output(show_config)
    set_config = config_sub.add_parser(
        "set",
        help="Save a server URL or API token.",
        description="Save a server URL or API token without contacting the server.",
    )
    set_config.add_argument("--url", dest="save_url", help="HTTP(S) server URL")
    set_config.add_argument(
        "--token", dest="save_token", nargs="?", const="", help="API token (prompts if the value is omitted)"
    )
    set_config.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print the saved configuration as JSON",
    )
    for name in ("login", "setup"):
        action = config_sub.add_parser(
            name,
            help=(
                "Log in to an existing account and save an API key."
                if name == "login"
                else "Create the initial account and save an API key."
            ),
            description=(
                "Log in to an existing account and save a new API key."
                if name == "login"
                else "Create the initial account and save a new API key."
            ),
        )
        output(action)
        action.add_argument("--username", help="Account username (prompts if omitted)")
        action.add_argument("--name", default="YTPTube CLI", help="Name assigned to the API key")
    db = sub.add_parser("db", help="Inspect the SQLite database.", description="Inspect the SQLite database.")
    output(db)
    db_sub = db.add_subparsers(dest="db_command", required=True)
    tables = db_sub.add_parser(
        "tables", help="List database tables.", description="List tables in the SQLite database."
    )
    output(tables)
    query = db_sub.add_parser(
        "query",
        help="Run a SQL statement.",
        description="Run a SQL statement against the SQLite database",
    )
    output(query)
    query.add_argument("sql", help="SQL statement to execute")
    query.add_argument("--write", action="store_true", help="Allow writes")
    info = sub.add_parser(
        "info", help="Show local paths and server URL.", description="Show local paths and the server URL in use."
    )
    output(info)
    return parser


class _RequestError(RuntimeError):
    def __init__(self, message: str, payload: object = None, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.payload = payload
        self.status_code = status_code


def _request(
    method: str,
    url: str,
    path: str,
    token: str | None,
    *,
    params: dict | None = None,
    body: object = None,
    json_output: bool = False,
) -> object:
    try:
        response = httpx.request(
            method,
            f"{url.rstrip('/')}/{path.lstrip('/')}",
            params=params,
            json=body,
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=30,
        )
    except (httpx.HTTPError, ValueError) as exc:
        message = f"Request failed: {exc}"
        raise _RequestError(message, {"error": message}) from exc
    try:
        value = response.json() if response.content else None
    except ValueError as exc:
        message = "API returned invalid JSON"
        raise _RequestError(message, {"error": message}) from exc
    if getattr(response, "status_code", None) == 304:
        return value
    if not response.is_success:
        detail = value.get("error") if isinstance(value, dict) else None
        message = f"HTTP {response.status_code}{f': {detail}' if detail else ''}"
        raise _RequestError(
            message,
            value if json_output and value is not None else {"error": message},
            status_code=response.status_code,
        )
    return value


def _display(value: object, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(value, indent=2))  # noqa: T201
    elif isinstance(value, list):
        if not value:
            print("No results.")  # noqa: T201
        for number, row in enumerate(value, 1):
            if isinstance(row, dict):
                fields = list(row.items())
                if not fields:
                    print(f"{number}.")  # noqa: T201
                else:
                    key, item = fields[0]
                    if isinstance(item, (dict, list)):
                        print(f"{number}.")  # noqa: T201
                        _display_field(key, item)
                    else:
                        print(f"{number}. {key}: {item}")  # noqa: T201
                    for key, item in fields[1:]:
                        _display_field(f"  {key}", item)
            else:
                print(f"{number}. {row}")  # noqa: T201
    elif isinstance(value, dict):
        for key, item in value.items():
            _display_field(key, item)


def _display_field(key: object, value: object) -> None:
    label = str(key)
    if isinstance(value, dict):
        print(f"{label}:")  # noqa: T201
        for child, item in value.items():
            _display_field(f"  {child}", item)
    elif isinstance(value, list):
        print(f"{label}:" if value else f"{label}: none")  # noqa: T201
        for item in value:
            if isinstance(item, (dict, list)):
                _display_field("-", item)
            else:
                print(f"- {item}")  # noqa: T201
    else:
        print(f"{label}: {value}")  # noqa: T201


def _db(args: argparse.Namespace, db_file: str) -> int:
    path = Path(db_file)
    if not path.exists():
        print(f"error: database does not exist: {path}", file=sys.stderr)  # noqa: T201
        return 1
    write = args.db_command == "query" and args.write
    try:
        safe_path = quote(path.resolve().as_posix(), safe="/:")
        with sqlite3.connect(f"file:{safe_path}?mode={'rw' if write else 'ro'}", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                if args.db_command == "tables"
                else args.sql
            )
            if args.db_command == "tables" and not args.json_output:
                result = [row["name"] for row in cursor]
            elif cursor.description:
                result = [
                    {key: item.hex() if isinstance(item, bytes) else item for key, item in dict(row).items()}
                    for row in cursor
                ]
            else:
                result = {"affected": cursor.rowcount}
            _display(result, json_output=args.json_output)
    except (sqlite3.Error, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        return 1
    return 0


def _save_settings(path: Path, values: dict[str, str]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            for key, value in values.items():
                name = key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else json.dumps(key)
                file.write(f"{name} = {json.dumps(value)}\n")
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _warn_secrets(path: Path) -> None:
    directory = path.parent / "secrets"
    for item in (directory, directory / "api_token"):
        try:
            mode = item.lstat().st_mode
            if stat.S_ISLNK(mode) or stat.S_IMODE(mode) & 0o077:
                print(f"warning: secret path may be accessible to others: {item}", file=sys.stderr)  # noqa: T201
        except FileNotFoundError:
            continue
        except OSError as exc:
            print(f"warning: cannot inspect secret path {item}: {exc}", file=sys.stderr)  # noqa: T201


def _save_token(path: Path, token: str) -> str:
    directory = path.parent / "secrets"
    directory.mkdir(mode=0o700, exist_ok=True)
    secret = directory / "api_token"
    mode = stat.S_IMODE(secret.stat().st_mode) if secret.exists() else 0o600
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as file:
            temporary = Path(file.name)
            file.write(token + "\n")
        temporary.chmod(mode)
        temporary.replace(secret)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return "file:secrets/api_token"


def _auth(args: argparse.Namespace, url: str, settings: dict[str, str], path: Path) -> int:
    username = args.username or input("Username: ").strip()
    password = getpass("Password: ")
    if args.config_command == "setup" and password != getpass("Confirm password: "):
        message = "Passwords do not match"
        raise ValueError(message)
    if not username or not password:
        message = "Username and password are required"
        raise ValueError(message)

    def failure(response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            data = None
        detail = data.get("error") if isinstance(data, dict) else None
        return f"{response.status_code}: {detail or response.reason_phrase}"

    with httpx.Client(base_url=url.rstrip("/") + "/", timeout=30, follow_redirects=False) as client:
        response = client.post(f"api/auth/{args.config_command}", json={"username": username, "password": password})
        if not response.is_success:
            message = f"Authentication failed ({failure(response)})"
            raise ValueError(message)
        try:
            response = client.post("api/auth/api-keys", json={"name": args.name})
            if not response.is_success:
                message = f"API key creation failed ({failure(response)})"
                raise ValueError(message)
            data = response.json()
            token = data.get("key") if isinstance(data, dict) else None
            if not isinstance(token, str) or not token:
                message = "API key creation returned no key"
                raise ValueError(message)
            _save_settings(path, {**settings, "url": url, "token": _save_token(path, token)})
        finally:
            try:
                client.post("api/auth/logout")
            except httpx.HTTPError:
                pass

    result = {"authenticated": True, "key_name": args.name, "config_file": str(path)}
    if args.json_output:
        print(json.dumps(result, indent=2))  # noqa: T201
    else:
        print(f"API key saved to {path}")  # noqa: T201
    return 0


def _config(args: argparse.Namespace, config: Config, settings: dict[str, str], path: Path, url: str) -> int:
    if args.config_command in {"login", "setup"}:
        return _auth(args, url, settings, path)

    if args.config_command == "set":
        new_url: str | None = args.save_url if args.save_url is not None else args.url
        new_token: str | None = _token_input(args.save_token if args.save_token is not None else args.token)
        if new_url is None and new_token is None:
            message = "Provide --url or --token to config set"
            raise ValueError(message)

        values: dict[str, str] = {**settings, "url": settings.get("url") or _default_url(config)}
        if new_url is not None:
            target = httpx.URL(new_url)
            if target.scheme not in {"http", "https"} or not target.host or target.query or target.fragment:
                message = "--url must be an HTTP(S) server URL without query or fragment"
                raise ValueError(message)
            normalized = new_url.rstrip("/") + "/"
            if normalized != values["url"] and new_token is None:
                values.pop("token", None)
            values["url"] = normalized
        if new_token is not None:
            values["token"] = _save_token(path, new_token)
        elif (token := values.get("token")) is not None and not token.startswith("file:"):
            values["token"] = _save_token(path, token)
        _save_settings(path, values)
        if settings.get("token") == "file:secrets/api_token" and "token" not in values:
            (path.parent / "secrets" / "api_token").unlink(missing_ok=True)
        settings = values

    result = {"url": settings.get("url") or _default_url(config), "token_configured": bool(settings.get("token"))}
    _display(result, json_output=args.json_output)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = Config.get_instance()
        toml, config_file = _settings(config)
        _warn_secrets(config_file)
        url = args.url or os.environ.get("YTP_API_URL") or toml.get("url") or _default_url(config)
        if args.command == "config":
            if args.config_command in {"set", "login", "setup"}:
                config_file.parent.mkdir(parents=True, exist_ok=True)
            return _config(args, config, toml, config_file, url)
        if args.command == "db":
            return _db(args, os.environ.get("YTP_DB_FILE", config.db_file))
        if args.command == "info":
            _display(
                {"config_path": config.config_path, "db_file": config.db_file, "api_url": url},
                json_output=args.json_output,
            )
            return 0
        raw_token = _token_input(args.token) or os.environ.get("YTP_API_TOKEN") or toml.get("token")
        token = resolve_secret(raw_token, base_dir=config_file.parent) if raw_token else None

        modules = {
            "downloads": downloads,
            "tasks": resources,
            "task-definitions": resources,
            "presets": resources,
            "conditions": resources,
            "dl-fields": resources,
            "notifications": resources,
            "system": operations,
            "stats": operations,
            "logs": operations,
            "account": operations,
        }

        def request(method: str, path: str, *, params: dict | None = None, body: object = None) -> object:
            return _request(method, url, path, token, params=params, body=body, json_output=args.json_output)

        module = modules[args.command]
        value = module.run(args, request)
        if args.json_output:
            _display(value, json_output=True)
        else:
            print(module.human(args, value))  # noqa: T201
        if (
            args.command == "downloads"
            and args.downloads_command == "batch"
            and isinstance(value, dict)
            and (
                value.get("status") == "error"
                or (isinstance(value.get("items"), dict) and value["items"].get("status") == "error")
            )
        ):
            return 1
        return 0
    except _RequestError as exc:
        if args.json_output:
            print(json.dumps(exc.payload), file=sys.stdout)  # noqa: T201
        else:
            print(f"error: {exc}", file=sys.stderr)  # noqa: T201
            if exc.status_code == 401:
                print("Run config login to save a valid API key.", file=sys.stderr)  # noqa: T201
        return 1
    except (OSError, ValueError, EOFError, KeyboardInterrupt, RuntimeError, httpx.HTTPError) as exc:
        if args.json_output:
            print(json.dumps({"error": str(exc)}), file=sys.stdout)  # noqa: T201
        else:
            print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
