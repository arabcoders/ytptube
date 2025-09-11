import logging
import re
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

from app.library.DownloadQueue import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.ItemDTO import Item
from app.library.Tasks import Task
from app.library.Utils import archive_read, get_archive_id

from ._base_handler import BaseHandler

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from app.library.Download import Download

LOG: logging.Logger = logging.getLogger(__name__)


class TwitchHandler(BaseHandler):
    FEED = "https://twitchrss.appspot.com/vodonly/{handle}"

    RX: re.Pattern[str] = re.compile(r"^https?:\/\/(?:www\.|m\.)?twitch\.tv\/(?P<id>[a-z0-9_]{3,25})(?:\/.*)?$")

    @staticmethod
    def can_handle(task: Task) -> bool:
        LOG.debug(f"Checking if task '{task.name}' is using parsable Twitch URL: {task.url}")
        return TwitchHandler.parse(task.url) is not None

    @staticmethod
    async def handle(task: Task, notify: EventBus, queue: DownloadQueue):
        """
        Fetch the RSS feed for a Twitch channel VODs, parse entries,
        and enqueue new items that are not in the archive/queue already.

        Args:
            task (Task): The task containing the Twitch channel URL.
            notify (EventBus): The event bus for notifications.
            queue (DownloadQueue): The download queue instance.

        """
        from defusedxml.ElementTree import fromstring

        handleName: str | None = TwitchHandler.parse(task.url)
        if not handleName:
            LOG.error(f"Cannot parse '{task.name}' URL: {task.url}")
            return

        params: dict = task.get_ytdlp_opts().get_all()
        archive_file: str | None = params.get("download_archive")
        if not archive_file:
            LOG.error(f"Task '{task.name}' does not have an archive file.")
            return

        feed_url: str = TwitchHandler.FEED.format(handle=handleName)

        LOG.debug(f"Fetching '{task.name}' feed.")
        response = await TwitchHandler.request(url=feed_url, ytdlp_opts=params)
        response.raise_for_status()

        items: list = []
        has_items = False

        root: Element[str] = fromstring(response.text)
        for entry in root.findall("channel/item"):
            link_elem: Element[str] | None = entry.find("link")
            url: str = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            if not url:
                LOG.warning(f"Entry in '{task.name}' feed is missing URL. Skipping entry.")
                continue

            m: re.Match[str] | None = re.search(r"^https?://(?:www\.)?twitch\.tv/videos/(?P<id>\d+)(?:[/?].*)?$", url)
            if not m:
                LOG.warning(f"URL in '{task.name}' feed does not look like a VOD link: {url}")
                continue

            vid: str = m.group("id")

            title_elem: Element[str] | None = entry.find("title")
            title: str = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

            has_items = True

            id_dict = get_archive_id(url)
            archive_id: str | None = id_dict.get("archive_id")
            if not archive_id:
                LOG.warning(f"Could not compute archive ID for video '{vid}' in '{task.name}' feed. Skipping entry.")
                continue

            if archive_id in TwitchHandler.queued:
                continue

            items.append({"id": vid, "url": url, "title": title, "archive_id": archive_id})

        if len(items) < 1:
            if not has_items:
                LOG.warning(f"No entries found in '{task.name}' feed. URL: {feed_url}")
            else:
                LOG.debug(f"No new items found in '{task.name}' feed.")
            return

        filtered: list = []

        downloaded: list[str] = archive_read(archive_file, [item["archive_id"] for item in items])

        for item in items:
            TwitchHandler.queued.add(item["archive_id"])

            if item["archive_id"] in downloaded:
                continue

            if queue.queue.exists(url=item["url"]):
                continue

            try:
                done: Download = queue.done.get(url=item["url"])
                if "error" != done.info.status:
                    continue
            except KeyError:
                pass

            if item["archive_id"] not in TwitchHandler.failure_count:
                TwitchHandler.failure_count[item["archive_id"]] = 0

            filtered.append(item)

        if len(filtered) < 1:
            LOG.debug(f"No new items found in '{task.name}' feed.")
            return

        LOG.info(f"Found '{len(filtered)}' new items from '{task.name}' feed.")

        rItem: Item = Item.format(
            {
                "url": feed_url,
                "preset": task.preset,
                "folder": task.folder if task.folder else "",
                "template": task.template if task.template else "",
                "cli": task.cli if task.cli else "",
                "auto_start": task.auto_start,
                "extras": {"source_task": task.id},
            }
        )

        try:
            for item in filtered:
                notify.emit(Events.ADD_URL, data=rItem.new_with(url=item["url"]).serialize())
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Error while adding items from '{task.name}'. {e!s}")
            return

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
