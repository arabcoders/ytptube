from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

Request = Callable[..., object]

_RESOURCES = {
    "tasks": "/api/tasks/",
    "task-definitions": "/api/tasks/definitions/",
    "presets": "/api/presets/",
    "conditions": "/api/conditions/",
    "dl-fields": "/api/dl_fields/",
    "notifications": "/api/notifications/",
}


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


def _body(args: argparse.Namespace, required: bool = True) -> object:
    data, file = getattr(args, "data", None), getattr(args, "file", None)
    if data is not None:
        return json.loads(data)
    if file is None:
        if required:
            message = "one of --data or --file is required"
            raise ValueError(message)
        return None
    try:
        return json.loads(Path(file).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = f"invalid JSON in --file {file}: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        raise ValueError(message) from exc


def _resource_parser(
    parent: argparse._SubParsersAction, name: str, add_output: Callable[[argparse.ArgumentParser], None]
) -> None:
    group_help = {
        "tasks": "Scheduled downloads and their settings.",
        "task-definitions": "Rules for matching URLs to extraction methods.",
        "presets": "Reusable download settings.",
        "conditions": "Rules for filtering extracted metadata.",
        "dl-fields": "Fields available to download templates.",
        "notifications": "Rules for sending download notifications.",
    }[name]
    parser = parent.add_parser(name, help=group_help, description=group_help)
    add_output(parser)
    actions = parser.add_subparsers(dest="action", required=True)
    subjects = {
        "tasks": ("scheduled tasks", "scheduled task"),
        "task-definitions": ("task definitions", "task definition"),
        "presets": ("presets", "preset"),
        "conditions": ("conditions", "condition"),
        "dl-fields": ("download fields", "download field"),
        "notifications": ("notification rules", "notification rule"),
    }
    plural, singular = subjects[name]
    descriptions = {
        "list": f"List {plural}.",
        "show": f"Show a {singular}.",
        "create": f"Create a {singular}.",
        "update": f"Update a {singular}.",
        "delete": f"Delete a {singular}.",
    }
    if name == "tasks":
        descriptions["update"] = "Change a task's URL, schedule, or settings."
    for action in ("list", "show", "create", "update", "delete"):
        item = actions.add_parser(action, help=descriptions[action], description=descriptions[action])
        add_output(item)
        if action in {"list"}:
            item.add_argument("--page", type=int, default=1, help="Page number (default: 1).")
            item.add_argument("--per-page", type=int, default=50, help="Items per page (default: 50).")
            if name == "presets":
                item.add_argument("--exclude-defaults", action="store_true", help="Hide built-in presets.")
            if name == "task-definitions":
                item.add_argument("--include-definition", action="store_true", help="Include definition documents.")
        if action in {"show", "update", "delete"}:
            item.add_argument("id", type=int, help=f"ID from '{name} list'.")
        if action in {"create", "update"}:
            body = item.add_mutually_exclusive_group(required=True)
            body.add_argument("--data", help="JSON object for the request body.")
            body.add_argument("--file", help="Path to a JSON file for the request body.")

    extras = {
        "tasks": ("inspect", "mark", "unmark", "metadata"),
        "task-definitions": ("inspect", "impersonate-targets"),
        "conditions": ("test",),
        "notifications": ("events", "test"),
    }
    descriptions = {
        ("tasks", "inspect"): "Preview which task handler matches a URL without starting downloads.",
        ("tasks", "mark"): "Mark all items from a scheduled task as downloaded.",
        ("tasks", "unmark"): "Mark a scheduled task's items as not downloaded.",
        (
            "tasks",
            "metadata",
        ): "Fetch a task's source metadata and write NFO, thumbnail, and JSON files to its folder. Existing files are overwritten.",
        (
            "task-definitions",
            "inspect",
        ): "Preview a URL using a saved or supplied task definition without starting downloads.",
        ("task-definitions", "impersonate-targets"): "List supported HTTP client impersonation targets.",
        ("conditions", "test"): "Test a condition against metadata extracted from a URL.",
        ("notifications", "events"): "List events available to notification rules.",
        ("notifications", "test"): "Send a test notification using the configured rules.",
    }
    for action in extras.get(name, ()):
        description = descriptions[name, action]
        item = actions.add_parser(action, help=description, description=description)
        add_output(item)
        if action in {"mark", "unmark", "metadata"}:
            item.add_argument("id", type=int, help="Numeric task ID from 'tasks list' (not a download ID).")
        if action == "inspect" or (action == "test" and name == "conditions"):
            body = item.add_mutually_exclusive_group(required=False)
            if action == "inspect" and name == "task-definitions":
                hint = 'JSON with "url" and either "definition_id" or "document".'
                item.add_argument("definition_id", nargs="?", help="Saved task definition ID.")
                item.add_argument("source_url", nargs="?", help="URL to inspect.")
            elif action == "test":
                hint = 'JSON with "url" and "condition".'
                item.add_argument("test_url", nargs="?", help="URL to test.")
                item.add_argument("condition", nargs="?", help="Condition expression to test.")
            else:
                hint = 'JSON with "url" to inspect; may include "static_only" or "resolve_ids".'
                item.add_argument("inspect_url", nargs="?", help="URL to inspect.")
            body.add_argument("--data", help=hint)
            body.add_argument("--file", help=f"Path to a file containing {hint}")
            if action == "inspect" and name == "tasks":
                item.add_argument("--preset", help="Preset to use for inspection.")
                item.add_argument("--static-only", action="store_true", help="Only match a handler without extracting.")
                item.add_argument(
                    "--no-resolve-ids",
                    action="store_true",
                    help="Skip checking whether extracted items were previously downloaded.",
                )
            if action == "test" and name == "conditions":
                item.add_argument("--preset", help="Preset to use for extraction.")
            if action == "inspect" and name == "task-definitions":
                item.add_argument("--preset", help="Preset to use for inspection.")
                item.add_argument(
                    "--no-resolve-ids",
                    action="store_true",
                    help="Skip checking whether extracted items were previously downloaded.",
                )


def register(sub: argparse._SubParsersAction, output_fn: Callable[[argparse.ArgumentParser], None] = output) -> None:
    for name in _RESOURCES:
        _resource_parser(sub, name, output_fn)


def run(args: argparse.Namespace, request: Request) -> object:
    resource = args.command
    base = _RESOURCES[resource]
    action = args.action
    identifier = getattr(args, "id", None)
    if identifier is not None and (not isinstance(identifier, int) or identifier < 0):
        message = f"resource id must be numeric: {identifier}"
        raise ValueError(message)
    path = base if action in {"list", "create"} else f"{base}{identifier}"
    params = None
    body = None
    method = "GET"
    if action == "list":
        params = {"page": args.page, "per_page": args.per_page}
        if resource == "presets" and args.exclude_defaults:
            params["exclude_defaults"] = True
        if resource == "task-definitions" and args.include_definition:
            params["include"] = "definition"
    elif action in {"create", "update"}:
        method = {"create": "POST", "update": "PATCH"}[action]
        body = _body(args)
    elif action == "delete":
        method = "DELETE"
    elif action == "inspect":
        method, path = "POST", f"{base}inspect"
        body = _body(args, required=False)
        if resource == "tasks":
            if body is not None and args.inspect_url is not None:
                message = "URL cannot be combined with --data or --file"
                raise ValueError(message)
            if body is None:
                if args.inspect_url is None:
                    message = "URL or one of --data or --file is required"
                    raise ValueError(message)
                body = {"url": args.inspect_url}
                if args.preset:
                    body["preset"] = args.preset
                if args.static_only:
                    body["static_only"] = True
                if args.no_resolve_ids:
                    body["resolve_ids"] = False
        elif resource == "task-definitions":
            if body is not None and (args.definition_id is not None or args.source_url is not None):
                message = "ID and URL cannot be combined with --data or --file"
                raise ValueError(message)
            if body is None:
                if args.definition_id is None or args.source_url is None:
                    message = "definition ID and URL, or one of --data or --file is required"
                    raise ValueError(message)
                if not args.definition_id.isdigit():
                    message = f"resource id must be numeric: {args.definition_id}"
                    raise ValueError(message)
                body = {"definition_id": int(args.definition_id), "url": args.source_url}
            if args.preset:
                body["preset"] = args.preset
            if args.no_resolve_ids:
                body["resolve_ids"] = False
    elif action == "mark":
        method, path = "POST", f"{base}{identifier}/mark"
    elif action == "unmark":
        method, path = "DELETE", f"{base}{identifier}/mark"
    elif action == "metadata":
        method, path = "POST", f"{base}{identifier}/metadata"
    elif action == "impersonate-targets":
        path = f"{base}impersonate-targets"
        params = {}
    elif action == "events":
        path = f"{base}events/"
        params = {}
    elif action == "test":
        method = "POST"
        path = f"{base}test/"
        if resource == "conditions":
            body = _body(args, required=False)
            if body is not None and args.test_url is not None:
                message = "URL cannot be combined with --data or --file"
                raise ValueError(message)
            if body is None:
                if args.test_url is None or not getattr(args, "condition", None):
                    message = "URL and condition are required"
                    raise ValueError(message)
                body = {"url": args.test_url, "condition": args.condition}
                if args.preset:
                    body["preset"] = args.preset
    return request(method, path, params=params, body=body)


def human(args: argparse.Namespace, value: object) -> str:
    if getattr(args, "json_output", False):
        return json.dumps(value, indent=2)
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        title = str(getattr(args, "command", "items") or "items").replace("-", " ").capitalize()
        rows = [title]
        page = value.get("pagination")
        if isinstance(page, dict):
            current = page.get("page", 1)
            next_page = current + 1 if page.get("has_next") else "-"
            prev_page = current - 1 if page.get("has_prev") else "-"
            rows.append(
                f"page {current} | per-page {page.get('per_page', '?')} | total {page.get('total', '?')} "
                f"| next {next_page} | prev {prev_page}"
            )
        if getattr(args, "exclude_defaults", False):
            rows.append("filters: defaults=excluded")
        rows.append("")
        start = (page.get("page", 1) - 1) * page.get("per_page", 0) + 1 if isinstance(page, dict) else 1
        for number, item in enumerate(value["items"], start=start):
            if not isinstance(item, dict):
                continue
            label = item.get("name") or item.get("title") or item.get("status") or "Item"
            rows.append(f"{number}. {label}")
            details = [f"id {item['id']}"] if item.get("id") is not None else []
            if item.get("default") is True:
                details.append("default")
            if item.get("status") and item["status"] != label:
                details.append(str(item["status"]))
            if details:
                rows.append(f"   {' | '.join(details)}")
            extra = [
                line
                for line in _item_details(getattr(args, "command", ""), item)
                if not line.startswith(("id:", "name:", "default:", "description:"))
            ]
            rows.extend(f"   {line}" for line in extra)
            if item.get("description"):
                rows.append(f"   {' '.join(str(item['description']).splitlines())}")
            rows.append("")
        if not value["items"]:
            rows.append("No items found.")
        return "\n".join(rows).rstrip()
    if isinstance(value, dict):
        if isinstance(value.get("events"), list):
            return "\n".join(_event_line(event) for event in value["events"])
        lines = _item_details(getattr(args, "command", ""), value)
        lines.extend(_action_details(getattr(args, "command", ""), getattr(args, "action", ""), value))
        lines.extend(_result_details(value))
        text = "\n".join(lines)
        return text or "ok"
    if isinstance(value, list):
        return "\n".join(human(args, item) for item in value)
    return str(value) if value is not None else "Done."


def _item_details(resource: str, item: dict[str, object]) -> list[str]:
    if resource == "notifications":
        return _notification_details(item)
    fields = {
        "tasks": (
            "id",
            "name",
            "url",
            "timer",
            "preset",
            "folder",
            "template",
            "cli",
            "enabled",
            "auto_start",
            "handler_enabled",
        ),
        "task-definitions": ("id", "name", "match_url", "priority", "enabled"),
        "presets": ("id", "description", "folder", "template", "default", "priority"),
        "conditions": ("id", "name", "filter", "cli", "enabled", "priority", "description"),
        "dl-fields": ("id", "name", "field", "kind", "order", "value", "description"),
    }.get(resource, ("id", "name", "status", "description", "enabled", "default", "count", "matched", "handler"))
    lines: list[str] = []
    for key in fields:
        if key not in item or (isinstance(item[key], (dict, list)) and key not in {"match_url"}):
            continue
        val = item[key]
        if val in (None, "", False) and key not in {"enabled", "default", "required", "auto_start", "handler_enabled"}:
            continue
        if key == "match_url":
            val = ", ".join(str(pattern) for pattern in val) if isinstance(val, list) else val
        elif key == "description":
            val = " ".join(str(val).splitlines())
        label = {"cli": "options", "value": "value"}.get(key, key.replace("_", " "))
        lines.append(f"{label}: {val}")
    return lines


def _notification_details(item: dict[str, object]) -> list[str]:
    lines = []
    for key in ("id", "name", "enabled", "on", "presets"):
        value = item.get(key)
        if value not in (None, "", [], False) or key == "enabled":
            lines.append(f"{key}: {', '.join(map(str, value)) if isinstance(value, list) else value}")
    request = item.get("request")
    if isinstance(request, dict):
        for key, value in request.items():
            if value not in (None, ""):
                rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
                lines.append(f"request {key}: {rendered}")
    return lines


def _event_line(event: object) -> str:
    if isinstance(event, str):
        return event
    if not isinstance(event, dict):
        return "event: available"
    parts = [
        f"{key}: {event[key]}"
        for key in ("event", "type", "name", "count", "status")
        if key in event and not isinstance(event[key], (dict, list))
    ]
    return " | ".join(parts) or "event: available"


def _result_details(value: dict[str, object]) -> list[str]:
    result = value.get("result", value.get("results"))
    if isinstance(result, list):
        return [f"results: {len(result)} item(s)"]
    if not isinstance(result, dict):
        return []
    return [
        f"result {key}: {result[key]}"
        for key in ("status", "matched", "handler", "count")
        if key in result and not isinstance(result[key], (dict, list))
    ]


def _action_details(resource: str, action: str, value: dict[str, object]) -> list[str]:
    if resource == "conditions" and action == "test":
        lines = []
        if "status" in value:
            lines.append(f"matched: {'yes' if value['status'] else 'no'}")
        if value.get("condition"):
            lines.append(f"condition: {value['condition']}")
        data = value.get("data")
        if isinstance(data, dict):
            lines.extend(
                f"{key}: {data[key]}" for key in ("title", "extractor", "id") if data.get(key) not in (None, "")
            )
        return lines
    if resource == "tasks" and action == "inspect":
        metadata = value.get("metadata")
        if isinstance(metadata, dict):
            return [
                f"{key}: {metadata[key]}"
                for key in ("matched", "handler", "title", "extractor", "id")
                if metadata.get(key) not in (None, "") and not isinstance(metadata[key], (dict, list))
            ]
    return []
