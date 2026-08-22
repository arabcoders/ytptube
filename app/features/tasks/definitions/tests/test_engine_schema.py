import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from jsonschema import Draft7Validator

from app.features.tasks.definitions.schemas import (
    BrowserEngineOptions,
    Definition,
    HttpEngineOptions,
    RequestConfig,
    TaskDefinition,
)


SCHEMA = json.loads((Path(__file__).parents[5] / "app" / "schema" / "task_definition.json").read_text())


def _definition(engine: dict) -> dict:
    return {"parse": {"url": {"type": "css", "expression": "a"}}, "engine": engine}


def test_http_defaults() -> None:
    definition = Definition.model_validate(_definition({}))

    assert definition.engine.type == "http"
    assert isinstance(definition.engine.options, HttpEngineOptions)
    assert definition.engine.options.flaresolverr is False
    assert definition.engine.options.curl_default_headers is True


def test_browser_url_rejected() -> None:
    with pytest.raises(ValidationError):
        Definition.model_validate(_definition({"type": "browser", "options": {"url": "ws://chrome:9222"}}))


def test_browser_protocol() -> None:
    definition = Definition.model_validate(
        _definition({"type": "browser", "options": {"url": "http://browser:9222/wd/hub"}})
    )

    assert isinstance(definition.engine.options, BrowserEngineOptions)
    assert definition.engine.options.protocol == "cdp"
    with pytest.raises(ValidationError):
        Definition.model_validate(
            _definition({"type": "browser", "options": {"protocol": "bidi", "url": "http://browser:4444"}})
        )


def test_engine_options_rejected() -> None:
    with pytest.raises(ValidationError):
        Definition.model_validate(_definition({"type": "http", "options": {"url": "http://chrome:9222"}}))


def test_request_values() -> None:
    request = RequestConfig.model_validate(
        {
            "headers": {"X-Test": "yes"},
            "params": {"page": 2, "enabled": True},
            "method": "POST",
            "body": {"type": "json", "value": {"filters": ["new"]}},
            "timeout": 0,
        }
    )

    assert request.params == {"page": 2, "enabled": True}
    assert request.body is not None
    assert request.body.type == "json"
    assert request.body.value == {"filters": ["new"]}
    assert request.timeout == 0


def test_form_nested_rejected() -> None:
    with pytest.raises(ValidationError):
        RequestConfig.model_validate({"method": "POST", "body": {"type": "form", "value": {"filter": {"type": "new"}}}})


def test_get_body_rejected() -> None:
    with pytest.raises(ValidationError, match="POST"):
        RequestConfig.model_validate({"body": {"type": "raw", "value": "stale"}})


def test_json_schema_engines() -> None:
    validator = Draft7Validator(SCHEMA)
    base = {
        "name": "x",
        "match_url": ["https://example.com/*"],
        "definition": {"parse": {"url": {"type": "css", "expression": "a"}}},
    }
    assert not list(
        validator.iter_errors(
            base | {"definition": {**base["definition"], "engine": {"type": "http", "options": {"flaresolverr": True}}}}
        )
    )
    assert list(
        validator.iter_errors(
            base
            | {
                "definition": {
                    **base["definition"],
                    "engine": {"type": "http", "options": {"url": "http://chrome:9222"}},
                }
            }
        )
    )
    assert not list(
        validator.iter_errors(
            base
            | {
                "definition": {
                    **base["definition"],
                    "engine": {
                        "type": "browser",
                        "options": {"protocol": "cdp", "url": "http://browser:9222"},
                    },
                }
            }
        )
    )
    assert list(
        validator.iter_errors(
            base
            | {
                "definition": {
                    **base["definition"],
                    "engine": {
                        "type": "browser",
                        "options": {"protocol": "bidi", "url": "http://browser:4444"},
                    },
                }
            }
        )
    )
    assert not list(
        validator.iter_errors(
            base
            | {
                "definition": {
                    **base["definition"],
                    "request": {
                        "method": "POST",
                        "body": {"type": "json", "value": {"query": "new videos"}},
                    },
                }
            }
        )
    )
    assert list(
        validator.iter_errors(
            base
            | {
                "definition": {
                    **base["definition"],
                    "request": {"method": "GET", "body": {"type": "raw", "value": "stale"}},
                }
            }
        )
    )


