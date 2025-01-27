import json
import logging

from .DownloadQueue import DownloadQueue
from .encoder import Encoder

LOG = logging.getLogger("common")


class common:
    """
    This class is used to share common methods between the socket and the API gateways.
    """

    queue: DownloadQueue
    encoder: Encoder

    def __init__(self, queue: DownloadQueue, encoder: Encoder):
        super().__init__()
        self.queue = queue
        self.encoder = encoder

    async def add(
        self, url: str, preset: str, folder: str, ytdlp_cookies: str, ytdlp_config: dict, output_template: str
    ) -> dict[str, str]:
        if ytdlp_cookies and isinstance(ytdlp_cookies, dict):
            ytdlp_cookies = self.encoder.encode(ytdlp_cookies)

        status = await self.queue.add(
            url=url,
            preset=preset if preset else "default",
            folder=folder,
            ytdlp_cookies=ytdlp_cookies,
            ytdlp_config=ytdlp_config if isinstance(ytdlp_config, dict) else {},
            output_template=output_template,
        )

        return status

    def format_item(self, item: dict) -> dict:
        """
        Format the item to be added to the download queue.

        Args:
            item (dict): The item to be formatted.

        Raises:
            ValueError: If the url is not provided.
            ValueError: If the yt-dlp config is not a valid json.

        Returns:
            dict: The formatted item
        """
        url: str = item.get("url")

        if not url:
            raise ValueError("url param is required.")

        preset: str = str(item.get("preset", self.config.default_preset))
        folder: str = str(item.get("folder")) if item.get("folder") else ""
        cookies: str = str(item.get("cookies")) if item.get("cookies") else ""
        template: str = str(item.get("template")) if item.get("template") else ""

        config = item.get("config")
        if isinstance(config, str) and config:
            try:
                config = json.loads(config)
            except Exception as e:
                raise ValueError(f"Failed to parse json yt-dlp config for '{url}'. {str(e)}")

        item = {
            "url": url,
            "preset": preset,
            "folder": folder,
            "ytdlp_cookies": cookies,
            "ytdlp_config": config if isinstance(config, dict) else {},
            "output_template": template,
        }

        return item
