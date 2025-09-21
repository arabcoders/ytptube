# flake8: noqa: ARG004
from typing import Any

import httpx
from yt_dlp.utils.networking import random_user_agent

from app.library.config import Config
from app.library.Tasks import Task, TaskFailure, TaskResult


class BaseHandler:
    @staticmethod
    def can_handle(task: Task) -> bool:
        return False

    @staticmethod
    async def extract(task: Task, config: Config | None = None) -> TaskResult | TaskFailure:
        raise NotImplementedError

    @classmethod
    async def inspect(cls, task: Task, config: Config | None = None) -> TaskResult | TaskFailure:
        return await cls.extract(task=task, config=config)

    @staticmethod
    def parse(url: str) -> Any | None:
        return None

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