def test_items_selector() -> None:
    definition = Definition.model_validate(
        {"parse": {"items": {"selector": ".card", "fields": {"url": {"type": "css", "expression": "a"}}}}}
    )

    assert definition.parse.items is not None
    assert definition.parse.items.selector == ".card"


def test_mixed_parse_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot combine"):
        Definition.model_validate(
            {
                "parse": {
                    "items": {"selector": ".card", "fields": {"url": {"type": "css", "expression": "a"}}},
                    "url": {"type": "css", "expression": "a"},
                }
            }
        )


def test_archive_field_rejected() -> None:
    rule = {"type": "css", "expression": "a"}

    with pytest.raises(ValidationError, match="generated internally"):
        Definition.model_validate({"parse": {"url": rule, "archive_id": rule}})
    with pytest.raises(ValidationError, match="generated internally"):
        Definition.model_validate(
            {"parse": {"items": {"selector": ".card", "fields": {"url": rule, "archive_id": rule}}}}
        )


def test_json_schema_parse() -> None:
    validator = Draft7Validator(SCHEMA)
    base = {
        "name": "x",
        "match_url": ["https://example.com/*"],
    }
    rule = {"type": "css", "expression": "a"}
    assert not list(
        validator.iter_errors(
            base | {"definition": {"parse": {"items": {"selector": ".card", "fields": {"url": rule}}}}}
        )
    )
    assert not list(validator.iter_errors(base | {"definition": {"parse": {"items": None, "url": rule}}}))
    assert list(
        validator.iter_errors(
            base
            | {
                "definition": {
                    "parse": {
                        "items": {"selector": ".card", "fields": {"url": rule}},
                        "url": rule,
                    }
                }
            }
        )
    )
    assert not list(
        validator.iter_errors(
            base
            | {
                "definition": {
                    "parse": {
                        "url": rule,
                        "title": rule,
                        "thumbnail": rule,
                        "description": rule,
                        "published": rule,
                        "source_id": rule,
                    }
                }
            }
        )
    )
    assert not list(
        validator.iter_errors(
            base
            | {
                "definition": {
                    "parse": {
                        "items": {
                            "selector": ".card",
                            "fields": {"url": rule, "title": rule, "published": rule, "source_id": rule},
                        }
                    }
                }
            }
        )
    )
    assert list(
        validator.iter_errors(
            base | {"definition": {"parse": {"items": {"selector": ".card", "fields": {"title": rule}}}}}
        )
    )
    assert list(
        validator.iter_errors(
            base
            | {"definition": {"parse": {"items": {"selector": ".card", "fields": {"url": rule, "archive_id": rule}}}}}
        )
    )
    assert list(validator.iter_errors(base | {"definition": {"parse": {"title": rule}}}))
    assert list(validator.iter_errors(base | {"definition": {"parse": {"url": rule, "archive_id": rule}}}))


def test_schema_model_parity() -> None:
    validator = Draft7Validator(SCHEMA)
    documents = [
        {
            "name": "direct",
            "match_url": ["https://example.com/*"],
            "definition": {"parse": {"url": {"type": "css", "expression": "a"}}},
        },
        {
            "id": None,
            "name": "nullable",
            "match_url": ["https://example.com/*"],
            "created_at": None,
            "updated_at": None,
            "definition": {
                "request": {
                    "url": None,
                    "headers": {"X-Test": "yes"},
                    "params": {"page": 2, "enabled": True, "empty": None},
                    "body": None,
                    "timeout": None,
                },
                "parse": {
                    "items": None,
                    "url": {
                        "type": "regex",
                        "expression": "https?://[^\\s]+",
                        "attribute": None,
                        "post_filter": {"filter": "(https?://[^\\s]+)", "value": None},
                    },
                },
            },
        },
        {
            "name": "browser",
            "match_url": ["https://example.com/*"],
            "definition": {
                "engine": {
                    "type": "browser",
                    "options": {"url": "http://browser:9222", "wait_for": None},
                },
                "parse": {"url": {"type": "css", "expression": "a"}},
            },
        },
    ]

    Draft7Validator.check_schema(SCHEMA)
    for document in documents:
        normalized = TaskDefinition.model_validate(document).model_dump(mode="json")
        assert not list(validator.iter_errors(normalized))


def test_schema_examples() -> None:
    validator = Draft7Validator(SCHEMA)

    for example in SCHEMA["examples"]:
        assert not list(validator.iter_errors(example))
        TaskDefinition.model_validate(example)
