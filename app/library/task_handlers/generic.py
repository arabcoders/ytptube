"""Generic task handler driven by JSON definitions."""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import json
import logging
import re
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urljoin

import httpx
import jmespath
from parsel import Selector
from parsel.selector import SelectorList
from yt_dlp.utils.networking import random_user_agent

from app.library.config import Config
from app.library.Tasks import Task, TaskFailure, TaskItem, TaskResult
from app.library.Utils import get_archive_id

from ._base_handler import BaseHandler

if TYPE_CHECKING:
    from parsel.selector import SelectorList

LOG: logging.Logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MatchRule:
    """Represents a single URL matcher compiled to regex."""

    source: str
    """Original source pattern (regex or glob)."""

    regex: re.Pattern[str]
    """Compiled regex pattern."""

    @classmethod
    def from_value(cls, value: str | Mapping[str, Any]) -> MatchRule | None:
        """
        Create a MatchRule from a string or mapping.

        Args:
            value (str|Mapping[str, Any]): A string (treated as glob) or a mapping with 'regex' or 'glob' keys.

        Returns:
            (MatchRule|None): A MatchRule instance if successful, None otherwise.

        """
        if isinstance(value, Mapping):
            pattern: str | None = value.get("regex")
            glob_pattern: str | None = value.get("glob")
            raw: str | None = None

            if isinstance(pattern, str) and pattern:
                raw = pattern
                try:
                    compiled: re.Pattern[str] = re.compile(pattern)
                except re.error as exc:
                    LOG.error(f"Invalid regex pattern '{pattern}': {exc}")
                    return None

                return cls(source=raw, regex=compiled)

            if isinstance(glob_pattern, str) and glob_pattern:
                raw = glob_pattern
                compiled = re.compile(fnmatch.translate(glob_pattern))
                return cls(source=raw, regex=compiled)

            LOG.error("Matcher mapping must include 'regex' or 'glob' key with a string value.")
            return None

        if not isinstance(value, str) or not value:
            LOG.error(f"Matcher value must be a non-empty string, got '{value!r}'.")
            return None

        # Treat plain string as glob pattern for convenience.
        compiled = re.compile(fnmatch.translate(value))
        return cls(source=value, regex=compiled)

    def matches(self, url: str) -> bool:
        """
        Check if the given URL matches this rule.

        Args:
            url (str): The URL to check.

        Returns:
            (bool): True if the URL matches, False otherwise.

        """
        return bool(self.regex.match(url))


@dataclass(slots=True)
class PostFilter:
    """Regex post-filter applied on extracted values."""

    pattern: re.Pattern[str]
    """Compiled regex pattern."""

    value_key: str | None = None
    """Optional group name or index to extract from the match."""

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> PostFilter | None:
        """
        Create a PostFilter from a mapping.

        Args:
            mapping (Mapping[str,Any]): A mapping with 'filter' (regex pattern) and optional 'value' (group name or index) keys.

        Returns:
            (PostFilter|None): A PostFilter instance if successful, None otherwise.

        """
        pattern: str | None = mapping.get("filter")
        if not isinstance(pattern, str) or not pattern:
            LOG.error("post_filter requires a non-empty 'filter' string.")
            return None

        try:
            compiled: re.Pattern[str] = re.compile(pattern)
        except re.error as exc:
            LOG.error(f"Invalid post_filter regex '{pattern}': {exc}")
            return None

        value_key: str | None = mapping.get("value")
        if value_key is not None and not isinstance(value_key, str):
            LOG.error("post_filter 'value' must be a string if provided.")
            return None

        return cls(pattern=compiled, value_key=value_key)

    def apply(self, candidate: str) -> str | None:
        """
        Apply the post-filter to the candidate string.

        Args:
            candidate (str): The string to filter.

        Returns:
            (str|None): The filtered value if matched, None otherwise.

        """
        match: re.Match[str] | None = self.pattern.search(candidate)
        if not match:
            return None

        if self.value_key:
            try:
                return match.group(self.value_key)
            except IndexError:
                LOG.warning(
                    f"post_filter value index '{self.value_key}' not present in pattern {self.pattern.pattern!r}."
                )
            except KeyError:
                LOG.warning(
                    f"post_filter value key '{self.value_key}' not present in pattern {self.pattern.pattern!r}."
                )
            return None

        if match.groupdict():
            # Prefer first named group when available.
            key, value = next(iter(match.groupdict().items()))
            if value is not None:
                LOG.debug(f"post_filter using named group '{key}'.")
                return value

        if match.groups():
            return match.group(1)

        return match.group(0)


