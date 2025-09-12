# flake8: noqa: ARG004
import logging
from typing import Any

import httpx
from yt_dlp.utils.networking import random_user_agent

from app.library.config import Config
from app.library.DownloadQueue import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.ItemDTO import ItemDTO
from app.library.Tasks import Task

LOG: logging.Logger = logging.getLogger(__name__)


class BaseHandler:
    queued: set[str] = set()
    failure_count: dict[str, int] = {}

    def __init_subclass__(cls, **kwargs):
        """Ensure each subclass has its own state containers."""
        super().__init_subclass__(**kwargs)
        if "queued" not in cls.__dict__:
            cls.queued = set()
        if "failure_count" not in cls.__dict__:
            cls.failure_count = {}

        async def event_handler(data, _):
            if data and data.data:
                await cls.on_error(data.data)

        EventBus.get_instance().subscribe(Events.ITEM_ERROR, event_handler, f"{cls.__name__}.on_error")

    @staticmethod
    def can_handle(task: Task) -> bool:
        return False

    @staticmethod
    async def handle(task: Task, notify: EventBus, config: Config, queue: DownloadQueue):
        pass

    @staticmethod
    def parse(url: str) -> Any | None:
        return None

    @classmethod
    async def on_error(cls, item: ItemDTO) -> None:
        """
        Handle errors by logging them and removing the queued ID if it exists.

        Args:
            item (ItemDTO): The error data containing the URL and other information.

        """
        if not item or not isinstance(item, ItemDTO):
            return

        if not item.archive_id or not cls.failure_count.get(item.archive_id, None):
            LOG.debug(f"Item '{item.name()}' not queued by the handler.")
            return

        failCount: int = int(cls.failure_count.get(item.archive_id, 0))

        LOG.info(f"Removing '{item.name()}' from queued IDs due to error. Failure count: '{failCount + 1}'.")
        if item.archive_id in cls.queued:
            cls.queued.remove(item.archive_id)

        cls.failure_count[item.archive_id] = 1 + failCount

    @staticmethod
    def tests() -> list[tuple[str, bool]]:
        return []

    @staticmethod
    async def request(url: str, headers: dict | None = None, ytdlp_opts: dict | None = None) -> httpx.Response:
        headers = {} if not isinstance(headers, dict) else headers
        ytdlp_opts = {} if not isinstance(ytdlp_opts, dict) else ytdlp_opts

        opts: dict[str, Any] = {
            "headers": {
                "User-Agent": random_user_agent(),
            },
        }

        try:
            from httpx_curl_cffi import AsyncCurlTransport, CurlOpt

            opts["transport"] = AsyncCurlTransport(
                impersonate="chrome",
                default_headers=True,
                curl_options={CurlOpt.FRESH_CONNECT: True},
            )
            opts["headers"].pop("User-Agent", None)
        except Exception:
            pass

        for k, v in headers.items():
            opts["headers"][k] = v

        if proxy := ytdlp_opts.get("proxy", None):
            opts["proxy"] = proxy

        async with httpx.AsyncClient(**opts) as client:
            return await client.request(method="GET", url=url, timeout=ytdlp_opts.get("socket_timeout", 120))
