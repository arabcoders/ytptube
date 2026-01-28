import logging
import re
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskItem, TaskResult
from app.features.ytdlp.utils import get_archive_id

from ._base_handler import BaseHandler

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

LOG: logging.Logger = logging.getLogger("handlers.twitch")


class TwitchHandler(BaseHandler):
    FEED: str = "https://twitchrss.appspot.com/vodonly/{handle}"

    RX: re.Pattern[str] = re.compile(r"^https?:\/\/(?:www\.|m\.)?twitch\.tv\/(?P<id>[a-z0-9_]{3,25})(?:\/.*)?$")

    @staticmethod
    async def can_handle(task: HandleTask) -> bool:
        LOG.debug(f"Checking if task '{task.name}' is using parsable Twitch URL: {task.url}")
        return TwitchHandler.parse(task.url) is not None

    @staticmethod
    async def _collect_feed(
        task: HandleTask,
        params: dict,
        handle_name: str,
    ) -> tuple[str, list[dict[str, str]], bool]:
        from defusedxml.ElementTree import fromstring

        feed_url: str = TwitchHandler.FEED.format(handle=handle_name)

        LOG.debug(f"Fetching '{task.name}' feed.")
        response = await TwitchHandler.request(url=feed_url, ytdlp_opts=params)
        response.raise_for_status()

        root: Element[str] = fromstring(response.text)
        items: list[dict[str, str]] = []
        has_items = False

        for entry in root.findall("channel/item"):
            link_elem: Element[str] | None = entry.find("link")
            url: str = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            if not url:
                LOG.warning(f"Entry in '{task.name}' feed is missing URL. Skipping entry.")
                continue

            match: re.Match[str] | None = re.search(
                r"^https?://(?:www\.)?twitch\.tv/videos/(?P<id>\d+)(?:[/?].*)?$", url
            )
            if not match:
                LOG.warning(f"URL in '{task.name}' feed does not look like a VOD link: {url}")
                continue

            vid: str = match.group("id")

            title_elem: Element[str] | None = entry.find("title")
            title: str = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

            has_items = True

            id_dict = get_archive_id(url)
            archive_id: str | None = id_dict.get("archive_id")
            if not archive_id:
                LOG.warning(f"Could not compute archive ID for video '{vid}' in '{task.name}' feed. Skipping entry.")
                continue

            items.append({"id": vid, "url": url, "title": title, "archive_id": archive_id})

        return feed_url, items, has_items

    @staticmethod
    async def extract(task: HandleTask) -> TaskResult | TaskFailure:
        handle_name: str | None = TwitchHandler.parse(task.url)
        if not handle_name:
            return TaskFailure(message="Unrecognized Twitch channel URL.")

        params: dict = task.get_ytdlp_opts().get_all()

        try:
            feed_url, items, has_items = await TwitchHandler._collect_feed(task, params, handle_name)
        except Exception as exc:
            LOG.exception(exc)
            return TaskFailure(message="Failed to fetch Twitch feed.", error=str(exc))

        task_items: list[TaskItem] = []

        for entry in items:
            if not (url := entry.get("url")):
                continue

            archive_id: str = entry.get("archive_id")
            task_items.append(TaskItem(url=url, title=entry.get("title"), archive_id=archive_id))

        return TaskResult(items=task_items, metadata={"feed_url": feed_url, "has_entries": has_items})

    @staticmethod
    def parse(url: str) -> str | None:
        """
        Parse twitch URL to extract the channel.

        Args:
            url (str): The url to check.

        Returns:
            str | None: The parsed ID if successful, None otherwise.

        """
        match: re.Match[str] | None = TwitchHandler.RX.match(url)
        return match.group("id") if match else None

    @staticmethod
    def tests() -> list[tuple[str, bool]]:
        """
        Test cases for the URL parser.

        Returns:
            list[tuple[str, bool]]: A list of tuples containing the URL and expected result.

        """
        return [
            ("https://www.twitch.tv/test_username", True),
            ("https://twitch.tv/test_username", True),
            ("http://m.twitch.tv/test_username,", True),
            ("https://www.twitch.tv/test_username/", True),
            ("https://twitch.tv/test_username/", True),
            ("http://m.twitch.tv/test_username/,", True),
            ("twitch.tv/test_username/", False),
        ]
