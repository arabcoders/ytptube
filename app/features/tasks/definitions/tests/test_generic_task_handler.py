import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

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
from app.library.config import Config


@pytest.fixture(autouse=True)
def reset_generic_handler(monkeypatch):
    monkeypatch.setattr(GenericTaskHandler, "_definitions", [])
    monkeypatch.setattr(GenericTaskHandler, "_sources_mtime", {})


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_request_method(method: str) -> None:
    assert RequestConfig.model_validate({"method": method}).method == method


def test_request_method_rejected():
    with pytest.raises(ValidationError):
        RequestConfig.model_validate({"method": "TRACE"})


@pytest.mark.asyncio
async def test_http_transport_options(monkeypatch):
    definition = TaskDefinition(
        name="http",
        match_url=["https://example.com/*"],
        definition=Definition(
            parse=Parse.model_validate({"url": {"type": "css", "expression": "a"}}),
            engine=EngineConfig.model_validate(
                {
                    "type": "http",
                    "options": {"impersonate": "safari", "curl_default_headers": False, "flaresolverr": True},
                }
            ),
        ),
    )
    response = Mock(text="<html>", json=lambda: {})
    response.raise_for_status = Mock()
    client = Mock(request=AsyncMock(return_value=response))
    get_client = Mock(return_value=client)
    monkeypatch.setattr("app.features.tasks.definitions.handlers.generic.get_async_client", get_client)

    definition.definition.request = RequestConfig(
        method="POST",
        headers={"X-Test": "yes"},
        params={"page": "2"},
        body={"type": "json", "value": {"active": True}},
        timeout=0,
    )

    await GenericTaskHandler._fetch_with_http("https://example.com", definition, {"proxy": "http://proxy"})

    get_client.assert_called_once_with(
        proxy="http://proxy",
        use_curl=True,
        curl_impersonate="safari",
        curl_default_headers=False,
        enable_cf=True,
    )
    request = client.request.await_args.kwargs
    assert request["method"] == "POST"
    assert request["params"] == {"page": "2"}
    assert request["content"] == '{"active":true}'
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["timeout"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "argument", "value"),
    [
        ({"type": "raw", "value": "raw body"}, "content", "raw body"),
        ({"type": "form", "value": {"key": "value"}}, "data", {"key": "value"}),
        ({"type": "json", "value": None}, "content", "null"),
    ],
)
async def test_http_body(
    monkeypatch: pytest.MonkeyPatch,
    body: dict[str, object],
    argument: str,
    value: str | dict[str, str],
) -> None:
    definition = TaskDefinition(
        name="http",
        match_url=["https://example.com/*"],
        definition=Definition(
            parse=Parse.model_validate({"url": {"type": "css", "expression": "a"}}),
            request=RequestConfig(method="POST", body=body),
        ),
    )
    response = Mock(text="<html>")
    response.raise_for_status = Mock()
    client = Mock(request=AsyncMock(return_value=response))
    monkeypatch.setattr(
        "app.features.tasks.definitions.handlers.generic.get_async_client",
        Mock(return_value=client),
    )

    await GenericTaskHandler._fetch_with_http("https://example.com", definition, {})

    request = client.request.await_args.kwargs
    assert request[argument] == value
    assert request["data" if argument == "content" else "content"] is None
    if body["type"] == "json":
        assert request["headers"]["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_browser_thread_cleanup(monkeypatch):
    definition = TaskDefinition(
        name="browser",
        match_url=["https://example.com/*"],
        definition=Definition(
            parse=Parse.model_validate({"url": {"type": "css", "expression": "a"}}),
            engine=EngineConfig.model_validate(
                {"type": "browser", "options": {"url": "http://chrome:9222", "wait_for": {"expression": ".ready"}}}
            ),
        ),
    )
    session = Mock()
    session.content.return_value = "<html>"
    connect_mock = Mock(return_value=session)
    monkeypatch.setattr(
        "app.yt_dlp_plugins.extractor.generic_browser.CdpDriver.connect",
        connect_mock,
    )
    to_thread = AsyncMock(side_effect=lambda function: function())
    monkeypatch.setattr("app.features.tasks.definitions.handlers.generic.asyncio.to_thread", to_thread)

    result = await GenericTaskHandler._fetch_with_browser("https://example.com", definition)

    assert result == ("<html>", None)
    connect_mock.assert_called_once_with("http://chrome:9222", 60000)
    session.goto.assert_called_once_with(
        "https://example.com",
        method="GET",
        headers={},
        data=None,
        timeout=60000,
    )
    session.wait_for_selector.assert_called_once_with("css", ".ready", 15)
    session.close.assert_called_once_with()
    to_thread.assert_awaited_once()


@pytest.mark.asyncio
async def test_browser_request(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = TaskDefinition(
        name="browser",
        match_url=["https://example.com/*"],
        definition=Definition(
            parse=Parse.model_validate({"url": {"type": "jsonpath", "expression": "url"}}),
            engine=EngineConfig.model_validate(
                {"type": "browser", "options": {"url": "http://chrome:9222", "page_load_timeout": 45}}
            ),
            request=RequestConfig(
                method="POST",
                headers={"X-Test": "yes"},
                params={"page": 2},
                body={"type": "json", "value": {"active": True}},
                timeout=3,
            ),
            response=ResponseConfig(type="json"),
        ),
    )
    session = Mock()
    session.response_text.return_value = '{"url":"https://example.com/video"}'
    connect_mock = Mock(return_value=session)
    monkeypatch.setattr(
        "app.yt_dlp_plugins.extractor.generic_browser.CdpDriver.connect",
        connect_mock,
    )
    monkeypatch.setattr(
        "app.features.tasks.definitions.handlers.generic.asyncio.to_thread",
        AsyncMock(side_effect=lambda function: function()),
    )

    result = await GenericTaskHandler._fetch_with_browser("https://example.com/feed?sort=new", definition)

    assert result == (
        '{"url":"https://example.com/video"}',
        {"url": "https://example.com/video"},
    )
    session.goto.assert_called_once_with(
        "https://example.com/feed?sort=new&page=2",
        method="POST",
        headers={"X-Test": "yes", "Content-Type": "application/json"},
        data='{"active":true}',
        timeout=3000,
    )
    session.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_browser_form(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = TaskDefinition(
        name="browser",
        match_url=["https://example.com/*"],
        definition=Definition(
            parse=Parse.model_validate({"url": {"type": "css", "expression": "a"}}),
            engine=EngineConfig.model_validate({"type": "browser", "options": {"url": "http://chrome:9222"}}),
            request=RequestConfig(
                method="POST",
                body={"type": "form", "value": {"query": "new videos", "page": 2}},
            ),
        ),
    )
    session = Mock()
    session.content.return_value = "<html>"
    monkeypatch.setattr(
        "app.yt_dlp_plugins.extractor.generic_browser.CdpDriver.connect",
        Mock(return_value=session),
    )
    monkeypatch.setattr(
        "app.features.tasks.definitions.handlers.generic.asyncio.to_thread",
        AsyncMock(side_effect=lambda function: function()),
    )

    result = await GenericTaskHandler._fetch_with_browser("https://example.com/search", definition)

    assert result == ("<html>", None)
    assert session.goto.call_args.kwargs["data"] == "query=new+videos&page=2"
    assert session.goto.call_args.kwargs["headers"] == {"Content-Type": "application/x-www-form-urlencoded"}


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
                    "url": {"type": "css", "expression": ".article a.link::attr(href)", "attribute": None},
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
        "url": "https://example.com/article-101",
        "title": "First Title",
        "id": "101",
    }
    assert items[1]["url"] == "https://example.com/article-102"


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
                            "url": {
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
        "url": "https://example.com/poems/view/111",
        "title": "First Poem",
        "poet": "Poet Alpha",
        "category": "Category One",
    }
    assert items[1] == {
        "url": "https://example.com/poems/view/222",
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
                            "url": {"type": "jsonpath", "expression": "url"},
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
        {"url": "https://example.com/video/1", "title": "First", "id": "1"},
        {"url": "https://example.com/video/2", "title": "Second", "id": "2"},
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
                            "url": {"type": "jsonpath", "expression": "url"},
                            "title": {"type": "jsonpath", "expression": "title"},
                            "thumbnail": {"type": "jsonpath", "expression": "thumbnail"},
                            "description": {"type": "jsonpath", "expression": "description"},
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
        return "", {
            "items": [
                {
                    "url": "/video/1",
                    "title": "First",
                    "thumbnail": "https://example.com/first.jpg",
                    "description": "First description",
                }
            ]
        }

    monkeypatch.setattr(GenericTaskHandler, "_fetch_content", staticmethod(fake_fetch_content))
    config = Config.get_instance()

    # Mock fetch_info to return valid info with required fields for archive ID generation
    async def fake_fetch_info(config, url, **kwargs):  # noqa: ARG001
        return ({"id": "test_video_1", "extractor_key": "Example"}, [])

    with patch("app.features.tasks.definitions.handlers.generic.fetch_info", side_effect=fake_fetch_info):
        task = HandleTask(id=1, name="Inspect", url="https://example.com/api")
        result: TaskResult | TaskFailure = await GenericTaskHandler.extract(task, config=config)

        assert isinstance(result, TaskResult)
        assert len(result.items) == 1
        item = result.items[0]
        assert item.url == "https://example.com/video/1"
        assert item.title == "First"
        assert item.thumbnail == "https://example.com/first.jpg"
        assert item.description == "First description"


@pytest.mark.asyncio
async def test_direct_extracts_without_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = TaskDefinition(
        name="direct",
        match_url=["https://example.com/*"],
        definition=Definition(
            parse=Parse.model_validate({"url": {"type": "css", "expression": "a", "attribute": "href"}})
        ),
    )

    async def fail_lookup(*_args, **_kwargs):
        raise AssertionError("definition lookup should not run")

    async def fetch_content(*_args, **_kwargs):
        return '<a href="https://example.com/item">Item</a>', None

    monkeypatch.setattr(GenericTaskHandler, "_find_definition", classmethod(fail_lookup))
    monkeypatch.setattr(GenericTaskHandler, "_fetch_content", staticmethod(fetch_content))
    monkeypatch.setattr(
        "app.features.tasks.definitions.handlers.generic.get_archive_id",
        lambda url: {"archive_id": "example item"},
    )

    result = await GenericTaskHandler.extract_definition(
        HandleTask(id=None, name="Inspect", url="https://example.com/feed"), definition
    )

    assert isinstance(result, TaskResult)
    assert result.items[0].archive_id == "example item"


@pytest.mark.asyncio
async def test_inspect_reports_failure(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    definition = TaskDefinition(
        name="inspect",
        match_url=["https://example.com/*"],
        definition=Definition(
            parse=Parse.model_validate({"url": {"type": "css", "expression": "a", "attribute": "href"}})
        ),
    )

    async def find_definition(cls, url):  # noqa: ARG001
        return definition

    async def fetch_content(*_args, **_kwargs):
        return '<a href="/item/1">Item</a>', None

    monkeypatch.setattr(GenericTaskHandler, "_find_definition", classmethod(find_definition))
    monkeypatch.setattr(GenericTaskHandler, "_fetch_content", staticmethod(fetch_content))
    monkeypatch.setattr(
        "app.features.tasks.definitions.handlers.generic.get_archive_id",
        lambda url: {"archive_id": None},
    )
    fetch = AsyncMock(return_value=(None, ["Invalid browser URL."]))
    monkeypatch.setattr("app.features.tasks.definitions.handlers.generic.fetch_info", fetch)

    with caplog.at_level(logging.WARNING, logger="ytptube"):
        result = await GenericTaskHandler.inspect(HandleTask(id=None, name="Inspect", url="https://example.com/feed"))

    assert isinstance(result, TaskResult)
    assert result.items[0].url == "https://example.com/item/1"
    assert result.items[0].archive_id is None
    assert "required yt-dlp archive ID fallback for 1 item(s)" in caplog.text
    assert "Keeping unresolved items for inspection. yt-dlp: Invalid browser URL." in caplog.text
    fetch.assert_awaited_once()
    assert fetch.await_args is not None
    assert fetch.await_args.kwargs["capture_logs"] == logging.ERROR


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
                            "url": {"type": "jsonpath", "expression": "url"},
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
        {"url": "https://example.com/video/1", "title": "First"},
        {"url": "https://example.com/video/2", "title": "Second"},
    ]
