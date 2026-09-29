from __future__ import annotations

import argparse
import json
from collections.abc import Callable

Request = Callable[..., object]


def output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print the complete API response as JSON.",
    )
    parser.add_argument("--url", default=argparse.SUPPRESS, help="Override the configured YTPTube server URL.")
    parser.add_argument(
        "--token",
        nargs="?",
        const="",
        default=argparse.SUPPRESS,
        help="Override the API token; prompt if no value is given.",
    )


def register(sub: argparse._SubParsersAction, output_fn: Callable[[argparse.ArgumentParser], None] = output) -> None:
    def group(name: str, description: str) -> argparse._SubParsersAction:
        parser = sub.add_parser(name, help=description, description=description)
        output_fn(parser)
        return parser.add_subparsers(dest=f"{name.replace('-', '_')}_command")

    system = group("system", "Inspect and control the server (default: status).")
    system_help = {
        "status": "Show server version, queue state, and download count.",
        "pause": "Pause the global download queue.",
        "resume": "Resume the download queue.",
        "diagnostics": "Run health and dependency checks.",
        "limits": "Show download and extraction limits.",
        "check-updates": "Check for app and yt-dlp updates.",
        "shutdown": "Stop the server.",
    }
    for name in ("status", "pause", "resume", "diagnostics", "limits", "check-updates", "shutdown"):
        description = system_help[name]
        output_fn(system.add_parser(name, help=description, description=description))
    stats = group("stats", "Show server resource usage (default: latest).")
    history = stats.add_parser(
        "history", help="Show recent resource usage samples.", description="Show recent resource usage samples."
    )
    output_fn(history)
    history.add_argument("--range", default="30m", help="Time window (default: 30m).")
    for name, description in (
        ("latest", "Show the latest resource usage sample."),
        ("bottlenecks", "Show resource bottlenecks."),
    ):
        output_fn(stats.add_parser(name, help=description, description=description))
    logs = group("logs", "Read logs and manage log levels (default: show).")
    show = logs.add_parser(
        "show",
        help="Show recent server log entries.",
        description="Show the most recent server log entries in chronological order.",
    )
    output_fn(show)
    show.add_argument("--offset", type=int, help="Skip this many newest log entries to see older logs.")
    show.add_argument("--limit", type=int, help="Maximum log entries to show (server default: 100).")
    level = logs.add_parser(
        "level",
        help="Show configured and active log levels.",
        description="Show configured and active log levels and available settings.",
    )
    output_fn(level)
    set_level = logs.add_parser(
        "set-level",
        help="Change the active log level.",
        description="Change the server's active log level; use 'logs level' to see supported values.",
    )
    output_fn(set_level)
    set_level.add_argument("level", help="New log level (see 'logs level').")
    account = group("account", "Manage your account, API keys, and sessions (default: me).")
    for name in ("me",):
        output_fn(
            account.add_parser(
                name, help="Show the signed-in account.", description="Show the account associated with this API token."
            )
        )
    edit = account.add_parser("edit", help="Update your account.", description="Update your account using a JSON file.")
    output_fn(edit)
    edit.add_argument("--file", required=True, help="Path to a JSON file with account changes.")
    keys = account.add_parser("keys", help="Manage API keys.", description="List, create, or delete API keys.")
    output_fn(keys)
    keys_sub = keys.add_subparsers(dest="keys_command", required=True)
    output_fn(keys_sub.add_parser("list", help="List your API keys.", description="List your API keys and their IDs."))
    create = keys_sub.add_parser(
        "create",
        help="Create a new API key.",
        description="Create a new API key; its value is shown once and cannot be retrieved later.",
    )
    output_fn(create)
    create.add_argument("name", help="Label for the new key.")
    delete = keys_sub.add_parser("delete", help="Delete an API key.", description="Delete an API key.")
    output_fn(delete)
    delete.add_argument("id", help="API key ID from 'account keys list'.")
    sessions = account.add_parser(
        "sessions", help="Manage sign-in sessions.", description="List or revoke sign-in sessions."
    )
    output_fn(sessions)
    ss = sessions.add_subparsers(dest="sessions_command", required=True)
    output_fn(ss.add_parser("list", help="List sign-in sessions.", description="List sign-in sessions and their IDs."))
    sd = ss.add_parser("delete", help="Revoke a sign-in session.", description="Revoke a sign-in session.")
    output_fn(sd)
    sd.add_argument("id", help="Session ID from 'account sessions list'.")


