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
