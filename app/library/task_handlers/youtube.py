import asyncio
import logging
import re
from pathlib import Path

from app.library.config import Config
from app.library.DownloadQueue import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.Tasks import Task
from app.library.Utils import is_downloaded
from app.library.YTDLPOpts import YTDLPOpts

LOG: logging.Logger = logging.getLogger(__name__)


class YoutubeHandler:
    queued_ids: set[str] = set()

    FEED = "https://www.youtube.com/feeds/videos.xml?{type}={id}"
    FEED_PLAYLIST = "https://www.youtube.com/feeds/videos.xml?playlist_id={id}"

    CHANNEL_REGEX = re.compile(r"^https?://(?:www\.)?youtube\.com/(?:channel/(?P<id>UC[0-9A-Za-z_-]{22})|)/?$")

    PLAYLIST_REGEX = re.compile(r"^https?://(?:www\.)?youtube\.com/(?:playlist\?list=(?P<id>[A-Za-z0-9_-]+)|).*$")

    @staticmethod
    def can_handle(task: Task, config: Config) -> bool:
        has, _ = YoutubeHandler.has_archive(task, config)
        if not has:
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
        archive_file, params = YoutubeHandler.has_archive(task, config)
        if not archive_file:
            LOG.error(f"Task '{task.id}: {task.name}' does not have an archive file configured.")
            return

        import httpx
        from defusedxml.ElementTree import fromstring

        parsed = YoutubeHandler.parse(task.url)
        if not parsed:
            LOG.error(f"Cannot parse '{task.id}: {task.name}' URL: {task.url}")
            return

        feed_url = YoutubeHandler.FEED.format(type=parsed["type"], id=parsed["id"])

        LOG.debug(f"Fetching '{task.id}: {task.name}' feed.")
        opts = {
            "proxy": params.get("proxy", None),
            "headers": {
                "User-Agent": params.get(
                    "user_agent",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                )
            },
        }

        items = []

        async with httpx.AsyncClient(**opts) as client:
            response = await client.request(method="GET", url=feed_url, timeout=120)
            response.raise_for_status()

            root = fromstring(response.text)
            ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}

            for entry in root.findall("atom:entry", ns):
                vid_elem = entry.find("yt:videoId", ns)
                title_elem = entry.find("atom:title", ns)
                pub_elem = entry.find("atom:published", ns)
                vid = vid_elem.text if vid_elem is not None else ""
                title = title_elem.text if title_elem is not None else ""
                published = pub_elem.text if pub_elem is not None else ""
                items.append(
                    {
                        "id": vid,
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "title": title,
                        "published": published,
                    }
                )

        if len(items) < 1:
            LOG.warning(f"No entries found in '{task.id}: {task.name}' feed. URL: {feed_url}")
            return

        filtered = []
        for item in items:
            status, _ = is_downloaded(archive_file, url=item["url"])
            if status is True or item["id"] in YoutubeHandler.queued_ids:
                continue

            if queue.done.exists(url=item["url"]) or queue.queue.exists(url=item["url"]):
                LOG.debug(f"Item '{item['id']}' already exists in the queue or download history.")
                YoutubeHandler.queued_ids.add(item["id"])
                continue

            YoutubeHandler.queued_ids.add(item["id"])
            filtered.append(item)

        if len(filtered) < 1:
            LOG.debug(f"No new items found in '{task.id}: {task.name}' feed.")
            return

        LOG.info(f"Found '{len(filtered)}' new items from '{task.id}: {task.name}' feed.")

        preset: str = str(task.preset or config.default_preset)
        folder: str = task.folder if task.folder else ""
        template: str = task.template if task.template else ""
        cli: str = task.cli if task.cli else ""

        queued = asyncio.gather(
            *[
                notify.emit(
                    Events.ADD_URL,
                    data={"url": item["url"], "preset": preset, "folder": folder, "template": template, "cli": cli},
                )
                for item in filtered
            ]
        )

        try:
            await queued
        except Exception as e:
            LOG.error(f"Error while adding items from '{task.id}: {task.name}'. {e!s}")
            return

    @staticmethod
    def has_archive(task: Task, config: Config) -> tuple[Path | None, dict]:
        archive_file: Path | None = Path(config.archive_file) if config.keep_archive else None
        params: YTDLPOpts = YTDLPOpts.get_instance()

        if task.preset:
            params.preset(name=task.preset)

        if task.cli:
            params.add_cli(task.cli, from_user=True)

        params = params.get_all()
        if user_archive_file := params.get("download_archive", None):
            archive_file = Path(user_archive_file)

        if not archive_file:
            return (None, params)

        if not archive_file.exists():
            archive_file.parent.mkdir(parents=True, exist_ok=True)
            archive_file.touch(exist_ok=True)

        return (archive_file, params)

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