@dataclass(slots=True)
class ExtractionRule:
    """Single field extraction description."""

    type: Literal["css", "xpath", "regex"]
    """Type of extraction to perform."""

    expression: str
    """CSS selector, XPath expression or regex pattern."""

    attribute: str | None = None
    """Optional attribute to extract (e.g. 'href', 'src', 'text', etc.)."""

    post_filter: PostFilter | None = None
    """Optional post-filter to apply on extracted values."""


@dataclass(slots=True)
class EngineConfig:
    """Engine selection to fetch the page."""

    type: Literal["httpx", "selenium"] = "httpx"
    """Engine type to use."""

    options: dict[str, Any] = field(default_factory=dict)
    """Engine-specific options."""


@dataclass(slots=True)
class RequestConfig:
    """HTTP request configuration."""

    method: str = "GET"
    """HTTP method to use."""
    headers: dict[str, str] = field(default_factory=dict)
    """HTTP headers to include."""
    params: dict[str, Any] = field(default_factory=dict)
    """Query parameters to include."""

    data: Any | None = None
    """Request body data to include."""
    json: Any | None = None
    """Request body JSON data to include."""
    timeout: float | None = None
    """Request timeout in seconds."""
    url: str | None = None
    """Optional URL to use instead of the task URL."""

    def normalized_method(self) -> str:
        """
        Get the HTTP method in uppercase.

        Returns:
            (str): The HTTP method in uppercase.

        """
        return self.method.upper() if isinstance(self.method, str) else "GET"


@dataclass(slots=True)
class ResponseConfig:
    """Defines how to interpret the response body returned by the fetch engine."""

    format: Literal["html", "json"] = "html"
    """Body format. Defaults to HTML."""


@dataclass(slots=True)
class ContainerDefinition:
    """Defines a repeating element with nested field extraction."""

    selector_type: Literal["css", "xpath", "jsonpath"]
    """Type of selector to use for locating container elements."""

    selector: str
    """Selector expression for locating container elements."""

    fields: dict[str, ExtractionRule]
    """Field extraction rules relative to the container."""


@dataclass(slots=True)
class TaskDefinition:
    """Full task definition as loaded from disk."""

    name: str
    """Human-readable name of the task definition."""
    source: Path
    """Path to the source JSON file."""
    matchers: list[MatchRule]
    """List of URL matchers."""
    engine: EngineConfig
    """Engine configuration."""
    request: RequestConfig
    """Request configuration."""
    parsers: dict[str, ExtractionRule]
    """Field extraction rules."""
    container: ContainerDefinition | None = None
    """Optional container definition for repeating elements."""
    response: ResponseConfig = field(default_factory=ResponseConfig)
    """Response configuration."""

    def matches(self, url: str) -> bool:
        """
        Check if the given URL matches any of the defined matchers.

        Args:
            url (str): The URL to check.

        Returns:
            (bool): True if any matcher matches the URL, False otherwise.

        """
        return any(rule.matches(url) for rule in self.matchers)


def _build_extraction_rule(field: str, raw: Mapping[str, Any], *, source: Path) -> ExtractionRule | None:
    """
    Build an ExtractionRule from a raw mapping.

    Args:
        field (str): The name of the field being defined.
        raw (Mapping[str, Any]): The raw mapping defining the extraction rule.
        source (Path): Path to the source JSON file for logging context.

    Returns:
        (ExtractionRule|None): An ExtractionRule instance if successful, None otherwise.

    """
    type_value: str | None = raw.get("type")
    expression: str | None = raw.get("expression")

    if not isinstance(type_value, str):
        LOG.error(f"[{source.name}] Field '{field}' is missing a valid 'type'.")
        return None

    if type_value not in {"css", "xpath", "regex", "jsonpath"}:
        LOG.error(f"[{source.name}] Field '{field}' has unsupported type '{type_value}'.")
        return None

    if not isinstance(expression, str) or not expression:
        LOG.error(f"[{source.name}] Field '{field}' requires non-empty 'expression'.")
        return None

    attribute: str | None = raw.get("attribute")
    if attribute is not None and not isinstance(attribute, str):
        LOG.error(f"[{source.name}] Field '{field}' attribute must be a string if provided.")
        return None

    post_filter: PostFilter | None = None
    if isinstance(raw.get("post_filter"), Mapping):
        post_filter = PostFilter.from_mapping(raw["post_filter"])

    return ExtractionRule(type=type_value, expression=expression, attribute=attribute, post_filter=post_filter)


