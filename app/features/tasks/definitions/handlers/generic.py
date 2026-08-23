"""Generic task handler driven by JSON definitions."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import httpx
import jmespath
from parsel import Selector

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskItem, TaskResult
from app.features.tasks.definitions.schemas import (
    BrowserEngineOptions,
    ExtractionRule,
    HttpEngineOptions,
    TaskDefinition,
)
from app.features.tasks.definitions.utils import (
    ARCHIVE_ID_TTL,
    ARCHIVE_LOOKUP_FAILURE_TTL,
    archive_key,
)
from app.features.ytdlp.extractor import ExtractorBatch, fetch_info
from app.features.ytdlp.utils import get_archive_id
from app.library.cache import Cache
from app.library.config import Config
from app.library.httpx_client import Globals, build_request_headers, get_async_client
from app.library.logging import get_logger
from app.library.Utils import validate_url

from ._base_handler import BaseHandler

if TYPE_CHECKING:
    from pathlib import Path

    from parsel.selector import SelectorList

LOG = get_logger()
CACHE: Cache = Cache()


class GenericTaskHandler(BaseHandler):
    """Handler that scrapes arbitrary web pages based on JSON task definitions."""

    _definitions: list[TaskDefinition] = []
    """Cached loaded task definitions."""

    _sources_mtime: dict[Path, float] = {}
    """Modification times of source files to detect changes."""

    @classmethod
    async def refresh_definitions(cls, force: bool = False) -> list[TaskDefinition]:
        """
        Refresh the cached task definitions if source files have changed.

        Args:
            force (bool): If True, force reload even if no changes detected.

        """
        if cls._definitions and not force:
            return cls._definitions

        try:
            from app.features.tasks.definitions.repository import TaskDefinitionsRepository
            from app.features.tasks.definitions.utils import model_to_schema

            repo = TaskDefinitionsRepository.get_instance()
            models = await repo.all()

            cls._definitions = [model_to_schema(model) for model in models]
            return cls._definitions
        except Exception as exc:
            LOG.exception(
                "Failed to load generic task definitions.",
                extra={"error": str(exc), "exception_type": type(exc).__name__},
            )
            return []

    @classmethod
    async def _find_definition(cls, url: str) -> TaskDefinition | None:
        """
        Find a task definition that matches the given URL.

        Args:
            url (str): The URL to match.

        Returns:
            (TaskDefinition|None): A matching TaskDefinition if found, None otherwise.

        """
        await cls.refresh_definitions()

        for definition in cls._definitions:
            if not definition.enabled:
                continue

            try:
                if cls.matches_url(definition, url):
                    return definition
            except Exception as exc:
                LOG.exception(
                    "Failed to match a generic task definition.",
                    extra={
                        "definition": definition.name,
                        "url": url,
                        "error": str(exc),
                        "exception_type": type(exc).__name__,
                    },
                )

        return None

    @staticmethod
    def matches_url(definition: TaskDefinition, url: str) -> bool:
        """Return whether a URL matches a definition's URL patterns."""
        for matcher in definition.match_url:
            pattern = (
                matcher[1:-1]
                if matcher.startswith("/") and matcher.endswith("/") and len(matcher) > 2
                else fnmatch.translate(matcher)
            )
            if re.match(pattern, url):
                return True
        return False

    @staticmethod
    async def can_handle(task: HandleTask) -> bool:
        """
        Determine if this handler can process the given task.

        Args:
            task (Task): The task to check.

        Returns:
            (bool): True if the handler can process the task, False otherwise.

        """
        definition: TaskDefinition | None = await GenericTaskHandler._find_definition(task.url)
        if definition:
            LOG.debug(
                "Task '%s' matched a generic task definition.",
                task.name,
                extra={"task_name": task.name, "url": task.url, "definition": definition.name},
            )
            return True

        return False

    @staticmethod
    async def extract(task: HandleTask, config: Config | None = None) -> TaskResult | TaskFailure:
        _ = config
        definition: TaskDefinition | None = await GenericTaskHandler._find_definition(task.url)
        if not definition:
            return TaskFailure(message="No generic task definition matched the provided URL.")

        return await GenericTaskHandler.extract_definition(task, definition, config=config)

    @classmethod
    async def inspect(
        cls, task: HandleTask, config: Config | None = None, *, resolve_ids: bool = True
    ) -> TaskResult | TaskFailure:
        """Extract parsed items without requiring downstream archive IDs."""
        definition = await cls._find_definition(task.url)
        if not definition:
            return TaskFailure(message="No generic task definition matched the provided URL.")

        return await cls.extract_definition(
            task,
            definition,
            config=config,
            inspection=True,
            resolve_ids=resolve_ids,
        )

    @staticmethod
    async def extract_definition(
        task: HandleTask,
        definition: TaskDefinition,
        config: Config | None = None,
        *,
        inspection: bool = False,
        resolve_ids: bool = True,
    ) -> TaskResult | TaskFailure:
        _ = config

        ytdlp_opts = GenericTaskHandler._get_params(task, inspection=inspection)
        target_url: str = definition.definition.request.url or task.url

        try:
            validate_url(target_url)
        except ValueError as exc:
            return TaskFailure(message="Invalid target URL.", error=str(exc))

        fetch_started = time.perf_counter()
        try:
            body_text, json_data = await GenericTaskHandler._fetch_content(
                url=target_url, definition=definition, ytdlp_opts=ytdlp_opts
            )
        except httpx.HTTPError as exc:
            return TaskFailure(message="Failed to fetch target URL.", error=str(exc))
        except Exception as exc:
            LOG.exception(
                "Failed to fetch content for task '%s'.",
                task.name,
                extra={
                    "task_name": task.name,
                    "definition": definition.name,
                    "url": target_url,
                    "exception_type": type(exc).__name__,
                },
            )
            return TaskFailure(message="Failed to fetch target URL.", error=str(exc))

        if "json" == definition.definition.response.type and json_data is None:
            return TaskFailure(message="Expected JSON response but decoding failed.")

        if "json" != definition.definition.response.type and not body_text:
            return TaskFailure(message="Received empty response body.")

        raw_items: list[dict[str, str]] = GenericTaskHandler._parse_items(
            definition=definition, html=body_text or "", base_url=target_url, json_data=json_data
        )
        LOG.debug(
            "Task '%s' fetched and parsed %s item(s) from definition '%s' in %.2fs.",
            task.name,
            len(raw_items),
            definition.name,
            time.perf_counter() - fetch_started,
            extra={"task_name": task.name, "definition": definition.name, "item_count": len(raw_items)},
        )

        task_items: list[TaskItem] = []
        archive_fallbacks = 0
        archive_errors: dict[str, int] = {}
        incomplete_archives = 0
        engine = definition.definition.engine
        generic_args = {"http": str(engine.type == "http").lower()}
        if isinstance(engine.options, BrowserEngineOptions):
            generic_args["url"] = engine.options.url

        async with ExtractorBatch(parallel=True) as batch:
            resolutions: dict[str, tuple[str | None, str | None, bool]] = {}
            pending: list[tuple[str, str, str]] = []
            pending_urls: set[str] = set()
            for entry in raw_items:
                if not isinstance(entry, dict) or not (url := entry.get("url")):
                    continue

                archive_id = get_archive_id(url=url).get("archive_id")
                if archive_id:
                    resolutions.setdefault(url, (archive_id, None, False))
                    continue

                cache_key = archive_key(url)
                failure_key = f"{cache_key}:f"
                cache_hit = CACHE.has(cache_key)
                cached = CACHE.get(cache_key) if cache_hit else None
                if isinstance(cached, str) and cached:
                    resolutions.setdefault(url, (cached, None, False))
                elif (inspection and not resolve_ids) or (not inspection and CACHE.has(failure_key)):
                    resolutions.setdefault(url, (None, None, False))
                else:
                    if cache_hit:
                        CACHE.delete(cache_key)
                    resolutions.setdefault(url, (None, None, False))
                    if url not in pending_urls:
                        pending.append((url, cache_key, failure_key))
                        pending_urls.add(url)
                        archive_fallbacks += 1

            LOG.debug(
                "Task '%s' archive ID plan: %s item(s), %s external lookup(s).",
                task.name,
                len(raw_items),
                len(pending),
                extra={
                    "task_name": task.name,
                    "definition": definition.name,
                    "item_count": len(raw_items),
                    "lookup_count": len(pending),
                    "resolve_ids": resolve_ids,
                },
            )

            async def resolve(url: str, cache_key: str, failure_key: str) -> tuple[str | None, str | None, bool]:
                info, logs = await fetch_info(
                    config=ytdlp_opts,
                    url=url,
                    no_archive=True,
                    no_log=True,
                    capture_logs=logging.ERROR,
                    batch=batch,
                    budget_sleep=True,
                    generic_args=generic_args,
                )
                if not info:
                    error = " | ".join(logs) if logs else "No yt-dlp error was reported."
                    if not inspection:
                        CACHE.set(failure_key, 1, ttl=ARCHIVE_LOOKUP_FAILURE_TTL, persist=False)
                    return None, error, False
                if not info.get("id") or not info.get("extractor_key"):
                    if not inspection:
                        CACHE.set(failure_key, 1, ttl=ARCHIVE_LOOKUP_FAILURE_TTL, persist=False)
                    return None, None, True

                archive_id = f"{str(info['extractor_key']).lower()} {info['id']}"
                CACHE.set(cache_key, archive_id, ttl=ARCHIVE_ID_TTL, persist=True)
                CACHE.delete(failure_key)
                return archive_id, None, False

            lookups = [asyncio.create_task(resolve(url, key, failure_key)) for url, key, failure_key in pending]
            try:
                results = await asyncio.gather(*lookups)
            except BaseException:
                for lookup in lookups:
                    lookup.cancel()
                await asyncio.gather(*lookups, return_exceptions=True)
                raise
            resolutions.update(dict(zip((url for url, _, _ in pending), results, strict=True)))

            for entry in raw_items:
                if not isinstance(entry, dict) or not (url := entry.get("url")):
                    continue

                archive_id, error, incomplete = resolutions[url]
                if error:
                    archive_errors[error] = archive_errors.get(error, 0) + 1
                    if not inspection:
                        continue
                if incomplete:
                    incomplete_archives += 1
                    if not inspection:
                        continue
                if archive_id is None and not inspection:
                    continue

                metadata: dict[str, str] = {
                    k: v
                    for k, v in entry.items()
                    if k not in {"url", "title", "published", "archive_id", "thumbnail", "description"}
                }

                task_items.append(
                    TaskItem(
                        url=url,
                        title=entry.get("title"),
                        archive_id=archive_id,
                        thumbnail=entry.get("thumbnail"),
                        description=entry.get("description"),
                        metadata={"published": entry.get("published"), **metadata},
                    )
                )

        if archive_fallbacks:
            LOG.warning(
                "Task '%s' required yt-dlp archive ID fallback for %s item(s).",
                task.name,
                archive_fallbacks,
                extra={
                    "definition": definition.name,
                    "task_name": task.name,
                    "item_count": archive_fallbacks,
                },
            )

        action = "Keeping unresolved items for inspection." if inspection else "Skipping unresolved items."
        for error, count in archive_errors.items():
            LOG.error(
                "Task '%s' failed to generate archive IDs for %s item(s). %s yt-dlp: %s",
                task.name,
                count,
                action,
                error,
                extra={
                    "definition": definition.name,
                    "task_name": task.name,
                    "item_count": count,
                    "error": error,
                },
            )

        if incomplete_archives:
            LOG.error(
                "Task '%s' received incomplete archive information for %s item(s). %s",
                task.name,
                incomplete_archives,
                action,
                extra={
                    "definition": definition.name,
                    "task_name": task.name,
                    "item_count": incomplete_archives,
                },
            )

        return TaskResult(
            items=task_items,
            metadata={
                "definition": definition.name,
                "response_format": definition.definition.response.type,
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
            definition (TaskDefinitionRuntimeSchema): The task definition specifying the engine and request details.
            ytdlp_opts (dict[str, Any]): yt-dlp options that may influence fetching

        Returns:
            (str|None): The fetched HTML content if successful, None otherwise.

        """
        if "browser" == definition.definition.engine.type:
            return await GenericTaskHandler._fetch_with_browser(url=url, definition=definition)

        return await GenericTaskHandler._fetch_with_http(url=url, definition=definition, ytdlp_opts=ytdlp_opts)

    @staticmethod
    async def _fetch_with_http(
        url: str,
        definition: TaskDefinition,
        ytdlp_opts: dict[str, Any],
    ) -> tuple[str | None, Any | None]:
        """
        Fetch the content using the shared HTTP transport.

        Args:
            url (str): The URL to fetch.
            definition (TaskDefinitionRuntimeSchema): The task definition specifying the request details.
            ytdlp_opts (dict[str, Any]): yt-dlp options that may influence fetching

        Returns:
            (str|None): The fetched HTML content if successful, None otherwise.

        """
        headers: dict[str, str] = {**definition.definition.request.headers}
        body = definition.definition.request.body
        form_data = body.value if body and body.type == "form" else None
        content = body.value if body and body.type == "raw" else None
        if body and body.type == "json":
            content = json.dumps(body.value, separators=(",", ":"))
            if not any(name.lower() == "content-type" for name in headers):
                headers["Content-Type"] = "application/json"
        options = definition.definition.engine.options
        if not isinstance(options, HttpEngineOptions):
            msg = "HTTP task definitions require HTTP engine options"
            raise TypeError(msg)
        use_curl = True
        request_headers = build_request_headers(
            base_headers=headers,
            user_agent=Globals.get_random_agent(),
            use_curl=use_curl,
        )

        timeout_value: float | Any = definition.definition.request.timeout
        if timeout_value is None:
            timeout_value = ytdlp_opts.get("socket_timeout", 120)

        client = get_async_client(
            proxy=ytdlp_opts.get("proxy"),
            use_curl=use_curl,
            curl_impersonate=options.impersonate,
            curl_default_headers=options.curl_default_headers,
            enable_cf=options.flaresolverr,
        )
        response: httpx.Response = await client.request(
            method=definition.definition.request.method.upper(),
            url=url,
            params=definition.definition.request.params or None,
            data=form_data,
            content=content,
            timeout=timeout_value,
            headers=request_headers,
        )
        response.raise_for_status()

        if "json" == definition.definition.response.type:
            try:
                json_data: dict[str, Any] = response.json()
            except Exception as exc:
                LOG.exception(
                    "Task definition '%s' returned invalid JSON for '%s'.",
                    definition.name,
                    url,
                    extra={
                        "definition": definition.name,
                        "url": url,
                        "error": str(exc),
                        "exception_type": type(exc).__name__,
                    },
                )
                return response.text, None

            return response.text, json_data

        return response.text, None

    @staticmethod
    async def _fetch_with_browser(
        url: str,
        definition: TaskDefinition,
    ) -> tuple[str | None, Any | None]:
        """
        Fetch the content using the configured browser protocol.

        Args:
            url (str): The URL to fetch.
            definition (TaskDefinitionRuntimeSchema): The task definition specifying the engine options.

        Returns:
            (str|None): The fetched HTML content if successful, None otherwise.

        """
        options = definition.definition.engine.options
        if not isinstance(options, BrowserEngineOptions):
            msg = "Browser task definitions require browser engine options"
            raise TypeError(msg)

        from app.yt_dlp_plugins.extractor.generic_browser import CdpDriver

        if options.protocol == "cdp":
            driver = CdpDriver
        else:
            msg = f"Unsupported browser protocol: {options.protocol}"
            raise ValueError(msg)

        request = definition.definition.request
        target_url = str(httpx.URL(url).copy_merge_params(request.params))
        headers = dict(request.headers)
        body: str | None = None
        if request.body and request.body.type == "json":
            body = json.dumps(request.body.value, separators=(",", ":"))
            if not any(name.lower() == "content-type" for name in headers):
                headers["Content-Type"] = "application/json"
        elif request.body and request.body.type == "form":
            body = str(httpx.QueryParams(request.body.value))
            if not any(name.lower() == "content-type" for name in headers):
                headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif request.body and request.body.type == "raw":
            body = request.body.value

        timeout = request.timeout if request.timeout is not None else options.page_load_timeout

        def load_page() -> tuple[str | None, Any | None]:
            session = driver.connect(options.url, int(options.page_load_timeout * 1000))
            try:
                session.goto(
                    target_url,
                    method=request.method,
                    headers=headers,
                    data=body,
                    timeout=int(timeout * 1000),
                )
                if options.wait_for:
                    session.wait_for_selector(options.wait_for.type, options.wait_for.expression, options.wait_timeout)

                if definition.definition.response.type == "json":
                    text = session.response_text()
                    try:
                        return text, json.loads(text or "")
                    except (TypeError, json.JSONDecodeError) as exc:
                        LOG.warning(
                            "Task definition '%s' returned invalid JSON for '%s': %s",
                            definition.name,
                            target_url,
                            exc,
                        )
                        return text, None

                return session.content(), None
            finally:
                session.close()

        return await asyncio.to_thread(load_page)

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
            definition (TaskDefinitionRuntimeSchema): The task definition specifying the parsers.
            html (str): The HTML content to parse.
            base_url (str): The base URL to resolve relative links.
            json_data (Any|None): The JSON data to parse if applicable.

        Returns:
            (list[dict[str, str]]): A list of extracted items as dictionaries.

        """
        if "json" == definition.definition.response.type:
            return GenericTaskHandler._parse_json_items(definition, json_data, base_url)

        selector = Selector(text=html)

        if definition.definition.parse.get("items"):
            return GenericTaskHandler._parse_with_container(
                definition=definition,
                selector=selector,
                html=html,
                base_url=base_url,
            )

        extracted: dict[str, list[str]] = {}

        for _field, rule_data in definition.definition.parse.field_items():
            if not isinstance(rule_data, dict):
                continue
            rule = ExtractionRule.model_validate(rule_data)
            values: list[str] = GenericTaskHandler._execute_rule(field=_field, selector=selector, html=html, rule=rule)
            extracted[_field] = values

        url_values: list[str] = extracted.get("url", [])
        if not url_values:
            LOG.debug("Definition '%s' produced no URL values.", definition.name, extra={"definition": definition.name})
            return []

        total_items: int = len(url_values)
        items: list[dict[str, str]] = []

        for index in range(total_items):
            entry: dict[str, str] = {}
            url_value: str = url_values[index]
            if not url_value:
                continue

            entry["url"] = urljoin(base_url, url_value)

            for _field, values in extracted.items():
                if "url" == _field:
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
            LOG.debug(
                "Definition '%s' expects JSON but no data was parsed.",
                definition.name,
                extra={"definition": definition.name},
            )
            return []

        if definition.definition.parse.get("items"):
            return GenericTaskHandler._parse_json_with_container(definition, json_data, base_url)

        items: list[dict[str, str]] = []
        entry: dict[str, str] = {}

        for _field, rule_data in definition.definition.parse.field_items():
            if not isinstance(rule_data, dict):
                continue
            rule = ExtractionRule.model_validate(rule_data)
            values: list[str] = GenericTaskHandler._execute_json_rule(_field, json_data, rule)
            if values:
                if "url" == _field:
                    entry["url"] = urljoin(base_url, values[0])
                else:
                    entry[_field] = values[0]

        if "url" in entry:
            items.append(entry)

        return items

    @staticmethod
    def _parse_with_container(
        definition: TaskDefinition,
        selector: Selector,
        html: str,
        base_url: str,
    ) -> list[dict[str, str]]:
        container: dict[str, Any] | None = definition.definition.parse.get("items")
        if not container:
            return []

        container_type = container.get("type", "css")
        container_selector = container.get("selector", "")
        if not container_selector:
            LOG.error(
                "Task definition '%s' is missing an item container selector.",
                definition.name,
                extra={"definition": definition.name},
            )
            return []
        container_fields = container.get("fields", {})

        selection: SelectorList[Selector] = (
            selector.css(container_selector) if "css" == container_type else selector.xpath(container_selector)
        )

        items: list[dict[str, str]] = []

        for node in selection:
            node_html: Any | str = node.get() or html
            entry: dict[str, str] = {}

            for _field, rule_data in container_fields.items():
                rule = ExtractionRule.model_validate(rule_data)
                values: list[str] = GenericTaskHandler._execute_rule(
                    field=_field,
                    selector=node,
                    html=node_html,
                    rule=rule,
                )

                value: str | None = values[0] if values else None
                if value is None:
                    continue

                if "url" == _field:
                    entry["url"] = urljoin(base_url, value)
                else:
                    entry[_field] = value

            if "url" not in entry:
                continue

            items.append(entry)

        return items

    @staticmethod
    def _parse_json_with_container(
        definition: TaskDefinition,
        json_data: Any,
        base_url: str,
    ) -> list[dict[str, str]]:
        container: dict[str, Any] | None = definition.definition.parse.get("items")
        if not container:
            return []

        container_type = container.get("type", "css")
        container_selector = container.get("selector", "")
        container_fields = container.get("fields", {})

        if "jsonpath" != container_type:
            LOG.error(
                "JSON response requires container selector type 'jsonpath'. Definition '%s'.",
                definition.name,
                extra={"definition": definition.name, "container_type": container_type},
            )
            return []

        nodes: Any = GenericTaskHandler._json_search(json_data, container_selector)
        if nodes is None:
            return []

        if not isinstance(nodes, list):
            nodes = [nodes]

        items: list[dict[str, str]] = []

        for node in nodes:
            entry: dict[str, str] = {}

            for _field, rule_data in container_fields.items():
                rule = ExtractionRule.model_validate(rule_data)
                values: list[str] = GenericTaskHandler._execute_json_rule(_field, node, rule)
                if not values:
                    continue

                if "url" == _field:
                    entry["url"] = urljoin(base_url, values[0])
                else:
                    entry[_field] = values[0]

            if "url" not in entry:
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
                LOG.exception(
                    "Invalid regex expression '%s'.",
                    rule.expression,
                    extra={
                        "field": field,
                        "expression": rule.expression,
                        "error": str(exc),
                        "exception_type": type(exc).__name__,
                    },
                )
                return values

            for match in pattern.finditer(target):
                raw: str | None = GenericTaskHandler._regex_value(match=match, attribute=rule.attribute)
                processed = GenericTaskHandler._apply_post_filter(raw, rule)
                if processed is not None:
                    values.append(processed)

            return values

        LOG.error(
            "Unsupported extraction type '%s' for JSON data in field '%s'.",
            rule.type,
            field,
            extra={"field": field, "rule_type": rule.type},
        )
        return values

    @staticmethod
    def _json_search(data: Any, expression: str) -> Any:
        try:
            return jmespath.search(expression, data)
        except Exception as exc:
            LOG.exception(
                "JSONPath search failed for expression '%s'.",
                expression,
                extra={"expression": expression, "error": str(exc), "exception_type": type(exc).__name__},
            )
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
            rule (ExtractionRuleSchema): The extraction rule to execute.

        Returns:
            (list[str]): A list of extracted values.

        """
        values: list[str] = []

        if "regex" == rule.type:
            try:
                pattern: re.Pattern[str] = re.compile(rule.expression, re.MULTILINE | re.DOTALL)
            except re.error as exc:
                LOG.exception(
                    "Invalid regex expression '%s'.",
                    rule.expression,
                    extra={
                        "field": field,
                        "expression": rule.expression,
                        "error": str(exc),
                        "exception_type": type(exc).__name__,
                    },
                )
                return values

            for match in pattern.finditer(html):
                raw: str | None = GenericTaskHandler._regex_value(match=match, attribute=rule.attribute)
                processed: str | None = GenericTaskHandler._apply_post_filter(raw, rule)
                if processed is not None:
                    values.append(processed)

            return values

        if "jsonpath" == rule.type:
            LOG.error("Field '%s' uses 'jsonpath' on a non-JSON response.", field, extra={"field": field})
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
                LOG.debug(
                    "Regex group '%s' not found in pattern '%s'.",
                    attribute,
                    match.re.pattern,
                    extra={"attribute": attribute, "pattern": match.re.pattern},
                )
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
                attributes: dict[str, str] | None = sel.attrib
            except AttributeError:
                attributes = None

            if attributes and attr in attributes:
                return attributes.get(attr)

            attr_value: str | None = sel.xpath(f"@{attr}").get()
            if attr_value is not None:
                return attr_value

        if attr is None and "url" == field.lower():
            href = None
            try:
                attributes: dict[str, str] | None = sel.attrib
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
            rule (ExtractionRuleSchema): The extraction rule containing the post-filter.

        Returns:
            (str|None): The filtered value if applicable, None otherwise.

        """
        if value is None:
            return None

        cleaned: str = value.strip()
        if rule.post_filter:
            # Apply post-filter inline (removed helper method)
            try:
                pattern = re.compile(rule.post_filter.filter)
                match = pattern.search(cleaned)
                if not match:
                    return None

                if rule.post_filter.value:
                    try:
                        return match.group(rule.post_filter.value)
                    except (IndexError, KeyError):
                        return None

                if match.groupdict():
                    # Prefer first named group when available
                    for group_value in match.groupdict().values():
                        if group_value is not None:
                            return group_value

                if match.groups():
                    return match.group(1)

                return match.group(0)
            except re.error:
                return None

        return cleaned or None