def run(args: argparse.Namespace, request: Request) -> object:
    command = args.command
    action = getattr(args, f"{command.replace('-', '_')}_command")
    action = action or {"logs": "show", "account": "me"}.get(command)
    method, path, params, body = "GET", "", None, None
    if command == "system":
        action = action or "status"
        path = {"status": "configuration", "check_updates": "check-updates"}.get(action, action)
        method = "POST" if action in {"pause", "resume", "check_updates", "check-updates", "shutdown"} else "GET"
        path = f"/api/system/{path}"
        body = {} if method == "POST" else None
    elif command == "stats":
        action = action or "latest"
        path = f"/api/stats/{action.replace('_', '-')}"
        params = {"range": args.range} if action == "history" else None
    elif command == "logs":
        if action == "show":
            path, params = (
                "/api/logs/",
                {
                    k: v
                    for k, v in {"offset": getattr(args, "offset", None), "limit": getattr(args, "limit", None)}.items()
                    if v is not None
                },
            )
        elif action == "level":
            path = "/api/logs/level"
        else:
            method, path = "POST", f"/api/logs/level/{args.level}"
    elif command == "account":
        if action == "edit":
            method, path = "PATCH", "/api/auth/account"
            with open(args.file, encoding="utf-8") as file:
                body = json.load(file)
            return request(method, path, params=None, body=body)
        path = "/api/auth/me" if action == "me" else f"/api/auth/{'api-keys' if action == 'keys' else 'sessions'}"
        nested = getattr(args, f"{action}_command", None)
        if action == "keys" and nested == "create":
            method, body = "POST", {"name": args.name}
        elif (action == "keys" and nested == "delete") or (action == "sessions" and nested == "delete"):
            method, path = "DELETE", f"{path}/{args.id}"
    return request(method, path, params=params, body=body)


