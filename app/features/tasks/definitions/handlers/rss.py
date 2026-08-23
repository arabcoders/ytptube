import logging
import re
from typing import Any
from urllib.parse import urljoin
from xml.etree.ElementTree import Element

import httpx

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskItem, TaskResult
from app.features.tasks.definitions.utils import ARCHIVE_ID_TTL, ARCHIVE_LOOKUP_FAILURE_TTL, archive_id_cache_key
from app.features.ytdlp.extractor import ExtractorBatch, fetch_info
from app.features.ytdlp.utils import get_archive_id
from app.library.cache import Cache
from app.library.config import Config
from app.library.logging import get_logger

from ._base_handler import BaseHandler

LOG = get_logger()
CACHE: Cache = Cache()


class RssGenericHandler(BaseHandler):
    FEED_PATTERN: re.Pattern[str] = re.compile(
        r"\.(rss|atom|xml)(\?.*)?$|handler=rss",
        re.IGNORECASE,
    )

    @staticmethod
    async def can_handle(task: HandleTask) -> bool:
        LOG.debug(
            "Checking if task '%s' uses a parsable RSS feed.",
            task.name,
            extra={"task_name": task.name, "url": task.url},
        )
        return RssGenericHandler.parse(task.url) is not None

    @staticmethod
    async def _get(
        task: HandleTask,
        params: dict,
        parsed: dict[str, str],
    ) -> tuple[str, list[dict[str, str]], int]:
        """
        Fetch the feed and return raw entries.

        Args:
            task (Task): The task containing the feed URL.
            params (dict): The ytdlp options.
            parsed (dict): The parsed URL components (contains 'url' key).

        Returns:
            tuple[str, list[dict[str, str]], int]: The feed URL, list of entry dictionaries, and entry count.

        """
        from defusedxml.ElementTree import fromstring

        feed_url: str = parsed["url"]
        LOG.debug(
            "Fetching RSS/Atom feed for task '%s'.",
            task.name,
            extra={"task_name": task.name, "feed_url": feed_url},
        )

        response = await RssGenericHandler.request(url=feed_url, ytdlp_opts=params)
        response.raise_for_status()

        root: Element = fromstring(response.text)

        # Define namespaces for different feed formats
        ns: dict[str, str] = {
            "atom": "http://www.w3.org/2005/Atom",
            "rss": "http://www.rssboard.org/specification",
            "content": "http://purl.org/rss/1.0/modules/content/",
            "media": "http://search.yahoo.com/mrss/",
            "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
        }

        items: list[dict[str, str]] = []
        real_count = 0

        # Try to parse as Atom feed first
        entries = root.findall("atom:entry", ns)
        if entries:
            LOG.debug(
                "'%s': Detected Atom feed format with %s entries",
                task.name,
                len(entries),
                extra={"task_name": task.name, "feed_url": feed_url, "entry_count": len(entries)},
            )
            for entry in entries:
                link_elem: Element | None = entry.find("atom:link[@rel='alternate']", ns)
                if link_elem is None:
                    link_elem = entry.find("atom:link", ns)

                url: str = ""
                if link_elem is not None and link_elem.get("href"):
                    url = link_elem.get("href", "")

                if not url:
                    LOG.warning(
                        "'%s': Atom entry missing URL. Skipping.",
                        task.name,
                        extra={"task_name": task.name, "feed_url": feed_url},
                    )
                    continue

                title_elem: Element | None = entry.find("atom:title", ns)
                title: str = title_elem.text if title_elem is not None and title_elem.text else ""
                description_elem = entry.find("media:group/media:description", ns)
                if description_elem is None:
                    description_elem = entry.find("media:description", ns)
                if description_elem is None:
                    description_elem = entry.find("atom:summary", ns)
                if description_elem is None:
                    description_elem = entry.find("atom:content", ns)
                description: str = (
                    description_elem.text if description_elem is not None and description_elem.text else ""
                )

                thumbnail = RssGenericHandler._thumbnail(entry, ns, feed_url)

                pub_elem: Element | None = entry.find("atom:published", ns)
                published: str = pub_elem.text if pub_elem is not None and pub_elem.text else ""

                real_count += 1
                items.append(
                    {
                        "url": url,
                        "title": title,
                        "description": description,
                        "published": published,
                        "thumbnail": thumbnail,
                    }
                )
        else:
            # Try to parse as RSS feed
            rss_items = root.findall(".//item")
            LOG.debug(
                "'%s': Detected RSS feed format with %s items",
                task.name,
                len(rss_items),
                extra={"task_name": task.name, "feed_url": feed_url, "entry_count": len(rss_items)},
            )

            for item in rss_items:
                # Try different link element names (link, url, media:content)
                url: str = ""

                link_elem = item.find("link")
                if link_elem is not None and link_elem.text:
                    url = link_elem.text
                else:
                    # Try media:content
                    media_elem = item.find("media:content", ns)
                    if media_elem is not None and media_elem.get("url"):
                        url = media_elem.get("url", "")
                    else:
                        # Try enclosure
                        enclosure_elem = item.find("enclosure")
                        if enclosure_elem is not None and enclosure_elem.get("url"):
                            url = enclosure_elem.get("url", "")

                if not url:
                    LOG.warning(
                        "'%s': RSS item missing URL. Skipping.",
                        task.name,
                        extra={"task_name": task.name, "feed_url": feed_url},
                    )
                    continue

                title_elem = item.find("title")
                title: str = title_elem.text if title_elem is not None and title_elem.text else ""
                description_elem = item.find("media:group/media:description", ns)
                if description_elem is None:
                    description_elem = item.find("media:description", ns)
                if description_elem is None:
                    description_elem = item.find("description")
                if description_elem is None:
                    description_elem = item.find("content:encoded", ns)
                description: str = (
                    description_elem.text if description_elem is not None and description_elem.text else ""
                )

                pub_elem = item.find("pubDate")
                published: str = pub_elem.text if pub_elem is not None and pub_elem.text else ""

                thumbnail = RssGenericHandler._thumbnail(item, ns, feed_url)

                real_count += 1
                items.append(
                    {
                        "url": url,
                        "title": title,
                        "description": description,
                        "published": published,
                        "thumbnail": thumbnail,
                    }
                )

        return feed_url, items, real_count

    @staticmethod
    async def extract(task: HandleTask, config: Config | None = None) -> TaskResult | TaskFailure:
        _ = config
        """
        Extract items from an RSS/Atom feed.

        Args:
            task (Task): The task containing the feed URL.
            config (Config | None): Optional handler configuration.

        Returns:
            TaskResult | TaskFailure: Extraction result with parsed items or failure information.

        """
        parsed: dict[str, str] | None = RssGenericHandler.parse(task.url)
        if not parsed and task.name == "Inspector":
            parsed = {"url": task.url}
        if not parsed:
            return TaskFailure(message="Unrecognized RSS/Atom feed URL.")

        params: dict = task.get_ytdlp_opts().get_all()

        try:
            feed_url, items, real_count = await RssGenericHandler._get(task, params, parsed)
        except httpx.HTTPError as exc:
            return TaskFailure(message="Failed to fetch RSS/Atom feed.", error=str(exc))
        except Exception as exc:
            LOG.exception(
                "Failed to fetch RSS/Atom feed for task '%s'.",
                task.name,
                extra={
                    "task_id": task.id,
                    "task_name": task.name,
                    "url": task.url,
                    "exception_type": type(exc).__name__,
                },
            )
            return TaskFailure(message="Failed to fetch RSS/Atom feed.", error=str(exc))

        task_items: list[TaskItem] = []
        archive_fallbacks = 0
        archive_errors: dict[str, int] = {}
        incomplete_archives = 0

        async with ExtractorBatch() as batch:
            for entry in items:
                if not (url := entry.get("url")):
                    continue

                # Try to get static archive ID first
                id_dict: dict[str, str | None] = get_archive_id(url=url)
                archive_id: str | None = id_dict.get("archive_id")

                # If static archive_id fails, try to fetch it via yt-dlp (like generic.py)
                if not archive_id:
                    cache_key = archive_id_cache_key(url)
                    cache_hit = CACHE.has(cache_key)
                    cached = CACHE.get(cache_key) if cache_hit else None
                    if isinstance(cached, str) and cached:
                        archive_id = cached
                    elif cache_hit and cached is None:
                        LOG.debug(
                            "Task '%s' has a cached archive ID lookup failure. Skipping item.",
                            task.name,
                            extra={"task_name": task.name, "url": url},
                        )
                        continue
                    else:
                        if cache_hit:
                            CACHE.delete(cache_key)
                        archive_fallbacks += 1

                        (info, logs) = await fetch_info(
                            config=params,
                            url=url,
                            no_archive=True,
                            no_log=True,
                            capture_logs=logging.ERROR,
                            batch=batch,
                            budget_sleep=True,
                        )

                        if not info:
                            error = " | ".join(logs) if logs else "No yt-dlp error was reported."
                            archive_errors[error] = archive_errors.get(error, 0) + 1
                            CACHE.set(cache_key, None, ttl=ARCHIVE_LOOKUP_FAILURE_TTL, persist=False)
                            continue

                        if not info.get("id") or not info.get("extractor_key"):
                            incomplete_archives += 1
                            CACHE.set(cache_key, None, ttl=ARCHIVE_LOOKUP_FAILURE_TTL, persist=False)
                            continue

                        archive_id = f"{str(info.get('extractor_key', '')).lower()} {info.get('id')}"
                        CACHE.set(cache_key, archive_id, ttl=ARCHIVE_ID_TTL, persist=True)

                metadata: dict[str, Any] = {
                    k: v for k, v in entry.items() if k not in {"url", "title", "description", "published", "thumbnail"}
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
                extra={"task_name": task.name, "item_count": archive_fallbacks},
            )

        for error, count in archive_errors.items():
            LOG.error(
                "Task '%s' failed to generate archive IDs for %s item(s). Skipping unresolved items. yt-dlp: %s",
                task.name,
                count,
                error,
                extra={"task_name": task.name, "item_count": count, "error": error},
            )

        if incomplete_archives:
            LOG.error(
                "Task '%s' received incomplete archive information for %s item(s). Skipping unresolved items.",
                task.name,
                incomplete_archives,
                extra={"task_name": task.name, "item_count": incomplete_archives},
            )

        return TaskResult(
            items=task_items,
            metadata={"feed_url": feed_url, "entry_count": real_count},
        )

    @staticmethod
    def _thumbnail(entry: Element, ns: dict[str, str], base_url: str) -> str:
        candidates = (
            entry.find("media:thumbnail", ns),
            entry.find("media:group/media:thumbnail", ns),
            entry.find("itunes:image", ns),
            entry.find("media:content", ns),
        )

        for element in candidates:
            if element is None:
                continue

            value = element.get("url") or element.get("href")
            if value:
                return urljoin(base_url, value)

        for link in entry.findall("atom:link", ns) + entry.findall("link"):
            if link.get("rel") == "enclosure" and link.get("type", "").startswith("image/"):
                value = link.get("href") or link.get("url")
                if value:
                    return urljoin(base_url, value)

        return ""

    @staticmethod
    def parse(url: str) -> dict[str, str] | None:
        """
        Parse URL for valid RSS/Atom feed.

        Args:
            url (str): The URL to parse.

        Returns:
            dict[str, str] | None: A dictionary with 'url' key if valid RSS/Atom feed, None otherwise.

        """
        if not isinstance(url, str) or not url:
            return None

        return {"url": url} if RssGenericHandler.FEED_PATTERN.search(url) else None

    @staticmethod
    def tests() -> list[tuple[str, bool]]:
        """
        Test cases for the URL parser.

        Returns:
            list[tuple[str, bool]]: A list of tuples containing the URL and expected result.

        """
        return [
            ("https://www.example.com/test.rss", True),
            ("https://www.example.com/test.atom", True),
            ("https://www.example.com/test.atom#handler=rss", True),
            ("https://www.example.com/test.atom?handler=rss", True),
            ("https://www.example.com/feed.rss?version=2.0", True),
            ("https://www.example.com/test.xml", True),
            ("https://www.example.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw", False),
            ("https://www.example.com/playlist?list=PLBCF2DAC6FFB574DE", False),
            ("https://www.example.com/user/SomeUser", False),
            ("https://example.com/feed.ATOM", True),
            ("https://example.com/feed.RSS", True),
        ]
