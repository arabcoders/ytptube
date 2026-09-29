from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote


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


def _body(args: argparse.Namespace) -> object:
    raw = Path(args.file).read_text(encoding="utf-8") if args.file is not None else args.data
    return json.loads(raw)


def _item_line(item: dict) -> str:
    fields = [f"ID: {item['_id']}"] if item.get("_id") else []
    if item.get("id"):
        fields.append(f"Source ID: {item['id']}")
    for key in ("status", "title", "preset", "folder", "filename", "percent", "speed", "eta", "error", "msg"):
        if item.get(key) is not None and item[key] != "":
            label = "Message" if key == "msg" else key.replace("_", " ").title()
            suffix = "%" if key == "percent" else ""
            fields.append(f"{label}: {item[key]}{suffix}")
    if item.get("url"):
        fields.append(f"URL: {item['url']}")
    return "\n  ".join(fields)


def register(sub: argparse._SubParsersAction, output_fn=output) -> None:
    downloads = sub.add_parser(
        "downloads", help="Manage downloads.", description="Manage queued and completed downloads."
    )
    output_fn(downloads)
    commands = downloads.add_subparsers(dest="downloads_command", required=True)

    listing = commands.add_parser("list", help="List downloads.", description="List queued or completed downloads.")
    output_fn(listing)
    listing.add_argument(
        "--type", choices=("queue", "done"), default="queue", help="Which downloads to list (default: queue)."
    )
    listing.add_argument("--page", type=int, default=1, help="Page number (default: 1).")
    listing.add_argument("--per-page", type=int, default=50, help="Items per page (default: 50).")
    listing.add_argument("--status", help="Filter by status; prefix with ! to exclude a status.")
    listing.add_argument("--source-id", type=int, help="Filter by the source task ID.")
    listing.add_argument(
        "--order", choices=("ASC", "DESC"), default="DESC", help="Oldest or newest first (default: DESC)."
    )

    show = commands.add_parser("show", help="Show one download.", description="Show one queued or completed download.")
    output_fn(show)
    show.add_argument("id", help="Download ID (_id from 'downloads list', not the source ID).")

    add = commands.add_parser(
        "add",
        help="Queue a download.",
        description="Queue a URL or one or more download requests.",
    )
    output_fn(add)
    add.add_argument("source_url", nargs="*", help="URL(s) to download (omit when using --data or --file).")
    add_data = add.add_mutually_exclusive_group()
    add_data.add_argument("--file", help="Path to a JSON file with one or more download requests.")
    add_data.add_argument("--data", help="JSON object or array with one or more download requests.")
    add.add_argument("--preset", help="Download preset name for the URL.")
    add.add_argument("--folder", help="Destination folder for the URL.")
    add.add_argument("--cli", help="yt-dlp options for the URL.")

    batch = commands.add_parser(
        "batch", help="Apply an action to downloads.", description="Apply one action to downloads."
    )
    output_fn(batch)
    batch.add_argument("id", nargs="*", help="Download IDs (_id from 'downloads list').")
    actions = batch.add_mutually_exclusive_group()
    action_help = {
        "cancel": "Cancel downloads.",
        "retry": "Retry downloads.",
        "start": "Start downloads.",
        "pause": "Pause downloads.",
        "force-start": "Start downloads without queue limits.",
        "front": "Move downloads to the front of the queue.",
        "back": "Move downloads to the back of the queue.",
        "delete": "Delete downloads.",
    }
    for name, help_text in action_help.items():
        actions.add_argument(f"--{name}", action="store_true", help=help_text)
    batch.add_argument("--status", help="Retry or delete downloads with this status.")
    batch.add_argument(
        "--type", choices=("queue", "done"), default=argparse.SUPPRESS, help="Which downloads to delete."
    )
    batch.add_argument("--remove-file", action="store_true", help="Also remove downloaded files when deleting.")

    rename = commands.add_parser(
        "rename", help="Rename a download's file.", description="Rename the file associated with a download."
    )
    output_fn(rename)
    rename.add_argument("id", help="Download ID (_id from 'downloads list').")
    rename.add_argument("name", help="New file name.")
    nfo = commands.add_parser(
        "nfo",
        help="Generate an NFO file.",
        description="Fetch source metadata and generate an NFO file for a completed download.",
    )
    output_fn(nfo)
    nfo.add_argument("id", help="Download ID (_id from 'downloads list').")
    nfo.add_argument("--type", choices=("tv", "movie"), default="tv", help="NFO format (default: tv).")
    nfo.add_argument("--overwrite", action="store_true", help="Replace an existing NFO file.")
    live = commands.add_parser(
        "live",
        help="Show queue activity and progress.",
        description="Show current queue activity and download progress.",
    )
    output_fn(live)
    live.add_argument("--limit", type=int, help="Maximum queued items to show (0 for unlimited).")

    update = commands.add_parser(
        "update",
        help="Update a download.",
        description="Update an existing download with the supplied fields.",
    )
    output_fn(update)
    update.add_argument("id", help="Download ID (_id from 'downloads list').")
    update_data = update.add_mutually_exclusive_group(required=True)
    update_data.add_argument("--file", help="Path to a JSON file with fields to update.")
    update_data.add_argument("--data", help="JSON object with fields to update.")


