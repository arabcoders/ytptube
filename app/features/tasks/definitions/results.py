from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.features.tasks.schemas import Task as TaskSchema
from app.features.ytdlp.ytdlp_opts import YTDLPOpts

from .utils import split_inspect_metadata


class HandleTask(TaskSchema):
    def get_ytdlp_opts(self) -> YTDLPOpts:
        """
        Get the yt-dlp options for the task.

        Returns:
            YTDLPOpts: The yt-dlp options.

        """
        from app.features.ytdlp.ytdlp_opts import YTDLPOpts

        params: YTDLPOpts = YTDLPOpts.get_instance()

        if self.preset:
            params = params.preset(name=self.preset)

        if self.cli:
            params = params.add_cli(self.cli, from_user=True)

        if self.template:
            params = params.add({"outtmpl": {"default": self.template}}, from_user=False)

        return params

    async def mark(self) -> tuple[bool, str]:
        """
        Mark the task's items as downloaded in the archive file.

        Returns:
            tuple[bool, str]: A tuple indicating success and a message.

        """
        from app.library.Utils import archive_add

        ret: tuple[bool, str] | dict[str, Any] = await self._mark_logic()
        if isinstance(ret, tuple):
            return ret

        archive_file: Path = ret.get("file")
        items: set[str] = ret.get("items", set())

        if len(items) < 1 or not archive_add(archive_file, list(items)):
            return (True, "No new items to mark as downloaded.")

        return (True, f"Task '{self.name}' items marked as downloaded.")

    async def unmark(self) -> tuple[bool, str]:
        """
        Unmark the task's items from the archive file.

        Returns:
            tuple[bool, str]: A tuple indicating success and a message.

        """
        from app.library.Utils import archive_delete

        ret: tuple[bool, str] | dict[str, Any] = await self._mark_logic()
        if isinstance(ret, tuple):
            return ret

        archive_file: Path = ret.get("file")
        items: set[str] = ret.get("items", set())

        if len(items) < 1 or not archive_delete(archive_file, list(items)):
            return (True, "No items to remove from archive file.")

        return (True, f"Removed '{self.name}' items from archive file.")

    async def fetch_metadata(self, full: bool = False) -> tuple[dict[str, Any] | None, bool, str]:
        """
        Fetch metadata for the task's URL.

        Args:
            full (bool): Whether to fetch full metadata including all entries for playlists.

        Returns:
            tuple[dict[str, Any]|None, bool, str]: A tuple containing the metadata (or None on failure), a boolean
            indicating if the operation was successful, and a message.

        """
        from app.features.ytdlp.ytdlp import fetch_info

        if not self.url:
            return ({}, False, "No URL found in task parameters.")

        params = self.get_ytdlp_opts()
        if not full:
            params.add_cli("-I0", from_user=False)

        params_dict = params.get_all()

        (ie_info, _) = await fetch_info(
            params_dict,
            self.url,
            no_archive=True,
            follow_redirect=False,
            sanitize_info=True,
        )

        if not ie_info or not isinstance(ie_info, dict):
            return ({}, False, "Failed to extract information from URL.")

        return (ie_info, True, "")

    async def _mark_logic(self) -> tuple[bool, str] | dict[str, Any]:
        """
        Internal logic for marking/un-marking items.

        Returns:
            tuple[bool, str] | dict[str, Any]: Either an error tuple or a dict with 'file' and 'items' keys.

        """
        from app.features.ytdlp.ytdlp import fetch_info

        if not self.url:
            return (False, "No URL found in task parameters.")

        params: dict = self.get_ytdlp_opts().get_all()
        if not (archive_file := params.get("download_archive")):
            return (False, "No archive file found.")

        archive_file: Path = Path(archive_file)

        (ie_info, _) = await fetch_info(params, self.url, no_archive=True, follow_redirect=True)
        if not ie_info or not isinstance(ie_info, dict):
            return (False, "Failed to extract information from URL.")

        if "playlist" != ie_info.get("_type"):
            return (False, "Expected a playlist type from extract_info.")

        items: set[str] = set()

        def _process(item: dict):
            for entry in item.get("entries", []):
                if not isinstance(entry, dict):
                    continue

                if "playlist" == entry.get("_type"):
                    _process(entry)
                    continue

                if entry.get("_type") not in ("video", "url"):
                    continue

                if not entry.get("id") or not entry.get("ie_key"):
                    continue

                archive_id: str = f"{entry.get('ie_key', '').lower()} {entry.get('id')}"

                items.add(archive_id)

        _process(ie_info)

        return {"file": archive_file, "items": items}


@dataclass(slots=True)
class TaskItem:
    """Represents a single item in a task result."""

    url: str
    "The URL of the item."
    title: str | None = None
    "The title of the item."
    archive_id: str | None = None
    "The archive ID of the item."
    metadata: dict[str, Any] = field(default_factory=dict)
    "Additional metadata related to the item."


@dataclass(slots=True)
class TaskResult:
    """Represents a successful task handler execution result."""

    items: list[TaskItem] = field(default_factory=list)
    "The list of items."
    metadata: dict[str, Any] = field(default_factory=dict)
    "Additional metadata related to the result."

    def serialize(self) -> dict[str, Any]:
        primary, extra = split_inspect_metadata(self.metadata)
        payload: dict[str, Any] = {**primary, "items": [asdict(item) for item in self.items]}

        if extra:
            payload["metadata"] = extra

        return payload


@dataclass(slots=True)
class TaskFailure:
    """Represents a failed task handler execution result."""

    message: str
    "A human-readable message describing the failure."
    error: str | None = None
    "An optional error code or string."
    metadata: dict[str, Any] = field(default_factory=dict)
    "Additional metadata related to the failure."

    def serialize(self) -> dict[str, Any]:
        primary, extra = split_inspect_metadata(self.metadata)
        payload: dict[str, Any] = dict(primary)

        if self.error:
            payload["error"] = self.error

        if self.message and (not self.error or self.message != self.error):
            payload["message"] = self.message

        if extra:
            payload["metadata"] = extra

        return payload
