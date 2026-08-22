import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.features.tasks.definitions.migration import normalize_definition as normalize_file_definition

migration = importlib.import_module("app.migrations.20260822142949_normalize_task_definition_engines")


@pytest.mark.asyncio
async def test_upgrade_normalizes_engines():
    rows = [
        SimpleNamespace(
            id=1,
            definition=json.dumps({"engine": {"type": "httpx", "options": {"unknown": True}}, "parse": {"x": 1}}),
        ),
        SimpleNamespace(
            id=2,
            definition=json.dumps(
                {
                    "engine": {
                        "type": "selenium",
                        "options": {
                            "url": "http://browser:4444/wd/hub",
                            "wait_for": {"type": "xpath", "value": "//main"},
                            "wait_timeout": 5,
                            "page_load_timeout": 301,
                            "browser": "chrome",
                            "arguments": ["--headless"],
                            "unknown": True,
                        },
                    },
                    "other": True,
                }
            ),
        ),
        SimpleNamespace(id=3, definition={"engine": {"type": "browser", "options": {"url": "http://browser"}}}),
    ]
    connection = AsyncMock()
    connection.execute.side_effect = [rows, None, None]

    await migration.upgrade(connection)

    updates = [call.args[1] for call in connection.execute.call_args_list[1:]]
    assert json.loads(updates[0]["definition"]) == {"engine": {"type": "http", "options": {}}, "parse": {"x": 1}}
    assert json.loads(updates[1]["definition"]) == {
        "engine": {
            "type": "browser",
            "options": {
                "protocol": "cdp",
                "url": "http://browser:4444/wd/hub",
                "wait_for": {"type": "xpath", "expression": "//main"},
                "wait_timeout": 5,
            },
        },
        "other": True,
    }
    assert len(updates) == 2


@pytest.mark.asyncio
async def test_engine_missing_url():
    row = SimpleNamespace(id=1, definition=json.dumps({"engine": {"type": "selenium", "options": {}}}))
    connection = AsyncMock()
    connection.execute.side_effect = [[row], None]

    await migration.upgrade(connection)

    params = connection.execute.call_args_list[1].args[1]
    assert json.loads(params["definition"])["engine"]["options"]["url"] == "http://localhost:4444/wd/hub"


@pytest.mark.asyncio
async def test_engine_downgrade_noop():
    connection = AsyncMock()

    await migration.downgrade(connection)

    connection.execute.assert_not_called()


def test_body_normalization():
    definition = {
        "request": {"method": "GET", "data": {"old": "form"}, "json_data": {"new": "json"}},
    }

    migration.normalize_definition(definition)

    assert definition["request"] == {
        "body": {"type": "json", "value": {"new": "json"}},
        "method": "POST",
    }


def test_body_preserves_existing():
    definition = {"request": {"body": {"type": "raw", "value": "x"}, "data": {"old": "form"}}}

    migration.normalize_definition(definition)

    assert definition["request"] == {"body": {"type": "raw", "value": "x"}}


def test_form_body_normalization():
    definition = {"request": {"method": "GET", "data": {"old": "form"}}}

    migration.normalize_definition(definition)

    assert definition["request"] == {
        "body": {"type": "form", "value": {"old": "form"}},
        "method": "POST",
    }


def test_null_body_ignored():
    definition = {"request": {"method": "GET", "data": None, "json_data": None}}

    migration.normalize_definition(definition)

    assert definition["request"] == {"method": "GET"}


def test_normalizers_match():
    definition = {
        "engine": {
            "type": "selenium",
            "options": {"url": "http://browser:4444/wd/hub", "browser": "chrome"},
        },
        "request": {"json_data": {"page": 1}},
        "parse": {
            "items": {
                "type": "xpath",
                "expression": "//article",
                "fields": {"url": {"type": "css", "expression": "a"}},
            },
            "title": {"type": "css", "expression": ".t"},
        },
    }

    database = json.loads(json.dumps(definition))
    imported = json.loads(json.dumps(definition))

    assert migration.normalize_definition(database) == normalize_file_definition(imported)


def test_items_expression_promoted():
    definition = {
        "parse": {
            "items": {
                "type": "xpath",
                "expression": "//article",
                "fields": {"url": {"type": "css", "expression": "a"}},
            }
        }
    }

    migration.normalize_definition(definition)

    assert definition == {
        "parse": {
            "items": {
                "type": "xpath",
                "selector": "//article",
                "fields": {"url": {"type": "css", "expression": "a"}},
            }
        }
    }


def test_selector_is_preferred():
    definition = {
        "parse": {
            "items": {
                "selector": ".card",
                "expression": ".old",
                "fields": {"url": {"type": "css", "expression": "a"}},
            }
        }
    }

    migration.normalize_definition(definition)

    assert definition["parse"]["items"] == {
        "selector": ".card",
        "fields": {"url": {"type": "css", "expression": "a"}},
    }


def test_sibling_parsers_removed():
    definition = {
        "parse": {
            "items": {"selector": ".card", "fields": {"url": {"type": "css", "expression": "a"}}},
            "link": {"type": "css", "expression": "a"},
            "title": {"type": "css", "expression": ".t"},
        }
    }

    migration.normalize_definition(definition)

    assert definition == {
        "parse": {"items": {"selector": ".card", "fields": {"url": {"type": "css", "expression": "a"}}}}
    }


def test_direct_parsers_normalized():
    definition = {"parse": {"link": {"type": "css", "expression": "a"}, "title": {"type": "css", "expression": ".t"}}}

    migration.normalize_definition(definition)

    assert definition == {
        "parse": {"url": {"type": "css", "expression": "a"}, "title": {"type": "css", "expression": ".t"}}
    }


@pytest.mark.parametrize("items", [None, {}, [], "", 0])
def test_falsey_items_preserve_direct(items: object):
    definition = {
        "parse": {
            "items": items,
            "link": {"type": "css", "expression": "a"},
        }
    }

    migration.normalize_definition(definition)

    assert definition == {"parse": {"url": {"type": "css", "expression": "a"}}}


def test_link_precedes_url():
    definition = {
        "parse": {"link": {"type": "css", "expression": ".old"}, "url": {"type": "css", "expression": ".new"}}
    }

    migration.normalize_definition(definition)

    assert definition["parse"]["url"]["expression"] == ".old"

    items = {
        "parse": {
            "items": {
                "selector": ".card",
                "fields": {"link": {"type": "css", "expression": "a"}, "url": {"type": "css", "expression": ".new"}},
            }
        }
    }
    migration.normalize_definition(items)
    assert items["parse"]["items"]["fields"]["url"]["expression"] == "a"
