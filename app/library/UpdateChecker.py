import asyncio
import logging
import re
from typing import Any

from aiohttp import web

from .cache import Cache
from .config import Config
from .Events import EventBus, Events
from .httpx_client import get_async_client
from .Scheduler import Scheduler
from .Singleton import Singleton
from .version import APP_VERSION

LOG: logging.Logger = logging.getLogger("update_checker")


class UpdateChecker(metaclass=Singleton):
    """
    Checks for application updates from GitHub releases.
    """

    GITHUB_API_URL: str = "https://api.github.com/repos/arabcoders/ytptube/releases/latest"
    "GitHub API endpoint for latest release"

    YTDLP_API_URL: str = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
    "GitHub API endpoint for yt-dlp latest release"

    CACHE_DURATION: int = 300
    "Cache duration in seconds (5 minutes)"

    CACHE_KEY: str = "update_checker:result"
    "Cache key for storing check results"

    YTDLP_CACHE_KEY: str = "update_checker:ytdlp"
    "Cache key for storing yt-dlp check results"

    def __init__(
        self, config: Config | None = None, scheduler: Scheduler | None = None, notify: EventBus | None = None
    ) -> None:
        self._config: Config = config or Config.get_instance()
        "Instance of Config to use."

        self._scheduler: Scheduler = scheduler or Scheduler.get_instance()
        "Instance of Scheduler to use."

        self._notify: EventBus = notify or EventBus.get_instance()
        "Instance of EventBus for notifications."

        self._cache: Cache = Cache()
        "Instance of Cache for caching check results."

        self._job_id: str | None = None
        "Scheduler job ID for update checks."

    @staticmethod
    def get_instance(
        config: Config | None = None, scheduler: Scheduler | None = None, notify: EventBus | None = None
    ) -> "UpdateChecker":
        return UpdateChecker(config=config, scheduler=scheduler, notify=notify)

    def attach(self, _: web.Application) -> None:
        from .Services import Services

        Services.get_instance().add("update_checker", self)

        if not self._config.check_for_updates:
            LOG.info("Update checking is disabled.")
            return

        if re.search(r"^v\d+", APP_VERSION) is None:
            LOG.warning("Not on a release version, skipping update checker setup.")
            return

        async def event_handler(_, __):
            await self.check_for_updates()

        self._notify.subscribe(
            event=Events.STARTED,
            callback=event_handler,
            name=f"{__class__.__name__}.{__class__.attach.__name__}",
        )

        self._schedule_check()

    async def on_shutdown(self, _: web.Application | None) -> None:
        """
        Handle application shutdown event.

        Args:
            _ (web.Application): The aiohttp web application instance.

        """
        if not self._job_id:
            return

        self._scheduler.remove(self._job_id)
        self._job_id = None

    def _schedule_check(self) -> None:
        if not self._config.check_for_updates:
            return

        timer: str = "0 3 * * *"

        self._job_id = self._scheduler.add(
            timer=timer,
            func=lambda: asyncio.create_task(self.check_for_updates()),
            id=f"{__class__.__name__}.{self.check_for_updates.__name__}",
        )

    async def check_for_updates(self) -> tuple[tuple[str, str | None], tuple[str, str | None]]:
        """
        Check for updates from GitHub releases for both the app and yt-dlp.
        Updates config.new_version and config.yt_new_version if newer versions are available.
        Stops the scheduled task if an app update is found.

        Returns:
            tuple[tuple[str, str | None], tuple[str, str | None]]: ((app_status, app_version), (ytdlp_status, ytdlp_version))
                status: "disabled", "error", "up_to_date", or "update_available"
                version: The new version tag if available, None otherwise

        """
        if not self._config.check_for_updates:
            return (("disabled", None), ("disabled", None))

        app_cached = await self._cache.aget(self.CACHE_KEY)
        ytdlp_cached = await self._cache.aget(self.YTDLP_CACHE_KEY)

        if app_cached and ytdlp_cached:
            return (app_cached, ytdlp_cached)

        app_result = app_cached or await self._check_app_version()
        ytdlp_result = ytdlp_cached or await self._check_ytdlp_version()

        return (app_result, ytdlp_result)

    async def _check_github_version(
        self,
        name: str,
        api_url: str,
        current_version: str,
        cache_key: str,
        strip_v_prefix: bool = False,
    ) -> tuple[str, str | None]:
        try:
            LOG.info(f"Checking for {name} updates...")

            client = get_async_client(use_curl=False)
            response = await client.get(
                api_url,
                headers={"Accept": "application/vnd.github+json"},
                timeout=10.0,
            )

            if 200 != response.status_code:
                LOG.warning(f"Failed to check for {name} updates: HTTP {response.status_code}")
                return ("error", None)

            data: dict[str, Any] = response.json()

            latest_tag: str = data.get("tag_name", "")
            if not latest_tag:
                LOG.warning(f"No tag_name found in {name} GitHub release data.")
                return ("error", None)

            compare_current: str = current_version.lstrip("v") if strip_v_prefix else current_version
            compare_latest: str = latest_tag.lstrip("v") if strip_v_prefix else latest_tag

            if self._compare_versions(compare_current, compare_latest):
                LOG.warning(f"{name} update available: {current_version} -> {latest_tag}")
                result = ("update_available", latest_tag)
                await self._cache.aset(cache_key, result, self.CACHE_DURATION)
                return result

            LOG.info(f"No {name} updates available.")
            result = ("up_to_date", None)
            await self._cache.aset(cache_key, result, self.CACHE_DURATION)
            return result
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Error checking for {name} updates: {e!s}")
            return ("error", None)

    async def _check_app_version(self) -> tuple[str, str | None]:
        status, new_version = await self._check_github_version(
            name="application",
            api_url=self.GITHUB_API_URL,
            current_version=APP_VERSION,
            cache_key=self.CACHE_KEY,
            strip_v_prefix=True,
        )

        if "update_available" == status:
            self._config.new_version = new_version or ""
            await self.on_shutdown(None)
        elif "up_to_date" == status:
            self._config.new_version = ""

        return (status, new_version)

    async def _check_ytdlp_version(self) -> tuple[str, str | None]:
        current_version: str = self._config._ytdlp_version()
        if not current_version or "0.0.0" == current_version:
            LOG.warning("Could not determine yt-dlp version, skipping yt-dlp update check.")
            return ("error", None)

        status, new_version = await self._check_github_version(
            name="yt-dlp",
            api_url=self.YTDLP_API_URL,
            current_version=current_version,
            cache_key=self.YTDLP_CACHE_KEY,
            strip_v_prefix=False,
        )

        if "update_available" == status:
            self._config.yt_new_version = new_version or ""
        elif "up_to_date" == status:
            self._config.yt_new_version = ""

        return (status, new_version)

    def _compare_versions(self, current: str, latest: str) -> bool:
        """
        Compare version strings to determine if an update is available.

        Args:
            current (str): Current version string
            latest (str): Latest version string

        Returns:
            bool: True if latest > current, False otherwise

        """
        try:
            from packaging.version import parse as parse_version

            return parse_version(latest) > parse_version(current)
        except Exception as e:
            LOG.warning(f"Error comparing versions '{current}' vs '{latest}': {e}")
            return False
