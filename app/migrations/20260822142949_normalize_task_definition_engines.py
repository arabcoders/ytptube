"""
This module contains a db migration.

Migration Name: normalize_task_definition_engines
Migration Version: 20260822142949
"""

import json
import math
from copy import deepcopy
from urllib.parse import urlsplit

from sqlalchemy import text

DEFAULT_SELENIUM_URL = "http://localhost:4444/wd/hub"


def _valid_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def normalize_definition(definition: object) -> object:
    if not isinstance(definition, dict):
        return definition

    engine = definition.get("engine")
    if isinstance(engine, dict):
        engine_type = engine.get("type")
        if engine_type == "httpx":
            engine["type"] = "http"
            engine["options"] = {}
        elif engine_type == "selenium":
            old_options = engine.get("options")
            old_options = old_options if isinstance(old_options, dict) else {}
            options: dict[str, object] = {
                "protocol": "cdp",
                "url": old_options.get("url") if _valid_url(old_options.get("url")) else DEFAULT_SELENIUM_URL,
            }
            wait_for = old_options.get("wait_for")
            if isinstance(wait_for, dict):
                expression = wait_for.get("expression", wait_for.get("value"))
                wait_type = wait_for.get("type", "css")
                if isinstance(expression, str) and expression and wait_type in {"css", "xpath"}:
                    options["wait_for"] = {"type": wait_type, "expression": expression}
            for key in ("wait_timeout", "page_load_timeout"):
                value = old_options.get(key)
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    and 0 <= value <= 300
                ):
                    options[key] = value
            engine["type"] = "browser"
            engine["options"] = options

    request = definition.get("request")
    if isinstance(request, dict):
        created_body = False
        if "body" not in request:
            if request.get("json_data") is not None:
                request["body"] = {"type": "json", "value": request["json_data"]}
                created_body = True
            elif request.get("data") is not None:
                request["body"] = {"type": "form", "value": request["data"]}
                created_body = True
        request.pop("data", None)
        request.pop("json_data", None)
        if created_body:
            request["method"] = "POST"

    parse = definition.get("parse")
    if isinstance(parse, dict):
        if "link" in parse:
            parse["url"] = parse.pop("link")
        items = parse.get("items")
        direct_keys = [key for key in parse if key != "items" and not key.startswith("_")]
        if items:
            for key in list(parse):
                if key != "items" and not key.startswith("_"):
                    parse.pop(key)
        elif direct_keys:
            parse.pop("items", None)
        if isinstance(items, dict):
            fields = items.get("fields")
            if isinstance(fields, dict) and "link" in fields:
                fields["url"] = fields.pop("link")
            selector = items.get("selector")
            expression = items.get("expression")
            if (
                (not isinstance(selector, str) or not selector.strip())
                and isinstance(expression, str)
                and expression.strip()
            ):
                items["selector"] = expression.strip()
            items.pop("expression", None)
    return definition


async def _normalize(c) -> None:
    result = await c.execute(text("SELECT id, definition FROM task_definitions"))
    for row in result:
        definition = json.loads(row.definition) if isinstance(row.definition, str) else row.definition
        original = deepcopy(definition)
        normalized = normalize_definition(definition)
        if normalized != original:
            await c.execute(
                text("UPDATE task_definitions SET definition = :definition WHERE id = :id"),
                {"definition": json.dumps(normalized), "id": row.id},
            )


async def upgrade(c):
    await _normalize(c)


async def downgrade(c):
    pass
