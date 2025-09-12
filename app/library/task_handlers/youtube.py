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


class YoutubeHandler(BaseHandler):
    FEED = "https://www.youtube.com/feeds/videos.xml?{type}={id}"

    CHANNEL_REGEX: re.Pattern[str] = re.compile(
        r"^https?://(?:www\.)?youtube\.com/(?:channel/(?P<id>UC[0-9A-Za-z_-]{22})|)/?$"
    )

    PLAYLIST_REGEX: re.Pattern[str] = re.compile(
        r"^https?://(?:www\.)?youtube\.com/(?:playlist\?list=(?P<id>[A-Za-z0-9_-]+)|).*$"
    )

    @staticmethod
    def can_handle(task: Task) -> bool:
        if not task.get_ytdlp_opts().get_all().get("download_archive"):
            LOG.debug(f"'{task.name}': Task does not have an archive file configured.")
            return False

        LOG.debug(f"'{task.name}': Checking if task URL is parsable YouTube URL: {task.url}")
        return YoutubeHandler.parse(task.url) is not None

    @staticmethod
    async def handle(task: Task, notify: EventBus, queue: DownloadQueue):
        """
        Fetch the Atom feed for a YouTube channel or playlist, parse entries,
        and return a list of videos with metadata.

        Args:
            task (Task): The task containing the YouTube URL.
            notify (EventBus): The event bus for notifications.
            queue (DownloadQueue): The download queue instance.

        """
        from defusedxml.ElementTree import fromstring

        parsed: dict[str, str] | None = YoutubeHandler.parse(task.url)
        if not parsed:
            LOG.error(f"'{task.name}': Cannot parse task URL: {task.url}")
            return

        params: dict = task.get_ytdlp_opts().get_all()

        feed_url: str = YoutubeHandler.FEED.format(type=parsed["type"], id=parsed["id"])
        LOG.debug(f"'{task.name}': Fetching feed.")

        items: list = []

        response = await YoutubeHandler.request(url=feed_url, ytdlp_opts=params)
        response.raise_for_status()

        root: Element[str] = fromstring(response.text)
        ns: dict[str, str] = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
        }

        real_count: int = 0
        for entry in root.findall("atom:entry", ns):
            vid_elem: Element[str] | None = entry.find("yt:videoId", ns)
            vid: str | None = vid_elem.text if vid_elem is not None else ""
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
            title: str | None = title_elem.text if title_elem is not None else ""

            pub_elem: Element[str] | None = entry.find("atom:published", ns)
            published: str | None = pub_elem.text if pub_elem is not None else ""
            real_count += 1

            if archive_id in YoutubeHandler.queued:
                continue

            items.append({"id": vid, "url": url, "title": title, "published": published, "archive_id": archive_id})

        if len(items) < 1:
            if real_count < 1:
                LOG.warning(f"'{task.name}': No entries found the RSS feed. URL: {feed_url}")
            else:
                LOG.debug(f"'{task.name}': Feed has '{real_count}' entries, all already downloaded/queued.")
            return

        filtered: list = []

        downloaded: list[str] = archive_read(params.get("download_archive"), [item["archive_id"] for item in items])

        for item in items:
            YoutubeHandler.queued.add(item["archive_id"])
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

            if item["archive_id"] not in YoutubeHandler.failure_count:
                YoutubeHandler.failure_count[item["archive_id"]] = 0

            filtered.append(item)

        if len(filtered) < 1:
            LOG.debug(f"'{task.name}': Feed has '{real_count}' entries, all already downloaded/queued.")
            return

        LOG.info(f"'{task.name}': Found '{len(filtered)}/{real_count}' new items from feed.")

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
            LOG.error(f"'{task.name}': Error while adding items from task feed. {e!s}")
            return

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
        if m := YoutubeHandler.CHANNEL_REGEX.match(url):
            return {"type": "channel_id", "id": m.group("id")}

        if m := YoutubeHandler.PLAYLIST_REGEX.match(url):
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