def _build_matchers(raw_match: Iterable[Any], *, source: Path) -> list[MatchRule]:
    """
    Build a list of MatchRule instances from raw match definitions.

    Args:
        raw_match (Iterable[Any]): An iterable of raw match definitions (strings or mappings).
        source (Path): Path to the source JSON file for logging context.

    Returns:
        (list[MatchRule]): A list of MatchRule instances.

    """
    matchers: list[MatchRule] = []
    for value in raw_match:
        rule: MatchRule | None = MatchRule.from_value(value)
        if rule:
            matchers.append(rule)

    if not matchers:
        LOG.error(f"[{source.name}] No valid match rules found.")

    return matchers


def _normalize_mapping(value: Any) -> MutableMapping[str, Any]:
    """
    Ensure the value is a mutable mapping.

    Args:
        value (Any): The value to check.

    Returns:
        (MutableMapping[str, Any]): The value if it's a mutable mapping.

    """
    if isinstance(value, MutableMapping):
        return value

    msg = "Expected a mapping for parse/request/engine sections."
    raise ValueError(msg)


def load_task_definitions(config: Config | None = None) -> list[TaskDefinition]:
    """
    Load JSON task definitions from the configured tasks directory.

    Args:
        config (Config|None): Optional Config instance. If None, the singleton instance is used.

    Returns:
        (list[TaskDefinition]): A list of loaded TaskDefinition instances.

    """
    cfg: Config = config or Config.get_instance()
    tasks_dir: Path = Path(cfg.config_path) / "tasks"

    if not tasks_dir.exists():
        return []

    definitions: list[TaskDefinition] = []

    for path in sorted(tasks_dir.glob("*.json")):
        try:
            content: str = path.read_text(encoding="utf-8")
        except Exception as exc:
            LOG.error(f"Failed to read task configuration '{path}': {exc}")
            continue

        try:
            raw = json.loads(content)
        except Exception as exc:
            LOG.error(f"Failed to parse JSON for '{path}': {exc}")
            continue

        if not isinstance(raw, Mapping):
            LOG.error(f"Task definition in '{path}' must be a JSON object.")
            continue

        name: str | None = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            LOG.error(f"Task definition '{path}' missing a valid 'name'.")
            continue

        match_value: list[str] | None = raw.get("match")
        if not isinstance(match_value, Iterable) or isinstance(match_value, (str, bytes)):
            LOG.error(f"[{path.name}] 'match' must be a list of patterns.")
            continue

        matchers: list[MatchRule] = _build_matchers(match_value, source=path)
        if not matchers:
            continue

        engine_raw: Any = raw.get("engine", {})
        try:
            engine_map: MutableMapping[str, Any] = _normalize_mapping(engine_raw)
        except ValueError:
            LOG.error(f"[{path.name}] 'engine' must be a JSON object when provided.")
            continue

        engine_type: str | None = engine_map.get("type", "httpx")
        if engine_type not in ("httpx", "selenium"):
            LOG.error(f"[{path.name}] Unsupported engine type '{engine_type}'.")
            continue

        engine_options: Any = engine_map.get("options") if isinstance(engine_map.get("options"), Mapping) else {}
        engine = EngineConfig(type=engine_type, options=dict(engine_options))

        request_raw: Any = raw.get("request", {})
        try:
            request_map: MutableMapping[str, Any] = _normalize_mapping(request_raw)
        except ValueError:
            LOG.error(f"[{path.name}] 'request' must be a JSON object when provided.")
            continue

        request = RequestConfig(
            method=str(request_map.get("method", "GET")),
            headers=dict(request_map.get("headers", {})) if isinstance(request_map.get("headers"), Mapping) else {},
            params=dict(request_map.get("params", {})) if isinstance(request_map.get("params"), Mapping) else {},
            data=request_map.get("data"),
            json=request_map.get("json"),
            timeout=float(request_map.get("timeout")) if request_map.get("timeout") is not None else None,
            url=str(request_map.get("url")) if isinstance(request_map.get("url"), str) else None,
        )

        response_raw: Any = raw.get("response", {})
        response_config = ResponseConfig()
        if response_raw:
            if not isinstance(response_raw, Mapping):
                LOG.error(f"[{path.name}] 'response' must be an object when provided.")
                continue

            response_type: str = str(response_raw.get("type", "html")).lower()
            if response_type not in ("html", "json"):
                LOG.error(f"[{path.name}] Unsupported response type '{response_type}'.")
                continue

            response_config = ResponseConfig(format=response_type)  # type: ignore[arg-type]

        parse_raw: Mapping | None = raw.get("parse")
        if not isinstance(parse_raw, Mapping):
            LOG.error(f"[{path.name}] 'parse' must be a JSON object mapping fields to instructions.")
            continue

        container_definition: ContainerDefinition | None = None
        parsers: dict[str, ExtractionRule] = {}

        items_block: Mapping | None = parse_raw.get("items")
        if isinstance(items_block, Mapping):
            raw_fields: Mapping | None = items_block.get("fields")
            if not isinstance(raw_fields, Mapping):
                LOG.error(f"[{path.name}] 'items.fields' must be a mapping of field definitions.")
                continue

            container_fields: dict[str, ExtractionRule] = {}
            for _field, rule in raw_fields.items():
                if not isinstance(_field, str):
                    LOG.error(f"[{path.name}] Container field names must be strings, got {_field!r}.")
                    continue

                if not isinstance(rule, Mapping):
                    LOG.error(f"[{path.name}] Container definition for '{_field}' must be an object.")
                    continue

                extraction_rule: ExtractionRule | None = _build_extraction_rule(_field, rule, source=path)
                if extraction_rule:
                    container_fields[_field] = extraction_rule

            if "link" not in container_fields:
                LOG.error(f"[{path.name}] Container definition is missing required 'link' field.")
                continue

            selector_value: str | None = items_block.get("selector") or items_block.get("expression")
            if not isinstance(selector_value, str) or not selector_value:
                LOG.error(f"[{path.name}] 'items.selector' must be a non-empty string.")
                continue

            selector_type = str(items_block.get("type", "css"))
            if selector_type not in ("css", "xpath", "jsonpath"):
                LOG.error(f"[{path.name}] Unsupported container selector type '{selector_type}'.")
                continue

            container_definition = ContainerDefinition(
                selector_type=selector_type,
                selector=selector_value,
                fields=container_fields,
            )

        for _field, rule in parse_raw.items():
            if "items" == _field:
                continue

            if not isinstance(_field, str):
                LOG.error(f"[{path.name}] Parser field names must be strings, got {_field!r}.")
                continue

            if not isinstance(rule, Mapping):
                LOG.error(f"[{path.name}] Parser definition for '{_field}' must be an object.")
                continue

            extraction_rule = _build_extraction_rule(_field, rule, source=path)
            if extraction_rule:
                parsers[_field] = extraction_rule

        if container_definition is None and "link" not in parsers:
            LOG.error(f"[{path.name}] Missing required 'link' parser definition.")
            continue

        definition = TaskDefinition(
            name=name.strip(),
            source=path,
            matchers=matchers,
            engine=engine,
            request=request,
            parsers=parsers,
            container=container_definition,
            response=response_config,
        )

        definitions.append(definition)

    return definitions