def human(args: argparse.Namespace, value: object) -> str:
    command = getattr(args, "command", "")
    if value is None:
        if command == "logs" and getattr(args, "logs_command", "") == "set-level":
            return "Log level updated."
        return "Done"

    def display(item: object, level: int = 0) -> str:
        if isinstance(item, dict):
            if not item:
                return "{}"
            pad = "  " * (level + 1)
            return "\n".join(f"{pad}{key}: {display(val, level + 1)}" for key, val in item.items())
        if isinstance(item, list):
            if not item:
                return "[]"
            pad = "  " * (level + 1)
            return "\n".join(f"{pad}- {display(entry, level + 1)}" for entry in item)
        return str(item)

    if command == "system" and isinstance(value, dict):
        if getattr(args, "system_command", "") in {"check-updates", "check_updates"}:
            return "\n".join(
                f"{name}: {item.get('status', 'unknown')} | current: {item.get('current_version', '?')}"
                + (f" | new: {item['new_version']}" if item.get("new_version") else "")
                for name in ("app", "ytdlp")
                if isinstance(item := value.get(name), dict)
            )
        if "app" in value:
            app = value["app"] if isinstance(value["app"], dict) else {}
            return f"version: {app.get('app_version', 'unknown')}\npaused: {value.get('paused', False)}  history: {value.get('history_count', 0)}"
        if "summary" in value and isinstance(value["summary"], dict):
            summary = value["summary"]
            lines = [
                (
                    f"status: {value.get('status', 'unknown')}\n"
                    f"checks: {summary.get('total', 0)}  failed: {summary.get('fail', 0)}  warnings: {summary.get('warn', 0)}"
                )
            ]
            lines.extend(
                f"- {check.get('label', check.get('id', 'check'))}: {check.get('status', 'unknown')} - {check.get('message', '')}"
                for check in value.get("checks", [])
                if isinstance(check, dict)
            )
            lines.extend(
                f"{section}:\n{display(value[section], 1)}"
                for section in ("runtime", "requirements", "stats")
                if section in value
            )
            return "\n".join(lines)
        if "downloads" in value and isinstance(value["downloads"], dict):
            global_limits = value["downloads"].get("global", {})
            return (
                f"paused: {value['downloads'].get('paused', False)}\n"
                f"active: {global_limits.get('active', 0)}  queued: {global_limits.get('queued', 0)}  "
                f"limit: {global_limits.get('limit', 0)}"
            )
        if "version" in value:
            return f"version: {value['version']}"
        return str(value.get("message", "Done"))
    if command == "account" and isinstance(value, dict):
        if "key" in value or "api_key" in value:
            name = value.get("name", "")
            return f"API key created: {name}\nkey: {value.get('key', value.get('api_key'))}"
        if "user" in value and isinstance(value["user"], dict):
            user = value["user"]
            return f"id: {user.get('id', '')}\nusername: {user.get('username', '')}"
        if "items" in value and isinstance(value["items"], list):
            action = getattr(args, "account_command", "")
            fields = (
                ("name", "hint", "created_at", "last_used_at")
                if action == "keys"
                else ("ip", "user_agent", "created_at", "expires_at", "current")
            )
            lines = []
            for item in value["items"]:
                if not isinstance(item, dict):
                    continue
                lines.append(f"ID: {item.get('id', '?')}")
                lines.extend(f"  {key.replace('_', ' ')}: {item[key]}" for key in fields if item.get(key) is not None)
            return "\n".join(lines) or f"No {action or 'account items'}."
    if command == "logs" and isinstance(value, dict) and isinstance(value.get("logs"), list):
        text = "\n".join(
            f"{str(item.get('datetime') or '')[11:19]}  {str(item.get('level') or '').upper():<5}  "
            f"{item.get('message', '')}"
            for item in value["logs"]
            if isinstance(item, dict)
        )
        if not text:
            return "No log entries."
        if not value.get("end_is_reached") and value.get("next_offset") is not None:
            text += f"\nNext page: --offset {value['next_offset']}"
        return text
    if command == "logs" and getattr(args, "logs_command", "") == "level" and isinstance(value, dict):
        return (
            f"configured: {value.get('conf', 'unknown')}\n"
            f"active: {value.get('active', 'unknown')}\n"
            f"available: {', '.join(str(level) for level in value.get('levels', []))}"
        )
    if command == "stats" and isinstance(value, dict):
        if not value:
            return "No statistics available."
        if getattr(args, "stats_command", "") == "history" and isinstance(value.get("samples"), list):
            fields = ("active_jobs", "queued_jobs", "process_cpu_percent", "rss_mb", "memory_percent")
            return (
                "\n".join(
                    f"{sample.get('ts', '?')}: "
                    + "  ".join(f"{field}={sample[field]}" for field in fields if field in sample)
                    for sample in value["samples"]
                    if isinstance(sample, dict)
                )
                or "No statistics available."
            )
        if "bottlenecks" in value:
            return "\n".join(f"{key}:\n{display(item, 1)}" for key, item in value.items())
        return "\n".join(f"{key.replace('_', ' ')}: {display(item, 1)}" for key, item in value.items())
    allowed = {
        "stats": {
            "ts",
            "active_jobs",
            "queued_jobs",
            "process_cpu_percent",
            "rss_mb",
            "memory_percent",
            "uptime_seconds",
        },
        "logs": {
            "id",
            "datetime",
            "level",
            "logger",
            "message",
            "fields",
            "offset",
            "limit",
            "next_offset",
            "end_is_reached",
        },
        "account": {"id", "name", "username", "created_at", "expires_at", "status", "hint"},
    }.get(command, set())

    def safe(item: object) -> object:
        if isinstance(item, dict):
            return {key: safe(val) for key, val in item.items() if key in allowed}
        if isinstance(item, list):
            return [safe(entry) for entry in item]
        return item

    value = safe(value)
    if isinstance(value, dict):
        return "\n".join(f"{key}: {display(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(display(item) for item in value)
    return str(value)
