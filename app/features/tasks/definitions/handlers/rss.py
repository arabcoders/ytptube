import hashlib
import logging
import re
from typing import TYPE_CHECKING, Any
from xml.etree.ElementTree import Element

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskItem, TaskResult
from app.library.cache import Cache
from app.library.Utils import fetch_info, get_archive_id

from ._base_handler import BaseHandler

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

LOG: logging.Logger = logging.getLogger(__name__)
CACHE: Cache = Cache()


class RssGenericHandler(BaseHandler):
    FEED_PATTERN: re.Pattern[str] = re.compile(
        r"\.(rss|atom)(\?.*)?$|handler=rss",
        re.IGNORECASE,
    )

    @staticmethod
    async def can_handle(task: HandleTask) -> bool:
        LOG.debug(f"'{task.name}': Checking if task URL is parsable RSS feed: {task.url}")
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
        LOG.debug(f"'{task.name}': Fetching RSS/Atom feed from {feed_url}")

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
            LOG.debug(f"'{task.name}': Detected Atom feed format with {len(entries)} entries")
            for entry in entries:
                link_elem: Element | None = entry.find("atom:link[@rel='alternate']", ns)
                if link_elem is None:
                    link_elem = entry.find("atom:link", ns)

                url: str = ""
                if link_elem is not None and link_elem.get("href"):
                    url = link_elem.get("href", "")

                if not url:
                    LOG.warning(f"'{task.name}': Atom entry missing URL. Skipping.")
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
            LOG.debug(f"'{task.name}': Detected RSS feed format with {len(rss_items)} items")

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
                    LOG.warning(f"'{task.name}': RSS item missing URL. Skipping.")
                    continue

                title_elem = item.find("title")
                title: str = title_elem.text if title_elem is not None and title_elem.text else ""

                pub_elem = item.find("pubDate")
                published: str = pub_elem.text if pub_elem is not None and pub_elem.text else ""

                real_count += 1
                items.append({"url": url, "title": title, "published": published})

        return feed_url, items, real_count

    @staticmethod
    async def extract(task: HandleTask) -> TaskResult | TaskFailure:
        """
        Extract items from an RSS/Atom feed.

        Args:
            task (Task): The task containing the feed URL.

        Returns:
            TaskResult | TaskFailure: Extraction result with parsed items or failure information.

        """
        parsed: dict[str, str] | None = RssGenericHandler.parse(task.url)
        if not parsed:
            return TaskFailure(message="Unrecognized RSS/Atom feed URL.")

        params: dict = task.get_ytdlp_opts().get_all()

        try:
            feed_url, items, real_count = await RssGenericHandler._get(task, params, parsed)
        except Exception as exc:
            LOG.exception(exc)
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
                        LOG.debug(f"'{task.name}': Cached failure for URL '{url}'. Skipping.")
                        continue
                else:
                    LOG.warning(
                        f"'{task.name}': Unable to generate static archive ID for '{url}' in feed. "
                        "Doing real request to fetch yt-dlp archive ID."
                    )

                    info = await fetch_info(
                        config=params,
                        url=url,
                        no_archive=True,
                        no_log=True,
                    )

                    if not info:
                        LOG.error(
                            f"'{task.name}': Failed to extract info for URL '{url}' to generate archive ID. Skipping."
                        )
                        CACHE.set(cache_key, None)
                        continue

                    if not info.get("id") or not info.get("extractor_key"):
                        LOG.error(
                            f"'{task.name}': Incomplete info extracted for URL '{url}' to generate archive ID. Skipping."
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
