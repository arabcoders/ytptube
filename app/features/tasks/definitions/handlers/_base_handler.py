# flake8: noqa: ARG004
from typing import TYPE_CHECKING, Any

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskResult
from app.library.config import Config
from app.library.httpx_client import Globals, build_request_headers, get_async_client, resolve_curl_transport

if TYPE_CHECKING:
    import httpx


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
    ) -> "httpx.Response":
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

        use_curl = resolve_curl_transport()
        request_headers = build_request_headers(
            base_headers=headers,
            user_agent=Globals.get_random_agent(),
            use_curl=use_curl,
        )

        proxy = ytdlp_opts.get("proxy", None)
        client = get_async_client(proxy=proxy, use_curl=use_curl)
        method = kwargs.pop("method", "GET").upper()
        timeout = ytdlp_opts.get("timeout", ytdlp_opts.get("socket_timeout", 120))
        return await client.request(
            method=method,
            url=url,
            headers=request_headers,
            timeout=timeout,
            **kwargs,
        )
