"""Generic task handler driven by JSON definitions."""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import json
import logging
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import jmespath
from parsel import Selector

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskItem, TaskResult
from app.features.tasks.definitions.schemas import (
    ExtractionRule,
    TaskDefinition,
)
from app.library.cache import Cache
from app.library.config import Config
from app.library.downloads.extractor import fetch_info
from app.library.httpx_client import Globals, build_request_headers, get_async_client, resolve_curl_transport
from app.library.Utils import get_archive_id

from ._base_handler import BaseHandler

if TYPE_CHECKING:
    from pathlib import Path

    import httpx
    from parsel.selector import SelectorList

LOG: logging.Logger = logging.getLogger(__name__)
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
            models = await repo.list()

            cls._definitions = [model_to_schema(model) for model in models]
            return cls._definitions
        except Exception as exc:
            LOG.error(f"Failed to load task definitions from database: {exc}")
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
                for matcher in definition.match_url:
                    pattern_str: str | None = None

                    if matcher.startswith("/") and matcher.endswith("/") and len(matcher) > 2:
                        pattern_str = matcher[1:-1]
                    else:
                        pattern_str = fnmatch.translate(matcher)

                    if pattern_str and re.match(pattern_str, url):
                        return definition
            except Exception as exc:
                LOG.error(f"Error while matching definition '{definition.name}': {exc}")

        return None

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
            LOG.debug(f"'{task.name}': Matched generic task definition '{definition.name}'.")
            return True

        return False

    @staticmethod
    async def extract(task: HandleTask, config: Config | None = None) -> TaskResult | TaskFailure:  # noqa: ARG004
        definition: TaskDefinition | None = await GenericTaskHandler._find_definition(task.url)
        if not definition:
            return TaskFailure(message="No generic task definition matched the provided URL.")

        ytdlp_opts: dict[str, Any] = task.get_ytdlp_opts().get_all()
        target_url: str = definition.definition.request.url or task.url

        LOG.debug(f"{task.name!r}: Fetching '{target_url}' using engine '{definition.definition.engine.type}'.")

        try:
            body_text, json_data = await GenericTaskHandler._fetch_content(
                url=target_url, definition=definition, ytdlp_opts=ytdlp_opts
            )
        except Exception as exc:
            LOG.exception(exc)
            return TaskFailure(message="Failed to fetch target URL.", error=str(exc))

        if "json" == definition.definition.response.type and json_data is None:
            return TaskFailure(message="Expected JSON response but decoding failed.")

        if "json" != definition.definition.response.type and not body_text:
            return TaskFailure(message="Received empty response body.")

        raw_items: list[dict[str, str]] = GenericTaskHandler._parse_items(
            definition=definition, html=body_text or "", base_url=target_url, json_data=json_data
        )

        task_items: list[TaskItem] = []

        def _generic_id(url):
            import os
            from urllib import parse

            return parse.unquote(os.path.splitext(url.rstrip("/").split("/")[-1])[0])

        for entry in raw_items:
            if not isinstance(entry, dict):
                continue

            if not (url := entry.get("link") or entry.get("url")):
                continue

            id_dict: dict[str, str | None] = get_archive_id(url=url)
            archive_id: str | None = id_dict.get("archive_id")
            if not archive_id:
                cache_key: str = hashlib.sha256(f"{task.name}-{url}".encode()).hexdigest()
                if CACHE.has(cache_key):
                    archive_id = CACHE.get(cache_key)
                    if not archive_id:
                        continue
                else:
                    LOG.warning(
                        f"[{definition.name}]: '{task.name}': Unable to generate static archive id for '{url}' in feed. Doing real request to fetch yt-dlp archive id."
                    )

                    (info, _) = await fetch_info(
                        config=task.get_ytdlp_opts().get_all(),
                        url=url,
                        no_archive=True,
                        no_log=True,
                    )

                    if not info:
                        LOG.error(
                            f"[{definition.name}]: '{task.name}': Failed to extract info for URL '{url}' to generate archive ID. Skipping."
                        )
                        CACHE.set(cache_key, None)
                        continue

                    if not info.get("id") or not info.get("extractor_key"):
                        LOG.error(
                            f"[{definition.name}]: '{task.name}': Incomplete info extracted for URL '{url}' to generate archive ID. Skipping."
                        )
                        CACHE.set(cache_key, None)
                        continue

                    archive_id = f"{str(info.get('extractor_key', '')).lower()} {info.get('id')}"
                    CACHE.set(cache_key, archive_id)

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
        if "selenium" == definition.definition.engine.type:
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
            definition (TaskDefinitionRuntimeSchema): The task definition specifying the request details.
            ytdlp_opts (dict[str, Any]): yt-dlp options that may influence fetching

        Returns:
            (str|None): The fetched HTML content if successful, None otherwise.

        """
        headers: dict[str, str] = {**definition.definition.request.headers}
        use_curl = resolve_curl_transport()
        request_headers = build_request_headers(
            base_headers=headers,
            user_agent=Globals.get_random_agent(),
            use_curl=use_curl,
        )

        timeout_value: float | Any = definition.definition.request.timeout or ytdlp_opts.get("socket_timeout", 120)

        client = get_async_client(proxy=ytdlp_opts.get("proxy"), use_curl=use_curl)
        response: httpx.Response = await client.request(
            method=definition.definition.request.method.upper(),
            url=url,
            params=definition.definition.request.params or None,
            data=definition.definition.request.data,
            json=definition.definition.request.json_data,
            timeout=timeout_value,
            headers=request_headers,
        )
        response.raise_for_status()

        if "json" == definition.definition.response.type:
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
            definition (TaskDefinitionRuntimeSchema): The task definition specifying the engine options.

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
            return (None, None)

        options_map: dict[str, Any] = definition.definition.engine.options
        command_executor_value = options_map.get("url")
        command_executor: str = (
            str(command_executor_value)
            if isinstance(command_executor_value, str) and command_executor_value
            else "http://localhost:4444/wd/hub"
        )
        browser: str = str(options_map.get("browser", "chrome")).lower()

        if "chrome" != browser:
            LOG.error(f"Unsupported selenium browser '{browser}'. Only 'chrome' is supported.")
            return (None, None)

        arguments: list[str] | str = options_map.get("arguments", ["--headless", "--disable-gpu"])
        if isinstance(arguments, str):
            arguments = [arguments]

        wait_for: Mapping | None = (
            options_map.get("wait_for") if isinstance(options_map.get("wait_for"), Mapping) else None
        )
        wait_timeout = float(options_map.get("wait_timeout") or 15)
        page_load_timeout = float(options_map.get("page_load_timeout") or 60)

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
        container: dict[str, Any] | None = definition.definition.parse.get("items")
        if not container:
            return []

        container_type = container.get("type", "css")
        container_selector = container.get("selector") or container.get("expression") or ""
        if not container_selector:
            LOG.error(f"Container missing selector/expression. Definition '{definition.name}'.")
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
        container: dict[str, Any] | None = definition.definition.parse.get("items")
        if not container:
            return []

        container_type = container.get("type", "css")
        container_selector = container.get("selector") or container.get("expression", "")
        container_fields = container.get("fields", {})

        if "jsonpath" != container_type:
            LOG.error(f"JSON response requires container selector type 'jsonpath'. Definition '{definition.name}'.")
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
            rule (ExtractionRuleSchema): The extraction rule to execute.

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
                attributes: dict[str, str] | None = sel.attrib
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
