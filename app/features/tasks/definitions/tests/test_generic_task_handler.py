from datetime import datetime
from unittest.mock import patch

import pytest

from app.features.tasks.definitions.handlers.generic import GenericTaskHandler
from app.features.tasks.definitions.results import TaskFailure, TaskResult
from app.features.tasks.definitions.schemas import (
    Definition,
    EngineConfig,
    RequestConfig,
    ResponseConfig,
    TaskDefinition,
)
from app.features.tasks.definitions.results import HandleTask


@pytest.fixture(autouse=True)
def reset_generic_handler(monkeypatch):
    monkeypatch.setattr(GenericTaskHandler, "_definitions", [])
    monkeypatch.setattr(GenericTaskHandler, "_sources_mtime", {})


def test_build_task_definition_parses_valid_payload():
    definition = TaskDefinition(
        id=1,
        name="example",
        priority=0,
        match_url=["https://example.com/articles/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse={
                "link": {"type": "css", "expression": ".article a.link::attr(href)"},
                "title": {"type": "css", "expression": ".article .title", "attribute": "text"},
            },
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(),
        ),
    )

    assert definition is not None, "TaskDefinition should be created"
    assert "example" == definition.name, "Name should match"
    assert "https://example.com/articles/*" in definition.match_url, "Match URL should be in list"
    assert "link" in definition.definition.parse, "Parse should contain link field"
    assert ".article a.link::attr(href)" == definition.definition.parse["link"]["expression"], (
        "Link expression should match"
    )


def test_build_task_definition_handles_container():
    definition = TaskDefinition(
        id=2,
        name="container",
        priority=0,
        match_url=["https://example.com/cards"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse={
                "items": {
                    "selector": ".cards .card",
                    "fields": {
                        "link": {"type": "css", "expression": ".card-header a", "attribute": "href"},
                        "title": {"type": "css", "expression": ".card-header a", "attribute": "text"},
                    },
                }
            },
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(),
        ),
    )

    assert definition is not None, "TaskDefinition should be created"
    assert "items" in definition.definition.parse, "Parse should contain items container"
    assert ".cards .card" == definition.definition.parse["items"]["selector"], "Items selector should match"
    assert "link" in definition.definition.parse["items"]["fields"], "Items fields should contain link"


def test_build_task_definition_handles_json():
    definition = TaskDefinition(
        id=3,
        name="json-def",
        priority=0,
        match_url=["https://example.com/api"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse={
                "items": {
                    "type": "jsonpath",
                    "selector": "items",
                    "fields": {
                        "link": {"type": "jsonpath", "expression": "url"},
                        "title": {"type": "jsonpath", "expression": "title"},
                    },
                }
            },
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(type="json"),
        ),
    )

    assert definition is not None, "TaskDefinition should be created"
    assert "json" == definition.definition.response.type, "Response type should be json"
    assert "items" in definition.definition.parse, "Parse should contain items container"
    assert "jsonpath" == definition.definition.parse["items"]["type"], "Items type should be jsonpath"
    assert "jsonpath" == definition.definition.parse["items"]["fields"]["link"]["type"], (
        "Link field type should be jsonpath"
    )


def test_parse_items_extracts_values():
    definition = TaskDefinition(
        id=4,
        name="example",
        priority=0,
        match_url=["https://example.com/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse={
                "link": {"type": "css", "expression": ".article a.link::attr(href)", "attribute": None},
                "title": {"type": "css", "expression": ".article .title", "attribute": "text"},
                "id": {"type": "css", "expression": ".article", "attribute": "data-id"},
            },
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(),
        ),
    )

    html = """
    <div class="article" data-id="101">
      <a class="link" href="/article-101">First</a>
      <span class="title">First Title</span>
    </div>
    <div class="article" data-id="102">
      <a class="link" href="https://example.com/article-102">Second</a>
      <span class="title">Second Title</span>
    </div>
    """

    items = GenericTaskHandler._parse_items(definition, html, "https://example.com/base/")

    assert 2 == len(items), "Should extract 2 items"
    assert "https://example.com/article-101" == items[0]["link"], "First item link should be absolute URL"
    assert "First Title" == items[0]["title"], "First item title should match"
    assert "101" == items[0]["id"], "First item id should match"
    assert "https://example.com/article-102" == items[1]["link"], "Second item link should match"


