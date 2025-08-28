import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any

from app.library.config import Config
from app.library.DownloadQueue import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.ItemDTO import Item, ItemDTO
from app.library.Tasks import Task
from app.library.Utils import archive_read, get_archive_id

if TYPE_CHECKING:
    from app.library.Download import Download

LOG: logging.Logger = logging.getLogger(__name__)

EventBus.get_instance().subscribe(
    Events.ITEM_ERROR,
    lambda data, _, **__: YoutubeHandler.on_error(data.data),
    f"{__name__}.on_error",
)


class YoutubeHandler:
    queued_ids: set[str] = set()
    failure_count: dict[str, int] = {}

    FEED = "https://www.youtube.com/feeds/videos.xml?{type}={id}"

    CHANNEL_REGEX = re.compile(r"^https?://(?:www\.)?youtube\.com/(?:channel/(?P<id>UC[0-9A-Za-z_-]{22})|)/?$")

    PLAYLIST_REGEX = re.compile(r"^https?://(?:www\.)?youtube\.com/(?:playlist\?list=(?P<id>[A-Za-z0-9_-]+)|).*$")

    @staticmethod
    def can_handle(task: Task) -> bool:
        if not task.get_ytdlp_opts().get_all().get("download_archive"):
            LOG.debug(f"Task '{task.id}: {task.name}' does not have an archive file configured.")
            return False

        LOG.debug(f"Checking if task '{task.id}: {task.name}' can handle YouTube URL: {task.url}")
        return YoutubeHandler.parse(task.url) is not None

    @staticmethod
    async def handle(task: Task, notify: EventBus, config: Config, queue: DownloadQueue):
        """
        Fetch the Atom feed for a YouTube channel or playlist, parse entries,
        and return a list of videos with metadata.

        Args:
            task (Task): The task containing the YouTube URL.
            notify (EventBus): The event bus for notifications.
            config (Config): The configuration instance.
            queue (DownloadQueue): The download queue instance.

        """
        params: dict = task.get_ytdlp_opts().get_all()
        if not (archive_file := params.get("download_archive")):
            LOG.error(f"Task '{task.id}: {task.name}' does not have an archive file.")
            return

        import httpx
        from defusedxml.ElementTree import fromstring

        parsed: dict[str, str] | None = YoutubeHandler.parse(task.url)
        if not parsed:
            LOG.error(f"Cannot parse '{task.id}: {task.name}' URL: {task.url}")
            return

        feed_url: str = YoutubeHandler.FEED.format(type=parsed["type"], id=parsed["id"])

        LOG.debug(f"Fetching '{task.id}: {task.name}' feed.")
        opts: dict[str, Any] = {
            "proxy": params.get("proxy"),
            "headers": {
                "User-Agent": params.get(
                    "user_agent",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                )
            },
        }

        try:
            from httpx_curl_cffi import AsyncCurlTransport, CurlOpt

            opts["transport"] = AsyncCurlTransport(
                impersonate="chrome",
                default_headers=True,
                curl_options={CurlOpt.FRESH_CONNECT: True},
            )
            opts.pop("headers", None)
        except Exception:
            pass

        items: list = []

        async with httpx.AsyncClient(**opts) as client:
            response: httpx.Response = await client.request(method="GET", url=feed_url, timeout=120)
            response.raise_for_status()

            root = fromstring(response.text)
            ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}

            for entry in root.findall("atom:entry", ns):
                vid_elem = entry.find("yt:videoId", ns)
                vid = vid_elem.text if vid_elem is not None else ""
                if not vid:
                    LOG.warning(f"Entry in '{task.id}: {task.name}' feed is missing a video ID. Skipping entry.")
                    continue

                title_elem = entry.find("atom:title", ns)
                pub_elem = entry.find("atom:published", ns)
                title = title_elem.text if title_elem is not None else ""
                published = pub_elem.text if pub_elem is not None else ""
                url: str = f"https://www.youtube.com/watch?v={vid}"
                idDict = get_archive_id(url=url)
                if not (archive_id := idDict.get("archive_id")):
                    LOG.warning(f"Item '{title}' does not have a valid archive ID. URL: {url}")
                    continue

                items.append({"id": vid, "url": url, "title": title, "published": published, "archive_id": archive_id})

        if len(items) < 1:
            LOG.warning(f"No entries found in '{task.id}: {task.name}' feed. URL: {feed_url}")
            return

        filtered: list = []

        downloaded: list[str] = archive_read(
            file=archive_file,
            ids=[item["archive_id"] for item in items if item["id"] not in YoutubeHandler.queued_ids],
        )

        for item in items:
            if item["archive_id"] in downloaded:
                YoutubeHandler.queued_ids.add(item["id"])
                continue

            if queue.queue.exists(url=item["url"]):
                LOG.debug(f"Item '{item['id']}' exists in the queue.")
                YoutubeHandler.queued_ids.add(item["id"])
                continue

            try:
                done: Download = queue.done.get(url=item["url"])
                if "error" != done.info.status:
                    LOG.debug(f"Item '{item['id']}' exists in the history.")
                    YoutubeHandler.queued_ids.add(item["id"])
                    continue
            except KeyError:
                pass

            YoutubeHandler.queued_ids.add(item)
            filtered.append(item)

        if len(filtered) < 1:
            LOG.debug(f"No new items found in '{task.id}: {task.name}' feed.")
            return

        LOG.info(f"Found '{len(filtered)}' new items from '{task.id}: {task.name}' feed.")

        rItem: Item = Item.format(
            {
                "url": feed_url,
                "preset": str(task.preset or config.default_preset),
                "folder": task.folder if task.folder else "",
                "template": task.template if task.template else "",
                "cli": task.cli if task.cli else "",
                "extras": {"source_task": task.id},
            }
        )

        try:
            await asyncio.gather(
                *[
                    notify.emit(Events.ADD_URL, data=rItem.new_with({"url": item["url"]}).serialize())
                    for item in filtered
                ]
            )
        except Exception as e:
            LOG.error(f"Error while adding items from '{task.id}: {task.name}'. {e!s}")
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
    async def on_error(item: ItemDTO) -> None:
        """
        Handle errors by logging them and removing the queued ID if it exists.

        Args:
            item (ItemDTO): The error data containing the URL and other information.

        """
        cls = YoutubeHandler
        if not item or not isinstance(item, ItemDTO):
            return

        cls.queued_ids.add(item.id)

        if item.id not in cls.queued_ids:
            return

        currentFailureCount: int = cls.failure_count.get(item.id, 0)

        LOG.info(f"Removing '{item.name()}' from queued IDs due to error. Failure count: '{currentFailureCount + 1}'.")
        cls.queued_ids.remove(item.id)

        cls.failure_count[item.id] = cls.failure_count.get(item.id, 0) + 1

    @staticmethod
    def tests() -> list[str]:
        """
        Return a list of test URLs to validate the parsing logic.
        """
        return [
            "https://www.youtube.com/channel/UCabc123ABCDEFGHIJKLMN",
            "https://youtube.com/c/MyCustomName",
            "https://youtube.com/user/SomeUser123",
            "https://youtube.com/@SomeHandle",
            "https://youtube.com/playlist?list=PLxyz789ABCDEFGHIJ",
            "https://youtube.com/watch?v=foo&list=PLxyz789ABCDEFGHIJ",
            "https://youtube.com/watch?v=foo",
        ]