def run(args: argparse.Namespace, request) -> object:
    action = args.downloads_command
    if action == "list":
        params = {"type": args.type, "page": args.page, "per_page": args.per_page, "order": args.order}
        for key in ("status", "source_id"):
            value = getattr(args, key, None)
            if value is not None:
                params[key] = value
        return request("GET", "/api/history/", params=params)
    if action == "show":
        return request("GET", f"/api/history/{quote(args.id, safe='')}")
    if action == "add":
        if args.file is not None or args.data is not None:
            if args.source_url or any(getattr(args, key, None) for key in ("preset", "folder", "cli")):
                message = "source URL and options cannot be combined with --file or --data"
                raise ValueError(message)
            body = _body(args)
        else:
            if not args.source_url:
                message = "source URL or --file/--data is required"
                raise ValueError(message)
            options = {key: value for key in ("preset", "folder", "cli") if (value := getattr(args, key, None))}
            body = [{"url": url, **options} for url in args.source_url]
            if len(body) == 1:
                body = body[0]
        return request("POST", "/api/history/", body=body)
    if action == "live":
        params = {"limit": args.limit} if args.limit is not None else None
        return request("GET", "/api/history/live", params=params)
    if action == "batch":
        selected = [
            name
            for name in ("cancel", "retry", "start", "pause", "force_start", "front", "back", "delete")
            if getattr(args, name)
        ]
        if len(selected) != 1:
            message = "exactly one batch action is required"
            raise ValueError(message)
        operation = selected[0]
        if args.status and operation not in ("retry", "delete"):
            message = "--status is only valid with --retry or --delete"
            raise ValueError(message)
        if args.status and args.id:
            message = "IDs and --status cannot be combined"
            raise ValueError(message)
        if not args.id and not args.status:
            message = "at least one ID or --status is required"
            raise ValueError(message)
        if operation != "delete" and hasattr(args, "type"):
            message = "--type is only valid with --delete"
            raise ValueError(message)
        if operation != "delete" and args.remove_file:
            message = "--remove-file is only valid with --delete"
            raise ValueError(message)
        if operation == "delete":
            body = {"type": getattr(args, "type", "done"), "remove_file": args.remove_file}
            body["status" if args.status else "ids"] = args.status or args.id
            return request("DELETE", "/api/history/", body=body)
        if operation in ("front", "back"):
            body = {"ids": args.id, "position": operation}
            return request("POST", "/api/history/position", body=body)
        body = {"status": args.status} if args.status else {"ids": args.id}
        path = "force-start" if operation == "force_start" else operation
        return request("POST", f"/api/history/{path}", body=body)
    if action == "update":
        body = _body(args)
        return request("POST", f"/api/history/{quote(args.id, safe='')}", body=body)
    if action == "rename":
        return request("POST", f"/api/history/{quote(args.id, safe='')}/rename", body={"new_name": args.name})
    if action == "nfo":
        return request(
            "POST", f"/api/history/{quote(args.id, safe='')}/nfo", body={"type": args.type, "overwrite": args.overwrite}
        )
    message = f"unsupported downloads operation: {action}"
    raise ValueError(message)


def human(args: argparse.Namespace, value: object) -> str:
    if getattr(args, "json_output", False):
        return json.dumps(value, indent=2)
    if isinstance(value, dict):
        if args.downloads_command == "list" and isinstance(value.get("items"), list):
            lines = [_item_line(item) for item in value["items"] if isinstance(item, dict)]
            pagination = value.get("pagination", value)
            page = pagination.get("page")
            per_page = pagination.get("per_page")
            total = pagination.get("total")
            page_line = (
                f"Page {page} (showing {per_page} per page, {total} total)"
                if page is not None and per_page is not None and total is not None
                else None
            )
            if pagination.get("has_prev"):
                page_line = f"{page_line}; previous page available"
            if pagination.get("has_next"):
                page_line = f"{page_line}; next page available"
            if not lines:
                return f"No downloads found.\n{page_line}" if page_line else "No downloads found."
            return "\n".join(["Downloads:"] + ([page_line] if page_line else []) + lines)
        if args.downloads_command == "live":
            fields = (
                "status",
                "active",
                "pending",
                "queue_count",
                "queue_loaded",
                "queue_limit",
                "history_count",
                "total",
            )
            lines = [f"{key.replace('_', ' ').title()}: {value[key]}" for key in fields if key in value]
            items = value.get("items", value.get("queue", []))
            if isinstance(items, list):
                lines.extend(_item_line(item) for item in items if isinstance(item, dict))
            return "\n".join(lines) or "No active downloads."
        if args.downloads_command == "batch":
            lines = []
            for key, status in value.items():
                if key == "failed":
                    continue
                if isinstance(status, dict):
                    detail = status.get("status", status.get("message", "completed"))
                elif isinstance(status, list):
                    detail = f"{len(status)} item(s)"
                else:
                    detail = status
                lines.append(f"{key}: {detail}")
            failed = value.get("failed")
            if failed:
                lines.append(f"failed: {failed if isinstance(failed, int) else len(failed)}")
            return "\n".join(lines) or "Action completed"
        fields = (
            "_id",
            "id",
            "status",
            "title",
            "error",
            "url",
            "filename",
            "percent",
            "speed",
            "eta",
            "message",
            "msg",
            "datetime",
            "created_at",
            "path",
            "count",
            "deleted",
        )
        lines = []
        for key in fields:
            if key in value and value[key] is not None:
                shown = value[key]
                if not isinstance(shown, (str, int, float, bool)):
                    continue
                label = {"_id": "ID", "id": "Source ID"}.get(key, key.replace("_", " ").title())
                lines.append(f"{label}: {shown}")
        return "\n".join(lines) or "Request completed."
    if isinstance(value, list):
        return "\n".join(_item_line(item) for item in value if isinstance(item, dict)) or "No downloads found."
    return "Request completed." if value is None else str(value)
