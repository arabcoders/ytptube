import hashlib
import re
from typing import TYPE_CHECKING, Any
from xml.etree.ElementTree import Element

import httpx

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskItem, TaskResult
from app.features.ytdlp.extractor import fetch_info
from app.features.ytdlp.utils import get_archive_id
from app.library.cache import Cache
from app.library.config import Config
from app.library.log import get_logger

from ._base_handler import BaseHandler

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

LOG = get_logger()
CACHE: Cache = Cache()


class RssGenericHandler(BaseHandler):
    FEED_PATTERN: re.Pattern[str] = re.compile(
        r"\.(rss|atom)(\?.*)?$|handler=rss",
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

                pub_elem: Element | None = entry.find("atom:published", ns)
                published: str = pub_elem.text if pub_elem is not None and pub_elem.text else ""

                real_count += 1
                items.append({"url": url, "title": title, "published": published})
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

                pub_elem = item.find("pubDate")
                published: str = pub_elem.text if pub_elem is not None and pub_elem.text else ""

                real_count += 1
                items.append({"url": url, "title": title, "published": published})

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

        for entry in items:
            if not (url := entry.get("url")):
                continue

            # Try to get static archive ID first
            id_dict: dict[str, str | None] = get_archive_id(url=url)
            archive_id: str | None = id_dict.get("archive_id")

            # If static archive_id fails, try to fetch it via yt-dlp (like generic.py)
            if not archive_id:
                cache_key: str = hashlib.sha256(f"{task.name}-{url}".encode()).hexdigest()

                if CACHE.has(cache_key):
                    archive_id = CACHE.get(cache_key)
                    if not archive_id:
                        LOG.debug(
                            "Task '%s' has a cached archive ID lookup failure. Skipping item.",
                            task.name,
                            extra={"task_name": task.name, "url": url},
                        )
                        continue
                else:
                    LOG.warning(
                        "Task '%s' could not generate a static archive ID. Fetching it with yt-dlp.",
                        task.name,
                        extra={"task_name": task.name, "url": url},
                    )

                    (info, _) = await fetch_info(
                        config=params,
                        url=url,
                        no_archive=True,
                        no_log=True,
                        budget_sleep=True,
                    )

                    if not info:
                        LOG.error(
                            "Task '%s' failed to extract info to generate an archive ID. Skipping item.",
                            task.name,
                            extra={"task_name": task.name, "url": url},
                        )
                        CACHE.set(cache_key, None)
                        continue

                    if not info.get("id") or not info.get("extractor_key"):
                        LOG.error(
                            "Task '%s' returned incomplete info while generating an archive ID. Skipping item.",
                            task.name,
                            extra={"task_name": task.name, "url": url},
                        )
                        CACHE.set(cache_key, None)
                        continue

                    archive_id = f"{str(info.get('extractor_key', '')).lower()} {info.get('id')}"
                    CACHE.set(cache_key, archive_id)

            metadata: dict[str, Any] = {k: v for k, v in entry.items() if k not in {"url", "title", "published"}}

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
            metadata={"feed_url": feed_url, "entry_count": real_count},
        )

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
            ("https://www.example.com/test.xml", False),
            ("https://www.example.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw", False),
            ("https://www.example.com/playlist?list=PLBCF2DAC6FFB574DE", False),
            ("https://www.example.com/user/SomeUser", False),
            ("https://example.com/feed.ATOM", True),
            ("https://example.com/feed.RSS", True),
        ]
