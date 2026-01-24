# flake8: noqa: ARG004
from typing import Any

import httpx
from yt_dlp.utils.networking import random_user_agent

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskResult
from app.library.config import Config
from app.library.httpx_client import async_client


class BaseHandler:
    @staticmethod
    async def can_handle(task: HandleTask) -> bool:
        return False

    @staticmethod
    async def extract(task: HandleTask, config: Config | None = None) -> TaskResult | TaskFailure:
        raise NotImplementedError

    @classmethod
    async def inspect(cls, task: HandleTask, config: Config | None = None) -> TaskResult | TaskFailure:
        return await cls.extract(task=task, config=config)

    @staticmethod
    def parse(url: str) -> Any | None:
        return None

    @staticmethod
    def tests() -> list[tuple[str, bool]]:
        return []

    @staticmethod
    async def request(
        url: str, headers: dict | None = None, ytdlp_opts: dict | None = None, **kwargs
    ) -> httpx.Response:
        """
        Make an HTTP request.

        Args:
            url (str): The URL to request.
            headers (dict | None): Additional headers to include in the request.
            ytdlp_opts (dict | None): yt-dlp options that may affect the request.
            **kwargs: Additional arguments to pass to httpx request.

        Returns:
            httpx.Response: The HTTP response.

        """
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

        async with async_client(**opts) as client:
            method = kwargs.pop("method", "GET").upper()
            timeout = ytdlp_opts.get("timeout", ytdlp_opts.get("socket_timeout", 120))
            return await client.request(method=method, url=url, timeout=timeout, **kwargs)
