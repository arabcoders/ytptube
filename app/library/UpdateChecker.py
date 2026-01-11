import asyncio
import logging
import re
from typing import TYPE_CHECKING

from aiohttp import web

from .cache import Cache
from .config import Config
from .Events import EventBus, Events
from .httpx_client import async_client
from .Scheduler import Scheduler
from .Singleton import Singleton
from .version import APP_VERSION

if TYPE_CHECKING:
    from app.library.dl_fields import Any

LOG: logging.Logger = logging.getLogger("update_checker")


class UpdateChecker(metaclass=Singleton):
    """
    Checks for application updates from GitHub releases.
    """

    GITHUB_API_URL: str = "https://api.github.com/repos/arabcoders/ytptube/releases/latest"
    "GitHub API endpoint for latest release"

    CACHE_DURATION: int = 300
    "Cache duration in seconds (5 minutes)"

    CACHE_KEY: str = "update_checker:result"
    "Cache key for storing check results"

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
        """
        Get the singleton instance of UpdateChecker.

        Args:
            config (Config | None): Optional Config instance to use.
            scheduler (Scheduler | None): Optional Scheduler instance to use.
            notify (EventBus | None): Optional EventBus instance to use.

        Returns:
            UpdateChecker: The singleton instance of UpdateChecker.

        """
        return UpdateChecker(config=config, scheduler=scheduler, notify=notify)

    def attach(self, _: web.Application) -> None:
        """
        Attach the UpdateChecker to the application.

        Args:
            _ (web.Application): The aiohttp web application instance.

        """
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

    async def on_shutdown(self, _: web.Application) -> None:
        """
        Handle application shutdown event.

        Args:
            _ (web.Application): The aiohttp web application instance.

        """
        if not self._job_id:
            return

        self._scheduler.remove(self._job_id)
        self._job_id = None
        LOG.debug("Stopped update check scheduled task.")

    def _schedule_check(self) -> None:
        """Schedule the update check task to run daily at 3 AM."""
        if not self._config.check_for_updates:
            LOG.debug("Update checking is disabled, skipping scheduling.")
            return

        # Run daily at 3 AM
        timer: str = "0 3 * * *"

        self._job_id = self._scheduler.add(
            timer=timer,
            func=lambda: asyncio.create_task(self.check_for_updates()),
            id="update_checker",
        )

        LOG.info(f"Scheduled update check to run daily at 3 AM (cron: {timer}).")

    async def check_for_updates(self) -> tuple[str, str | None]:
        """
        Check for updates from GitHub releases.
        Updates config.new_version if a newer version is available.
        Stops the scheduled task if an update is found.

        Returns:
            tuple[str, str | None]: (status, new_version)
                status: "disabled", "error", "up_to_date", or "update_available"
                new_version: The new version tag if available, None otherwise

        """
        if not self._config.check_for_updates:
            LOG.debug("Update checking is disabled, skipping check.")
            return ("disabled", None)

        # Check cache
        cached = await self._cache.aget(self.CACHE_KEY)
        if cached:
            ttl = await self._cache.attl(self.CACHE_KEY)
            LOG.debug(f"Returning cached result (TTL: {ttl:.0f}s)")
            return cached

        try:
            LOG.info("Checking for application updates...")

            current_version: str = APP_VERSION.lstrip("v")

            async with async_client(timeout=10.0) as client:
                response = await client.get(
                    self.GITHUB_API_URL,
                    headers={"Accept": "application/vnd.github+json"},
                )

                if 200 != response.status_code:
                    LOG.warning(f"Failed to check for updates: HTTP {response.status_code}")
                    return ("error", None)

                data: dict[str, Any] = response.json()

                latest_tag: str = data.get("tag_name", "").lstrip("v")
                if not latest_tag:
                    LOG.warning("No tag_name found in GitHub release data.")
                    return ("error", None)

                if self._compare_versions(current_version, latest_tag):
                    LOG.warning(f"Update available: {current_version} → {latest_tag}")
                    new_version_tag = data.get("tag_name", "")
                    self._config.new_version = new_version_tag
                    await self.on_shutdown(None)
                    result = ("update_available", new_version_tag)
                    await self._cache.aset(self.CACHE_KEY, result, self.CACHE_DURATION)
                    return result

                LOG.info("No updates available.")
                self._config.new_version = ""
                result = ("up_to_date", None)
                await self._cache.aset(self.CACHE_KEY, result, self.CACHE_DURATION)
                return result
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Error checking for updates: {e!s}")
            return ("error", None)

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