def test_parse_items_handles_nested_card_layout():
    definition = TaskDefinition(
        id=5,
        name="nested",
        priority=0,
        match_url=["https://example.com/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse={
                "items": {
                    "type": "css",
                    "selector": ".columns .card",
                    "fields": {
                        "link": {
                            "type": "css",
                            "expression": ".card-header a[href]",
                            "attribute": "href",
                        },
                        "title": {
                            "type": "css",
                            "expression": ".card-header a[href]",
                            "attribute": "text",
                        },
                        "poet": {
                            "type": "css",
                            "expression": "footer .card-footer-item:first-child a",
                            "attribute": "text",
                        },
                        "category": {
                            "type": "css",
                            "expression": "footer .card-footer-item:nth-child(2) a",
                            "attribute": "text",
                        },
                    },
                }
            },
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(),
        ),
    )

    html = """
    <div class="columns is-multiline">
      <div class="column is-6">
        <div class="card">
          <div class="card-header">
            <p class="card-header-title is-4 has-text-centered is-block text-truncate">
              <a href="/poems/view/111" title="First Poem">First Poem</a>
            </p>
          </div>
          <footer class="card-footer has-text-centered">
            <p class="card-footer-item text-truncate">
              <span class="text-truncate"> By <a href="/poet/alpha">Poet Alpha</a></span>
            </p>
            <p class="card-footer-item text-truncate">
              <span class="text-truncate"> In <a href="/category/one">Category One</a></span>
            </p>
          </footer>
        </div>
      </div>
      <div class="column is-6">
        <div class="card">
          <div class="card-header">
            <p class="card-header-title is-4 has-text-centered is-block text-truncate">
              <a href="/poems/view/222" title="Second Poem">Second Poem</a>
            </p>
          </div>
          <footer class="card-footer has-text-centered">
            <p class="card-footer-item text-truncate">
              <span class="text-truncate"> By <a href="/poet/beta">Poet Beta</a></span>
            </p>
          </footer>
        </div>
      </div>
    </div>
    """

    items = GenericTaskHandler._parse_items(definition, html, "https://example.com")

    assert 2 == len(items), "Should extract 2 items"
    assert "https://example.com/poems/view/111" == items[0]["link"], "First item link should match"
    assert "First Poem" == items[0]["title"], "First item title should match"
    assert "Poet Alpha" == items[0]["poet"], "First item poet should match"
    assert "Category One" == items[0]["category"], "First item category should match"

    assert "https://example.com/poems/view/222" == items[1]["link"], "Second item link should match"
    assert "Second Poem" == items[1]["title"], "Second item title should match"
    assert "Poet Beta" == items[1]["poet"], "Second item poet should match"
    assert "category" not in items[1], "Second item should not have category"


def test_parse_items_handles_json_container():
    definition = TaskDefinition(
        id=6,
        name="json",
        priority=0,
        match_url=["https://example.com/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse={
                "items": {
                    "type": "jsonpath",
                    "selector": "entries",
                    "fields": {
                        "link": {"type": "jsonpath", "expression": "url"},
                        "title": {"type": "jsonpath", "expression": "title"},
                        "id": {"type": "jsonpath", "expression": "id"},
                    },
                }
            },
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(type="json"),
        ),
    )

    payload = {
        "entries": [
            {"url": "/video/1", "title": "First", "id": 1},
            {"url": "https://example.com/video/2", "title": "Second", "id": 2},
            {"title": "Missing Link", "id": 3},
        ]
    }

    items = GenericTaskHandler._parse_items(
        definition=definition,
        html="",
        base_url="https://example.com",
        json_data=payload,
    )

    assert 2 == len(items), "Should extract 2 items (third missing link)"
    assert "https://example.com/video/1" == items[0]["link"], "First item link should be absolute"
    assert "First" == items[0]["title"], "First item title should match"
    assert "1" == items[0]["id"], "First item id should match"

    assert "https://example.com/video/2" == items[1]["link"], "Second item link should match"
    assert "Second" == items[1]["title"], "Second item title should match"
    assert "2" == items[1]["id"], "Second item id should match"


@pytest.mark.asyncio
async def test_generic_task_handler_inspect(monkeypatch):
    definition = TaskDefinition(
        id=7,
        name="json-inspect",
        priority=0,
        match_url=["https://example.com/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse={
                "items": {
                    "type": "jsonpath",
                    "selector": "items",
                    "fields": {
                        "link": {"type": "jsonpath", "expression": "url"},
                        "title": {"type": "jsonpath", "expression": "title"},
                    },
                }
            },
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(type="json"),
        ),
    )

    async def fake_find_definition(cls, url):  # noqa: ARG001
        return definition

    monkeypatch.setattr(
        GenericTaskHandler,
        "_find_definition",
        classmethod(fake_find_definition),
    )

    async def fake_fetch_content(url, definition, ytdlp_opts):  # noqa: ARG001
        return "", {"items": [{"url": "/video/1", "title": "First"}]}

    monkeypatch.setattr(GenericTaskHandler, "_fetch_content", staticmethod(fake_fetch_content))

    # Mock fetch_info to return valid info with required fields for archive ID generation
    async def fake_fetch_info(config, url, **kwargs):  # noqa: ARG001
        return {"id": "test_video_1", "extractor_key": "Example"}

    with patch("app.features.tasks.definitions.handlers.generic.fetch_info", side_effect=fake_fetch_info):
        task = HandleTask(id=1, name="Inspect", url="https://example.com/api")
        result: TaskResult | TaskFailure = await GenericTaskHandler.extract(task)

        assert isinstance(result, TaskResult), "Result should be TaskResult"
        assert 1 == len(result.items), "Should have 1 item"
        item = result.items[0]
        assert "https://example.com/video/1" == item.url, "Item URL should match"
        assert "First" == item.title, "Item title should match"


def test_parse_items_handles_json_top_level_list():
    definition = TaskDefinition(
        id=8,
        name="json-list",
        priority=0,
        match_url=["https://example.com/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse={
                "items": {
                    "type": "jsonpath",
                    "selector": "[]",
                    "fields": {
                        "link": {"type": "jsonpath", "expression": "url"},
                        "title": {"type": "jsonpath", "expression": "title"},
                    },
                }
            },
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(type="json"),
        ),
    )

    payload = [
        {"url": "/video/1", "title": "First"},
        {"url": "/video/2", "title": "Second"},
    ]

    items = GenericTaskHandler._parse_items(
        definition=definition,
        html="",
        base_url="https://example.com",
        json_data=payload,
    )

    assert 2 == len(items), "Should extract 2 items"
    assert "https://example.com/video/1" == items[0]["link"], "First item link should match"
    assert "First" == items[0]["title"], "First item title should match"
    assert "https://example.com/video/2" == items[1]["link"], "Second item link should match"
    assert "Second" == items[1]["title"], "Second item title should match"
