import json
import logging

from .config import Config
from .DownloadQueue import DownloadQueue
from .encoder import Encoder

LOG = logging.getLogger("common")


class Common:
    """
    This class is used to share common methods between the socket and the API gateways.
    """

    def __init__(
        self,
        queue: DownloadQueue | None = None,
        encoder: Encoder | None = None,
        config: Config | None = None,
    ):
        super().__init__()
        self.queue = queue or DownloadQueue.get_instance()
        self.encoder = encoder or Encoder()

        config = config or Config.get_instance()
        self.default_preset = config.default_preset

    async def add(
        self, url: str, preset: str, folder: str, cookies: str, config: dict, template: str, extras: dict | None = None
    ) -> dict[str, str]:
        """
        Add an item to the download queue.

        Args:
            url (str): The url to be added to the queue.
            preset (str): The preset to be used for the download.
            folder (str): The folder to save the download to.
            cookies (str): The cookies to be used for the download.
            config (dict): The yt-dlp config to be used for the download.
            template (str): The template to be used for the download.
            extras (dict): Extra data to be added to the download

        Returns:
            dict[str, str]: The status of the download.
            { "status": "text" }

        """
        if cookies and isinstance(cookies, dict):
            cookies = self.encoder.encode(cookies)

        return await self.queue.add(
            url=url,
            preset=preset if preset else self.config.default_preset,
            folder=folder,
            cookies=cookies,
            config=config if isinstance(config, dict) else {},
            template=template,
            extras=extras,
        )

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
            msg = "url param is required."
            raise ValueError(msg)

        preset: str = str(item.get("preset", self.config.default_preset))
        folder: str = str(item.get("folder")) if item.get("folder") else ""
        cookies: str = str(item.get("cookies")) if item.get("cookies") else ""
        template: str = str(item.get("template")) if item.get("template") else ""
        extras = item.get("extras", {})

        config = item.get("config")
        if isinstance(config, str) and config:
            try:
                config = json.loads(config)
            except Exception as e:
                msg = f"Failed to parse json yt-dlp config for '{url}'. {e!s}"
                raise ValueError(msg) from e

        return {
            "url": url,
            "preset": preset,
            "folder": folder,
            "cookies": cookies,
            "config": config if isinstance(config, dict) else {},
            "template": template,
            "extras": extras if isinstance(extras, dict) else {},
        }