class GenericTaskHandler(BaseHandler):
    """Handler that scrapes arbitrary web pages based on JSON task definitions."""

    _definitions: list[TaskDefinition] = []
    """Cached loaded task definitions."""

    _sources_mtime: dict[Path, float] = {}
    """Modification times of source files to detect changes."""

    @classmethod
    def _tasks_dir(cls) -> Path:
        """
        Get the path to the tasks directory.

        Returns:
            (Path): Path to the tasks directory.

        """
        return Path(Config.get_instance().config_path) / "tasks"

    @classmethod
    def _refresh_definitions(cls, force: bool = False) -> None:
        """
        Refresh the cached task definitions if source files have changed.

        Args:
            force (bool): If True, force reload even if no changes detected.

        """
        tasks_dir: Path = cls._tasks_dir()

        if not tasks_dir.exists():
            if cls._definitions or cls._sources_mtime:
                cls._definitions = []
                cls._sources_mtime = {}
            return

        current: dict[Path, float] = {}
        for path in tasks_dir.glob("*.json"):
            try:
                current[path] = path.stat().st_mtime
            except OSError:
                LOG.warning(f"Unable to stat task definition '{path}'.")

        if force or not cls._definitions or current != cls._sources_mtime:
            cls._definitions = load_task_definitions()
            cls._sources_mtime = current

    @classmethod
    def _find_definition(cls, url: str) -> TaskDefinition | None:
        """
        Find a task definition that matches the given URL.

        Args:
            url (str): The URL to match.

        Returns:
            (TaskDefinition|None): A matching TaskDefinition if found, None otherwise.

        """
        cls._refresh_definitions()

        for definition in cls._definitions:
            try:
                if definition.matches(url):
                    return definition
            except Exception as exc:
                LOG.error(f"Error while matching definition '{definition.name}': {exc}")

        return None

    @staticmethod
    def can_handle(task: Task) -> bool:
        """
        Determine if this handler can process the given task.

        Args:
            task (Task): The task to check.

        Returns:
            (bool): True if the handler can process the task, False otherwise.

        """
        definition: TaskDefinition | None = GenericTaskHandler._find_definition(task.url)
        if definition:
            LOG.debug(f"'{task.name}': Matched generic task definition '{definition.name}'.")
            return True

        return False

    @staticmethod
    async def extract(task: Task, config: Config | None = None) -> TaskResult | TaskFailure:  # noqa: ARG004
        definition: TaskDefinition | None = GenericTaskHandler._find_definition(task.url)
        if not definition:
            return TaskFailure(message="No generic task definition matched the provided URL.")

        ytdlp_opts: dict[str, Any] = task.get_ytdlp_opts().get_all()
        target_url: str = definition.request.url or task.url

        LOG.debug(f"{task.name!r}: Fetching '{target_url}' using engine '{definition.engine.type}'.")

        try:
            body_text, json_data = await GenericTaskHandler._fetch_content(
                url=target_url, definition=definition, ytdlp_opts=ytdlp_opts
            )
        except Exception as exc:
            LOG.exception(exc)
            return TaskFailure(message="Failed to fetch target URL.", error=str(exc))

        if "json" == definition.response.format and json_data is None:
            return TaskFailure(message="Expected JSON response but decoding failed.")

        if "json" != definition.response.format and not body_text:
            return TaskFailure(message="Received empty response body.")

        raw_items: list[dict[str, str]] = GenericTaskHandler._parse_items(
            definition=definition, html=body_text or "", base_url=target_url, json_data=json_data
        )

        task_items: list[TaskItem] = []

        for entry in raw_items:
            if not isinstance(entry, dict):
                continue

            if not (url := entry.get("link") or entry.get("url")):
                continue

            idDict: str | None = get_archive_id(url=url)
            archive_id: str | None = idDict.get("archive_id")
            if not archive_id:
                LOG.warning(
                    f"[{definition.name}]: '{task.name}': Could not compute archive ID for video '{url}' in feed. generating one."
                )
                archive_id = f"generic {hashlib.sha256(url.encode()).hexdigest()[:16]}"

            metadata: dict[str, str] = {
                k: v for k, v in entry.items() if k not in {"link", "url", "title", "published", "archive_id"}
            }

            task_items.append(
                TaskItem(
                    url=url,
                    title=entry.get("title"),
                    archive_id=archive_id,
                    metadata={"published": entry.get("published"), **metadata},
                )
            )

        return TaskResult(
            items=task_items,
            metadata={
                "definition": definition.name,
                "response_format": definition.response.format,
            },
        )

    @staticmethod
    async def _fetch_content(
        url: str,
        definition: TaskDefinition,
        ytdlp_opts: dict[str, Any],
    ) -> tuple[str | None, Any | None]:
        """
        Fetch the content of the given URL using the specified engine.

        Args:
            url (str): The URL to fetch.
            definition (TaskDefinition): The task definition specifying the engine and request details.
            ytdlp_opts (dict[str, Any]): yt-dlp options that may influence fetching

        Returns:
            (str|None): The fetched HTML content if successful, None otherwise.

        """
        if "selenium" == definition.engine.type:
            return await GenericTaskHandler._fetch_with_selenium(url=url, definition=definition)

        return await GenericTaskHandler._fetch_with_httpx(url=url, definition=definition, ytdlp_opts=ytdlp_opts)

    @staticmethod
    async def _fetch_with_httpx(
        url: str,
        definition: TaskDefinition,
        ytdlp_opts: dict[str, Any],
    ) -> tuple[str | None, Any | None]:
        """
        Fetch the content using httpx.

        Args:
            url (str): The URL to fetch.
            definition (TaskDefinition): The task definition specifying the request details.
            ytdlp_opts (dict[str, Any]): yt-dlp options that may influence fetching

        Returns:
            (str|None): The fetched HTML content if successful, None otherwise.

        """
        headers: dict[str, str] = {**definition.request.headers}
        client_options: dict[str, Any] = {
            "headers": {
                "User-Agent": random_user_agent(),
            }
        }

        try:
            from httpx_curl_cffi import AsyncCurlTransport, CurlOpt

            client_options["transport"] = AsyncCurlTransport(
                impersonate="chrome",
                default_headers=True,
                curl_options={CurlOpt.FRESH_CONNECT: True},
            )
            client_options["headers"].pop("User-Agent", None)
        except Exception:
            pass

        if headers:
            client_options["headers"].update(headers)

        if proxy := ytdlp_opts.get("proxy"):
            client_options["proxy"] = proxy

        timeout_value: float | Any = definition.request.timeout or ytdlp_opts.get("socket_timeout", 120)

        async with httpx.AsyncClient(**client_options) as client:
            response: httpx.Response = await client.request(
                method=definition.request.normalized_method(),
                url=url,
                params=definition.request.params or None,
                data=definition.request.data,
                json=definition.request.json,
                timeout=timeout_value,
            )
            response.raise_for_status()

            if "json" == definition.response.format:
                try:
                    json_data: dict[str, Any] = response.json()
                except Exception as exc:
                    LOG.error(f"Failed to decode JSON response from '{url}': {exc}")
                    return response.text, None

                return response.text, json_data

            return response.text, None

    @staticmethod
    async def _fetch_with_selenium(
        url: str,
        definition: TaskDefinition,
    ) -> tuple[str | None, Any | None]:
        """
        Fetch the content using a Selenium WebDriver.

        Args:
            url (str): The URL to fetch.
            definition (TaskDefinition): The task definition specifying the engine options.

        Returns:
            (str|None): The fetched HTML content if successful, None otherwise.

        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError as exc:
            LOG.error(f"Selenium engine requested but selenium is not installed: {exc!s}.")
            return None

        options_map: dict[str, Any] = definition.engine.options
        command_executor: str | None = options_map.get("url", "http://localhost:4444/wd/hub")
        browser: str = str(options_map.get("browser", "chrome")).lower()

        if "chrome" != browser:
            LOG.error(f"Unsupported selenium browser '{browser}'. Only 'chrome' is supported.")
            return None

        arguments: list[str] | str = options_map.get("arguments", ["--headless", "--disable-gpu"])
        if isinstance(arguments, str):
            arguments = [arguments]

        wait_for: Mapping | None = (
            options_map.get("wait_for") if isinstance(options_map.get("wait_for"), Mapping) else None
        )
        wait_timeout = float(options_map.get("wait_timeout", 15))
        page_load_timeout = float(options_map.get("page_load_timeout", 60))

        def load_page() -> str | None:
            chrome_options = ChromeOptions()
            for arg in arguments:
                chrome_options.add_argument(str(arg))

            driver = webdriver.Remote(command_executor=command_executor, options=chrome_options)
            try:
                driver.set_page_load_timeout(page_load_timeout)
                driver.get(url)

                if wait_for:
                    wait_type: str = str(wait_for.get("type", "css")).lower()
                    expression: str | None = wait_for.get("expression") or wait_for.get("value")
                    if isinstance(expression, str) and expression:
                        locator = None
                        locator = (By.XPATH, expression) if "xpath" == wait_type else (By.CSS_SELECTOR, expression)
                        WebDriverWait(driver, wait_timeout).until(EC.presence_of_element_located(locator))

                return driver.page_source
            finally:
                driver.quit()

        html: str | None = await asyncio.to_thread(load_page)
        return html, None

    @staticmethod
    def _parse_items(
        definition: TaskDefinition,
        html: str,
        base_url: str,
        json_data: Any | None = None,
    ) -> list[dict[str, str]]:
        """
        Parse the HTML content and extract items based on the definition.

        Args:
            definition (TaskDefinition): The task definition specifying the parsers.
            html (str): The HTML content to parse.
            base_url (str): The base URL to resolve relative links.
            json_data (Any|None): The JSON data to parse if applicable.

        Returns:
            (list[dict[str, str]]): A list of extracted items as dictionaries.

        """
        if "json" == definition.response.format:
            return GenericTaskHandler._parse_json_items(definition, json_data, base_url)

        selector = Selector(text=html)

        if definition.container:
            return GenericTaskHandler._parse_with_container(
                definition=definition,
                selector=selector,
                html=html,
                base_url=base_url,
            )

        extracted: dict[str, list[str]] = {}

        for _field, rule in definition.parsers.items():
            values: list[str] = GenericTaskHandler._execute_rule(field=_field, selector=selector, html=html, rule=rule)
            extracted[_field] = values

        link_values: list[str] = extracted.get("link", [])
        if not link_values:
            LOG.debug(f"Definition '{definition.name}' produced no link values.")
            return []

        total_items: int = len(link_values)
        items: list[dict[str, str]] = []

        for index in range(total_items):
            entry: dict[str, str] = {}
            link_value: str = link_values[index]
            if not link_value:
                continue

            entry["link"] = urljoin(base_url, link_value)

            for _field, values in extracted.items():
                if "link" == _field:
                    continue

                value: str | None = values[index] if index < len(values) else None
                if value is None:
                    continue

                entry[_field] = value

            items.append(entry)

        return items

    @staticmethod
    def _parse_json_items(
        definition: TaskDefinition,
        json_data: Any | None,
        base_url: str,
    ) -> list[dict[str, str]]:
        if json_data is None:
            LOG.debug(f"Definition '{definition.name}' expects JSON but no data was parsed.")
            return []

        if definition.container:
            return GenericTaskHandler._parse_json_with_container(definition, json_data, base_url)

        items: list[dict[str, str]] = []
        entry: dict[str, str] = {}

        for _field, rule in definition.parsers.items():
            values: list[str] = GenericTaskHandler._execute_json_rule(_field, json_data, rule)
            if values:
                if "link" == _field:
                    entry["link"] = urljoin(base_url, values[0])
                else:
                    entry[_field] = values[0]

        if "link" in entry:
            items.append(entry)

        return items

    @staticmethod
    def _parse_with_container(
        definition: TaskDefinition,
        selector: Selector,
        html: str,
        base_url: str,
    ) -> list[dict[str, str]]:
        container: ContainerDefinition | None = definition.container
        if not container:
            return []

        if "jsonpath" == container.selector_type:
            LOG.error(
                f"Container selector type 'jsonpath' requires response type 'json'. Definition '{definition.name}'."
            )
            return []

        selection: SelectorList[Selector] = (
            selector.css(container.selector) if "css" == container.selector_type else selector.xpath(container.selector)
        )

        items: list[dict[str, str]] = []

        for node in selection:
            node_html: Any | str = node.get() or html
            entry: dict[str, str] = {}

            for _field, rule in container.fields.items():
                values: list[str] = GenericTaskHandler._execute_rule(
                    field=_field,
                    selector=node,
                    html=node_html,
                    rule=rule,
                )

                value: str | None = values[0] if values else None
                if value is None:
                    continue

                if "link" == _field:
                    entry["link"] = urljoin(base_url, value)
                else:
                    entry[_field] = value

            if "link" not in entry:
                continue

            items.append(entry)

        return items

    @staticmethod
    def _parse_json_with_container(
        definition: TaskDefinition,
        json_data: Any,
        base_url: str,
    ) -> list[dict[str, str]]:
        container: ContainerDefinition | None = definition.container
        if not container:
            return []

        if "jsonpath" != container.selector_type:
            LOG.error(f"JSON response requires container selector type 'jsonpath'. Definition '{definition.name}'.")
            return []

        nodes: Any = GenericTaskHandler._json_search(json_data, container.selector)
        if nodes is None:
            return []

        if not isinstance(nodes, list):
            nodes = [nodes]

        items: list[dict[str, str]] = []

        for node in nodes:
            entry: dict[str, str] = {}

            for _field, rule in container.fields.items():
                values: list[str] = GenericTaskHandler._execute_json_rule(_field, node, rule)
                if not values:
                    continue

                if "link" == _field:
                    entry["link"] = urljoin(base_url, values[0])
                else:
                    entry[_field] = values[0]

            if "link" not in entry:
                continue

            items.append(entry)

        return items

    @staticmethod
    def _execute_json_rule(field: str, data: Any, rule: ExtractionRule) -> list[str]:
        values: list[str] = []

        if "jsonpath" == rule.type:
            result: Any = GenericTaskHandler._json_search(data, rule.expression)
            candidates: list | list[Any] = result if isinstance(result, list) else [result]
            for candidate in candidates:
                if candidate is None:
                    continue

                text: str = GenericTaskHandler._coerce_to_string(candidate)
                processed: str | None = GenericTaskHandler._apply_post_filter(text, rule)
                if processed is not None:
                    values.append(processed)

            return values

        if "regex" == rule.type:
            target: str = GenericTaskHandler._coerce_to_string(data)
            try:
                pattern: re.Pattern[str] = re.compile(rule.expression, re.MULTILINE | re.DOTALL)
            except re.error as exc:
                LOG.error(f"Invalid regex expression '{rule.expression}': {exc}")
                return values

            for match in pattern.finditer(target):
                raw: str | None = GenericTaskHandler._regex_value(match=match, attribute=rule.attribute)
                processed = GenericTaskHandler._apply_post_filter(raw, rule)
                if processed is not None:
                    values.append(processed)

            return values

        LOG.error(f"Unsupported extraction type '{rule.type}' for JSON data in field '{field}'.")
        return values

    @staticmethod
    def _json_search(data: Any, expression: str) -> Any:
        try:
            return jmespath.search(expression, data)
        except Exception as exc:
            LOG.error(f"JSONPath search failed for expression '{expression}': {exc}")
            return None

    @staticmethod
    def _coerce_to_string(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)) or value is None:
            return "" if value is None else str(value)
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    @staticmethod
    def _execute_rule(field: str, selector: Selector, html: str, rule: ExtractionRule) -> list[str]:
        """
        Execute a single extraction rule and return the list of extracted values.

        Args:
            field (str): The name of the field being extracted.
            selector (Selector): The parsel Selector for the HTML content.
            html (str): The raw HTML content.
            rule (ExtractionRule): The extraction rule to execute.

        Returns:
            (list[str]): A list of extracted values.

        """
        values: list[str] = []

        if "regex" == rule.type:
            try:
                pattern: re.Pattern[str] = re.compile(rule.expression, re.MULTILINE | re.DOTALL)
            except re.error as exc:
                LOG.error(f"Invalid regex expression '{rule.expression}': {exc}")
                return values

            for match in pattern.finditer(html):
                raw: str | None = GenericTaskHandler._regex_value(match=match, attribute=rule.attribute)
                processed: str | None = GenericTaskHandler._apply_post_filter(raw, rule)
                if processed is not None:
                    values.append(processed)

            return values

        if "jsonpath" == rule.type:
            LOG.error("Extraction type 'jsonpath' is only valid for JSON responses.")
            return values

        selection: SelectorList[Selector] = (
            selector.css(rule.expression) if "css" == rule.type else selector.xpath(rule.expression)
        )

        for sel in selection:
            raw = GenericTaskHandler._selector_value(field, sel, rule.attribute)
            processed = GenericTaskHandler._apply_post_filter(raw, rule)
            if processed is not None:
                values.append(processed)

        return values

    @staticmethod
    def _regex_value(match: re.Match[str], attribute: str | None) -> str | None:
        """
        Extract a value from a regex match based on the attribute.

        Args:
            match (re.Match[str]): The regex match object.
            attribute (str|None): Optional group name or index to extract.

        Returns:
            (str|None): The extracted value if found, None otherwise.

        """
        if attribute:
            try:
                return match.group(attribute)
            except (IndexError, KeyError):
                LOG.debug(f"Regex group '{attribute}' not found in pattern '{match.re.pattern}'.")
                return None

        if match.groupdict():
            return next((value for value in match.groupdict().values() if value), None)

        if match.groups():
            return match.group(1)

        return match.group(0)

    @staticmethod
    def _selector_value(field: str, sel: Selector, attribute: str | None) -> str | None:
        """
        Extract a value from a parsel Selector based on the attribute.

        Args:
            field (str): The name of the field being extracted.
            sel (Selector): The parsel Selector object.
            attribute (str|None): Optional attribute to extract (e.g. 'href', 'src', 'text', etc.).

        Returns:
            (str|None): The extracted value if found, None otherwise.

        """
        attr: str | None = attribute.lower() if isinstance(attribute, str) else None

        if attr in {"text", "inner_text"}:
            return sel.xpath("normalize-space()").get()

        if attr in {"html", "outer_html"}:
            value: Any = sel.get()
            return value if value is not None else None

        if attr and attr not in {"html", "outer_html", "text", "inner_text"}:
            try:
                attributes: dict[str, str] = sel.attrib
            except AttributeError:
                attributes = None

            if attributes and attr in attributes:
                return attributes.get(attr)

            attr_value: str | None = sel.xpath(f"@{attr}").get()
            if attr_value is not None:
                return attr_value

        if attr is None and "link" == field.lower():
            href = None
            try:
                attributes = sel.attrib
            except AttributeError:
                attributes = None

            if attributes and "href" in attributes:
                href: str | None = attributes.get("href")
            if not href:
                href: str | None = sel.xpath("@href").get()
            if href:
                return href

        if attr is None:
            text_value: str | None = sel.xpath("normalize-space()").get()
            if text_value:
                return text_value

        value = sel.get()
        return value if value is not None else None

    @staticmethod
    def _apply_post_filter(value: str | None, rule: ExtractionRule) -> str | None:
        """
        Apply the post-filter to the extracted value if defined.

        Args:
            value (str|None): The extracted value to filter.
            rule (ExtractionRule): The extraction rule containing the post-filter.

        Returns:
            (str|None): The filtered value if applicable, None otherwise.

        """
        if value is None:
            return None

        cleaned: str = value.strip()
        if rule.post_filter:
            return rule.post_filter.apply(cleaned)

        return cleaned or None
