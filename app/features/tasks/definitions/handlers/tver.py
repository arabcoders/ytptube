import logging
import re

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskItem, TaskResult
from app.library.Utils import get_archive_id

from ._base_handler import BaseHandler

LOG: logging.Logger = logging.getLogger("handlers.tver")


class TverHandler(BaseHandler):
    SERIES_API: str = "https://platform-api.tver.jp/service/api/v1/callSeriesEpisodes/{id}"
    SESSION_API: str = "https://platform-api.tver.jp/v2/api/platform_users/browser/create"
    HEADERS: dict[str, str] = {
        "x-tver-platform-type": "web",
        "Origin": "https://tver.jp",
        "Referer": "https://tver.jp/",
    }

    RX: re.Pattern[str] = re.compile(r"^https?:\/\/(?:www\.|m\.)?tver\.jp\/series\/(?P<id>sr[a-z0-9_]+)$")

    @staticmethod
    async def can_handle(task: HandleTask) -> bool:
        LOG.debug(f"Checking if task '{task.name}' is using parsable Tver series URL: {task.url}")
        return TverHandler.parse(task.url) is not None

    @staticmethod
    async def _get_session_tokens() -> dict[str, str] | None:
        """
        Create a session and retrieve platform_uid and platform_token.

        Returns:
            dict[str, str] | None: Dictionary with platform_uid and platform_token, or None on failure.

        """
        try:
            response = await TverHandler.request(
                url=TverHandler.SESSION_API,
                headers=TverHandler.HEADERS,
                method="POST",
                data={"device_type": "pc"},
            )
            response.raise_for_status()

            data = response.json()
            platform_uid = data.get("result", {}).get("platform_uid")
            platform_token = data.get("result", {}).get("platform_token")

            if not platform_uid or not platform_token:
                LOG.warning("Failed to extract platform_uid and platform_token from session response.")
                return None

            return {"platform_uid": platform_uid, "platform_token": platform_token}
        except Exception as exc:
            LOG.warning(f"Failed to create tver session: {exc}")
            return None

    @staticmethod
    async def _collect_feed(
        task: HandleTask,
        params: dict,
        series_id: str,
    ) -> tuple[str, list[dict[str, str]], bool]:
        """
        Fetch episodes from tver series API.

        Args:
            task (Task): The task containing the tver series URL.
            params (dict): The ytdlp options.
            series_id (str): The tver series ID.

        Returns:
            tuple[str, list[dict[str, str]], bool]: The feed URL, list of episodes, and whether items were found.

        """
        tokens = await TverHandler._get_session_tokens()
        if not tokens:
            msg = "Could not obtain tver session tokens"
            raise RuntimeError(msg)

        feed_url = TverHandler.SERIES_API.format(id=series_id)

        LOG.debug(f"Fetching '{task.name}' episodes from tver series {series_id}.")

        response = await TverHandler.request(
            url=feed_url,
            headers=TverHandler.HEADERS,
            ytdlp_opts=params,
            params={
                "platform_uid": tokens["platform_uid"],
                "platform_token": tokens["platform_token"],
            },
        )
        response.raise_for_status()

        data = response.json()

        items: list[dict[str, str]] = []
        has_items = False

        # Parse episodes from result.contents[0].contents
        try:
            contents = data.get("result", {}).get("contents", [])
            if not contents:
                LOG.warning(f"No contents found in tver series response for '{task.name}'.")
                return feed_url, items, has_items

            season_block = contents[0] if contents else {}
            episodes = season_block.get("contents", [])

            for episode_data in episodes:
                if "episode" != episode_data.get("type"):
                    continue

                content = episode_data.get("content", {})
                episode_id = content.pop("id")
                if not episode_id:
                    LOG.warning(f"Episode missing ID in '{task.name}' feed. Skipping.")
                    continue

                url = f"https://tver.jp/episodes/{episode_id}"

                title = content.pop("title", "")

                id_dict = get_archive_id(url)
                archive_id = id_dict.get("archive_id")
                if not archive_id:
                    LOG.warning(
                        f"Could not compute archive ID for episode '{episode_id}' in '{task.name}' feed. Skipping."
                    )
                    continue

                has_items = True
                items.append(
                    {"id": episode_id, "url": url, "title": title, "archive_id": archive_id, "metadata": content}
                )

        except Exception as exc:
            LOG.warning(f"Error parsing tver episodes for '{task.name}': {exc}")

        return feed_url, items, has_items

    @staticmethod
    async def extract(task: HandleTask) -> TaskResult | TaskFailure:
        series_id: str | None = TverHandler.parse(task.url)
        if not series_id:
            return TaskFailure(message="Unrecognized Tver series URL.")

        params: dict = task.get_ytdlp_opts().get_all()

        try:
            feed_url, items, has_items = await TverHandler._collect_feed(task, params, series_id)
        except Exception as exc:
            LOG.exception(exc)
            return TaskFailure(message="Failed to fetch Tver feed.", error=str(exc))

        task_items: list[TaskItem] = []

        for entry in items:
            if not (url := entry.get("url")):
                continue

            archive_id: str = entry.get("archive_id")
            task_items.append(
                TaskItem(url=url, title=entry.get("title"), archive_id=archive_id, metadata=entry.get("metadata", {}))
            )

        return TaskResult(items=task_items, metadata={"feed_url": feed_url, "has_entries": has_items})

    @staticmethod
    def parse(url: str) -> str | None:
        """
        Parse URL to extract series ID.

        Args:
            url (str): The url to check.

        Returns:
            str | None: The parsed ID if successful, None otherwise.

        """
        match: re.Match[str] | None = TverHandler.RX.match(url)
        return match.group("id") if match else None

    @staticmethod
    def tests() -> list[tuple[str, bool]]:
        """
        Test cases for the URL parser.

        Returns:
            list[tuple[str, bool]]: A list of tuples containing the URL and expected result.

        """
        return [
            ("https://tver.jp/series/sr1jg44pbb", True),
            ("https://www.tver.jp/series/sr1jg44pbb", True),
            ("https://m.tver.jp/series/sr_test_id", True),
            ("http://tver.jp/series/sr123abc456", True),
            ("https://tver.jp/videos/sr123abc456", False),
            ("https://youtube.com/watch?v=123", False),
        ]
