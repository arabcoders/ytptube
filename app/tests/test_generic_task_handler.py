import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.library.task_handlers.generic import (
    ContainerDefinition,
    EngineConfig,
    ExtractionRule,
    GenericTaskHandler,
    RequestConfig,
    ResponseConfig,
    TaskDefinition,
    load_task_definitions,
)
from app.library.Tasks import Task, TaskFailure, TaskResult


@pytest.fixture(autouse=True)
def reset_generic_handler(monkeypatch):
    monkeypatch.setattr(GenericTaskHandler, "_definitions", [])
    monkeypatch.setattr(GenericTaskHandler, "_sources_mtime", {})


def test_load_task_definitions_parses_valid_file(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    definition_content = {
        "name": "example",
        "match": ["https://example.com/articles/*"],
        "parse": {
            "link": {"type": "css", "expression": ".article a.link::attr(href)"},
            "title": {"type": "css", "expression": ".article .title", "attribute": "text"},
        },
    }

    (tasks_dir / "01-example.json").write_text(json.dumps(definition_content), encoding="utf-8")

    config = SimpleNamespace(config_path=str(tmp_path))
    definitions = load_task_definitions(config=config)

    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.name == "example"
    assert definition.matchers[0].matches("https://example.com/articles/123")
    assert definition.parsers["link"].expression == ".article a.link::attr(href)"


def test_load_task_definitions_handles_container(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    definition_content = {
        "name": "container",
        "match": ["https://example.com/cards"],
        "parse": {
            "items": {
                "selector": ".cards .card",
                "fields": {
                    "link": {"type": "css", "expression": ".card-header a", "attribute": "href"},
                    "title": {"type": "css", "expression": ".card-header a", "attribute": "text"},
                },
            }
        },
    }

    (tasks_dir / "02-container.json").write_text(json.dumps(definition_content), encoding="utf-8")

    config = SimpleNamespace(config_path=str(tmp_path))
    definitions = load_task_definitions(config=config)

    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.container is not None
    assert definition.container.selector == ".cards .card"
    assert "link" in definition.container.fields
    assert definition.parsers == {}


def test_load_task_definitions_handles_json(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    definition_content = {
        "name": "json-def",
        "match": ["https://example.com/api"],
        "response": {"type": "json"},
        "parse": {
            "items": {
                "type": "jsonpath",
                "selector": "items",
                "fields": {
                    "link": {"type": "jsonpath", "expression": "url"},
                    "title": {"type": "jsonpath", "expression": "title"},
                },
            }
        },
    }

    (tasks_dir / "03-json.json").write_text(json.dumps(definition_content), encoding="utf-8")

    config = SimpleNamespace(config_path=str(tmp_path))
    definitions = load_task_definitions(config=config)

    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.response.format == "json"
    assert definition.container is not None
    assert definition.container.selector_type == "jsonpath"
    assert definition.container.fields["link"].type == "jsonpath"


def test_parse_items_extracts_values():
    definition = TaskDefinition(
        name="example",
        source=Path("example.json"),
        matchers=[],
        engine=EngineConfig(),
        request=RequestConfig(),
        parsers={
            "link": ExtractionRule(type="css", expression=".article a.link::attr(href)", attribute=None),
            "title": ExtractionRule(type="css", expression=".article .title", attribute="text"),
            "id": ExtractionRule(type="css", expression=".article", attribute="data-id"),
        },
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
    assert items[0]["link"] == "https://example.com/article-101"
    assert items[0]["title"] == "First Title"
    assert items[0]["id"] == "101"
    assert items[1]["link"] == "https://example.com/article-102"


def test_parse_items_handles_nested_card_layout():
    definition = TaskDefinition(
        name="nested",
        source=Path("nested.json"),
        matchers=[],
        engine=EngineConfig(),
        request=RequestConfig(),
        parsers={},
        container=ContainerDefinition(
            selector_type="css",
            selector=".columns .card",
            fields={
                "link": ExtractionRule(
                    type="css",
                    expression=".card-header a[href]",
                    attribute="href",
                ),
                "title": ExtractionRule(
                    type="css",
                    expression=".card-header a[href]",
                    attribute="text",
                ),
                "poet": ExtractionRule(
                    type="css",
                    expression="footer .card-footer-item:first-child a",
                    attribute="text",
                ),
                "category": ExtractionRule(
                    type="css",
                    expression="footer .card-footer-item:nth-child(2) a",
                    attribute="text",
                ),
            },
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
    assert items[0]["link"] == "https://example.com/poems/view/111"
    assert items[0]["title"] == "First Poem"
    assert items[0]["poet"] == "Poet Alpha"
    assert items[0]["category"] == "Category One"

    assert items[1]["link"] == "https://example.com/poems/view/222"
    assert items[1]["title"] == "Second Poem"
    assert items[1]["poet"] == "Poet Beta"
    assert "category" not in items[1]


def test_parse_items_handles_json_container():
    definition = TaskDefinition(
        name="json",
        source=Path("json.json"),
        matchers=[],
        engine=EngineConfig(),
        request=RequestConfig(),
        parsers={},
        container=ContainerDefinition(
            selector_type="jsonpath",
            selector="entries",
            fields={
                "link": ExtractionRule(type="jsonpath", expression="url"),
                "title": ExtractionRule(type="jsonpath", expression="title"),
                "id": ExtractionRule(type="jsonpath", expression="id"),
            },
        ),
        response=ResponseConfig(format="json"),
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

    assert len(items) == 2
    assert items[0]["link"] == "https://example.com/video/1"
    assert items[0]["title"] == "First"
    assert items[0]["id"] == "1"

    assert items[1]["link"] == "https://example.com/video/2"
    assert items[1]["title"] == "Second"
    assert items[1]["id"] == "2"


@pytest.mark.asyncio
async def test_generic_task_handler_inspect(monkeypatch):
    definition = TaskDefinition(
        name="json-inspect",
        source=Path("json-inspect.json"),
        matchers=[],
        engine=EngineConfig(),
        request=RequestConfig(),
        parsers={},
        container=ContainerDefinition(
            selector_type="jsonpath",
            selector="items",
            fields={
                "link": ExtractionRule(type="jsonpath", expression="url"),
                "title": ExtractionRule(type="jsonpath", expression="title"),
            },
        ),
        response=ResponseConfig(format="json"),
    )

    monkeypatch.setattr(
        GenericTaskHandler,
        "_find_definition",
        classmethod(lambda cls, url: definition),  # noqa: ARG005
    )

    async def fake_fetch_content(url, definition, ytdlp_opts):  # noqa: ARG001
        return "", {"items": [{"url": "/video/1", "title": "First"}]}

    monkeypatch.setattr(GenericTaskHandler, "_fetch_content", staticmethod(fake_fetch_content))

    task = Task(id="inspect", name="Inspect", url="https://example.com/api")
    result: TaskResult | TaskFailure = await GenericTaskHandler.extract(task)

    assert isinstance(result, TaskResult)
    assert len(result.items) == 1
    item = result.items[0]
    assert item.url == "https://example.com/video/1"
    assert item.title == "First"


def test_parse_items_handles_json_top_level_list():
    definition = TaskDefinition(
        name="json-list",
        source=Path("json-list.json"),
        matchers=[],
        engine=EngineConfig(),
        request=RequestConfig(),
        parsers={},
        container=ContainerDefinition(
            selector_type="jsonpath",
            selector="[]",
            fields={
                "link": ExtractionRule(type="jsonpath", expression="url"),
                "title": ExtractionRule(type="jsonpath", expression="title"),
            },
        ),
        response=ResponseConfig(format="json"),
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

    assert len(items) == 2
    assert items[0]["link"] == "https://example.com/video/1"
    assert items[0]["title"] == "First"
    assert items[1]["link"] == "https://example.com/video/2"
    assert items[1]["title"] == "Second"
