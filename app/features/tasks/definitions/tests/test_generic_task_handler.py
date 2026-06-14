from datetime import datetime
from unittest.mock import patch

import pytest

from app.features.tasks.definitions.handlers.generic import GenericTaskHandler
from app.features.tasks.definitions.results import TaskFailure, TaskResult
from app.features.tasks.definitions.schemas import (
    Definition,
    EngineConfig,
    Parse,
    RequestConfig,
    ResponseConfig,
    TaskDefinition,
)
from app.features.tasks.definitions.results import HandleTask


@pytest.fixture(autouse=True)
def reset_generic_handler(monkeypatch):
    monkeypatch.setattr(GenericTaskHandler, "_definitions", [])
    monkeypatch.setattr(GenericTaskHandler, "_sources_mtime", {})


def test_build_def_payload():
    definition = TaskDefinition(
        id=1,
        name="example",
        priority=0,
        match_url=["https://example.com/articles/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse=Parse.model_validate(
                {
                    "link": {"type": "css", "expression": ".article a.link::attr(href)"},
                    "title": {"type": "css", "expression": ".article .title", "attribute": "text"},
                }
            ),
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(),
        ),
    )

    assert definition.name == "example"
    assert definition.match_url == ["https://example.com/articles/*"]
    assert definition.definition.parse["link"]["expression"] == ".article a.link::attr(href)"


def test_build_def_container():
    definition = TaskDefinition(
        id=2,
        name="container",
        priority=0,
        match_url=["https://example.com/cards"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse=Parse.model_validate(
                {
                    "items": {
                        "selector": ".cards .card",
                        "fields": {
                            "link": {"type": "css", "expression": ".card-header a", "attribute": "href"},
                            "title": {"type": "css", "expression": ".card-header a", "attribute": "text"},
                        },
                    }
                }
            ),
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(),
        ),
    )

    assert definition.definition.parse["items"]["selector"] == ".cards .card"
    assert definition.definition.parse["items"]["fields"]["link"]["attribute"] == "href"


def test_build_def_json():
    definition = TaskDefinition(
        id=3,
        name="json-def",
        priority=0,
        match_url=["https://example.com/api"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse=Parse.model_validate(
                {
                    "items": {
                        "type": "jsonpath",
                        "selector": "items",
                        "fields": {
                            "link": {"type": "jsonpath", "expression": "url"},
                            "title": {"type": "jsonpath", "expression": "title"},
                        },
                    }
                }
            ),
            engine=EngineConfig(),
            request=RequestConfig(),
            response=ResponseConfig(type="json"),
        ),
    )

    assert definition.definition.response.type == "json"
    assert definition.definition.parse["items"]["type"] == "jsonpath"
    assert definition.definition.parse["items"]["fields"]["link"]["type"] == "jsonpath"


def test_parse_items_basic():
    definition = TaskDefinition(
        id=4,
        name="example",
        priority=0,
        match_url=["https://example.com/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse=Parse.model_validate(
                {
                    "link": {"type": "css", "expression": ".article a.link::attr(href)", "attribute": None},
                    "title": {"type": "css", "expression": ".article .title", "attribute": "text"},
                    "id": {"type": "css", "expression": ".article", "attribute": "data-id"},
                }
            ),
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

    assert len(items) == 2
    assert items[0] == {
        "link": "https://example.com/article-101",
        "title": "First Title",
        "id": "101",
    }
    assert items[1]["link"] == "https://example.com/article-102"


def test_parse_items_cards():
    definition = TaskDefinition(
        id=5,
        name="nested",
        priority=0,
        match_url=["https://example.com/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse=Parse.model_validate(
                {
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
                }
            ),
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

    assert len(items) == 2
    assert items[0] == {
        "link": "https://example.com/poems/view/111",
        "title": "First Poem",
        "poet": "Poet Alpha",
        "category": "Category One",
    }
    assert items[1] == {
        "link": "https://example.com/poems/view/222",
        "title": "Second Poem",
        "poet": "Poet Beta",
    }


def test_parse_items_json():
    definition = TaskDefinition(
        id=6,
        name="json",
        priority=0,
        match_url=["https://example.com/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse=Parse.model_validate(
                {
                    "items": {
                        "type": "jsonpath",
                        "selector": "entries",
                        "fields": {
                            "link": {"type": "jsonpath", "expression": "url"},
                            "title": {"type": "jsonpath", "expression": "title"},
                            "id": {"type": "jsonpath", "expression": "id"},
                        },
                    }
                }
            ),
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

    assert items == [
        {"link": "https://example.com/video/1", "title": "First", "id": "1"},
        {"link": "https://example.com/video/2", "title": "Second", "id": "2"},
    ]


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
            parse=Parse.model_validate(
                {
                    "items": {
                        "type": "jsonpath",
                        "selector": "items",
                        "fields": {
                            "link": {"type": "jsonpath", "expression": "url"},
                            "title": {"type": "jsonpath", "expression": "title"},
                        },
                    }
                }
            ),
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
        return ({"id": "test_video_1", "extractor_key": "Example"}, [])

    with patch("app.features.tasks.definitions.handlers.generic.fetch_info", side_effect=fake_fetch_info):
        task = HandleTask(id=1, name="Inspect", url="https://example.com/api")
        result: TaskResult | TaskFailure = await GenericTaskHandler.extract(task)

        assert isinstance(result, TaskResult)
        assert len(result.items) == 1
        item = result.items[0]
        assert item.url == "https://example.com/video/1"
        assert item.title == "First"


def test_parse_items_json_list():
    definition = TaskDefinition(
        id=8,
        name="json-list",
        priority=0,
        match_url=["https://example.com/*"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        definition=Definition(
            parse=Parse.model_validate(
                {
                    "items": {
                        "type": "jsonpath",
                        "selector": "[]",
                        "fields": {
                            "link": {"type": "jsonpath", "expression": "url"},
                            "title": {"type": "jsonpath", "expression": "title"},
                        },
                    }
                }
            ),
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

    assert items == [
        {"link": "https://example.com/video/1", "title": "First"},
        {"link": "https://example.com/video/2", "title": "Second"},
    ]
