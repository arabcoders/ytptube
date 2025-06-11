import logging

from .config import Config
from .DownloadQueue import DownloadQueue
from .encoder import Encoder
from .ItemDTO import Item

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
        self.queue: DownloadQueue = queue or DownloadQueue.get_instance()
        self.encoder: Encoder = encoder or Encoder()
        config: Config = config or Config.get_instance()
        self.default_preset: str = config.default_preset

    async def add(self, item: Item) -> dict[str, str]:
        """
        Add an item to the download queue.

        Args:
            item (Item): The item to be added to the queue.

        Returns:
            dict[str, str]: The status of the download.
            { "status": "text" }

        """
        return await self.queue.add(item=item)
