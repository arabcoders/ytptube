import logging
import re
from typing import TYPE_CHECKING, Any
from xml.etree.ElementTree import Element

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskItem, TaskResult
from app.features.ytdlp.utils import get_archive_id

from ._base_handler import BaseHandler

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

LOG: logging.Logger = logging.getLogger("handlers.youtube")


class YoutubeHandler(BaseHandler):
    FEED: str = "https://www.youtube.com/feeds/videos.xml?{type}={id}"

    CHANNEL_REGEX: re.Pattern[str] = re.compile(
        r"^https?://(?:www\.)?youtube\.com/(?:channel/(?P<id>UC[0-9A-Za-z_-]{22})|)/?$"
    )

    PLAYLIST_REGEX: re.Pattern[str] = re.compile(
        r"^https?://(?:www\.)?youtube\.com/(?:playlist\?list=(?P<id>[A-Za-z0-9_-]+)|).*$"
    )

    @staticmethod
    async def can_handle(task: HandleTask) -> bool:
        LOG.debug(f"'{task.name}': Checking if task URL is parsable YouTube URL: {task.url}")
        return YoutubeHandler.parse(task.url) is not None

    @staticmethod
    async def _get(task: HandleTask, params: dict, parsed: dict[str, str]) -> tuple[str, list[dict[str, str]], int]:
        """
        Fetch the feed and return raw entries.

        Args:
            task (Task): The task containing the YouTube URL.
            params (dict): The ytdlp options.
            parsed (dict): The parsed URL components.

        Returns:
            tuple[str, list[dict[str, str]], int]: The feed URL, list of

        """
        from defusedxml.ElementTree import fromstring

        feed_url: str = YoutubeHandler.FEED.format(type=parsed["type"], id=parsed["id"])
        LOG.debug(f"'{task.name}': Fetching feed.")

        response = await YoutubeHandler.request(url=feed_url, ytdlp_opts=params)
        response.raise_for_status()

        root: Element[str] = fromstring(response.text)
        ns: dict[str, str] = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
        }

        items: list[dict[str, str]] = []
        real_count = 0

        for entry in root.findall("atom:entry", ns):
            vid_elem: Element[str] | None = entry.find("yt:videoId", ns)
            vid: str = vid_elem.text if vid_elem is not None and vid_elem.text else ""
            if not vid:
                LOG.warning(f"'{task.name}': Entry in the feed is missing a video ID. Skipping.")
                continue

            url: str = f"https://www.youtube.com/watch?v={vid}"

            id_dict: dict[str, str | None] = get_archive_id(url)
            archive_id: str | None = id_dict.get("archive_id")
            if not archive_id:
                LOG.warning(f"'{task.name}': Could not compute archive ID for video '{vid}' in feed. Skipping.")
                continue

            title_elem: Element[str] | None = entry.find("atom:title", ns)
            title: str = title_elem.text if title_elem is not None and title_elem.text else ""

            pub_elem: Element[str] | None = entry.find("atom:published", ns)
            published: str = pub_elem.text if pub_elem is not None and pub_elem.text else ""

            real_count += 1

            items.append({"id": vid, "url": url, "title": title, "published": published, "archive_id": archive_id})

        return feed_url, items, real_count

    @staticmethod
    async def extract(task: HandleTask) -> TaskResult | TaskFailure:
        parsed: dict[str, str] | None = YoutubeHandler.parse(task.url)
        if not parsed:
            return TaskFailure(message="Unrecognized YouTube channel or playlist URL.")

        params: dict = task.get_ytdlp_opts().get_all()

        try:
            feed_url, items, real_count = await YoutubeHandler._get(task, params, parsed)
        except Exception as exc:
            LOG.exception(exc)
            return TaskFailure(message="Failed to fetch YouTube feed.", error=str(exc))

        task_items: list[TaskItem] = []

        for entry in items:
            if not (url := entry.get("url")):
                continue

            archive_id: str = entry.get("archive_id")
            metadata: dict[str, Any] = {"published": entry.get("published")}

            task_items.append(TaskItem(url=url, title=entry.get("title"), archive_id=archive_id, metadata=metadata))

        return TaskResult(items=task_items, metadata={"feed_url": feed_url, "entry_count": real_count})

    @staticmethod
    def parse(url: str) -> dict[str, str] | None:
        """
        Parse YouTube channel or playlist URL.

        Args:
            url (str): The YouTube URL to parse.

        Returns:
            {'type': 'channel', 'id': <channel-id>}
            {'type': 'playlist', 'id': <playlist-id>}
            None if the URL is neither.

        """
        if (m := YoutubeHandler.CHANNEL_REGEX.match(url)) and m.group("id"):
            return {"type": "channel_id", "id": m.group("id")}

        if (m := YoutubeHandler.PLAYLIST_REGEX.match(url)) and m.group("id"):
            return {"type": "playlist_id", "id": m.group("id")}

        return None

    @staticmethod
    def tests() -> list[tuple[str, bool]]:
        """
        Test cases for the URL parser.

        Returns:
            list[tuple[str, bool]]: A list of tuples containing the URL and expected result.

        """
        return [
            ("https://www.youtube.com/channel/UCabc123ABCDEFGHIJKLMN", True),
            ("https://youtube.com/c/MyCustomName", False),
            ("https://youtube.com/user/SomeUser123", False),
            ("https://youtube.com/@SomeHandle", False),
            ("https://youtube.com/playlist?list=PLxyz789ABCDEFGHIJ", True),
            ("https://youtube.com/watch?v=foo&list=PLxyz789ABCDEFGHIJ", True),
            ("https://youtube.com/watch?v=foo", False),
        ]
