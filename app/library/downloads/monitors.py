"""Queue monitoring functions."""

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.library.ag_utils import ag
from app.library.Events import Events
from app.library.ItemDTO import Item, ItemDTO
from app.library.Utils import dt_delta, str_to_dt

if TYPE_CHECKING:
    from .queue_manager import DownloadQueue

LOG: logging.Logger = logging.getLogger("downloads.monitors")


async def check_for_stale(queue: "DownloadQueue") -> None:
    """
    Monitor pool for stale downloads and cancel them if needed.

    Iterates through active queue items and cancels any that have become stale
    (not making progress for an extended period).

    Args:
        queue: DownloadQueue instance

    """
    if queue.is_paused() or queue.queue.empty():
        return

    for _id, item in list(queue.queue.items()):
        item_ref = f"{_id=} {item.info.id=} {item.info.title=}"
        if not item.is_stale():
            continue

        try:
            LOG.warning(f"Cancelling staled item '{item_ref}' from download queue.")
            await queue.cancel([_id])
        except Exception as e:
            LOG.error(f"Failed to cancel staled item '{item_ref}'. {e!s}")
            LOG.exception(e)


async def check_live(queue: "DownloadQueue") -> None:
    """
    Monitor the queue for items marked as live events and queue them when time is reached.

    Checks history for live streams/premieres that are scheduled to start and
    re-adds them to the download queue when their start time arrives.

    Args:
        queue: DownloadQueue instance

    """
    if queue.is_paused() or queue.done.empty():
        return

    if queue.config.debug:
        LOG.debug("Checking history queue for queued live stream links.")

    time_now = datetime.now(tz=UTC)

    status: list[str] = ["not_live", "is_upcoming", "is_live"]

    for id, item in list(queue.done.items()):
        if item.info.status not in status:
            continue

        item_ref: str = f"{id=} {item.info.id=} {item.info.title=}"
        if not item.is_live:
            LOG.debug(f"Item '{item_ref}' is not a live stream.")
            continue

        duration: int | None = item.info.extras.get("duration", None)
        is_premiere: bool = item.info.extras.get("is_premiere", False)

        live_in: str | None = item.info.live_in or ag(item.info.extras, ["live_in", "release_in"], None)
        if not live_in:
            LOG.debug(
                f"Item '{item_ref}' marked as {'premiere video' if is_premiere else 'live stream'}, but no date is set."
            )
            continue

        starts_in = str_to_dt(live_in)
        starts_in = starts_in.replace(tzinfo=UTC) if starts_in.tzinfo is None else starts_in.astimezone(UTC)

        if time_now < (starts_in + timedelta(minutes=1)):
            LOG.debug(f"Item '{item_ref}' is not yet live. will start at '{dt_delta(starts_in - time_now)}'.")
            continue

        if queue.config.prevent_live_premiere and is_premiere and duration:
            buffer_time = queue.config.live_premiere_buffer if queue.config.live_premiere_buffer >= 0 else 5
            premiere_ends: datetime = starts_in + timedelta(minutes=buffer_time, seconds=duration)
            if time_now < premiere_ends:
                LOG.debug(
                    f"Item '{item_ref}' is premiering, download will start in '{(starts_in + timedelta(minutes=buffer_time, seconds=duration)).astimezone().isoformat()}'"
                )
                continue

        LOG.info(f"Retrying item '{item_ref} {item.info.extras=}' for download.")

        try:
            await queue.clear([item.info._id], remove_file=False)
        except Exception as e:
            LOG.error(f"Failed to clear item '{item_ref}'. {e!s}")
            continue

        try:
            await queue.add(
                item=Item(
                    url=item.info.url,
                    preset=item.info.preset,
                    folder=item.info.folder,
                    cookies=item.info.cookies,
                    template=item.info.template,
                    cli=item.info.cli,
                    extras=item.info.extras,
                )
            )
        except Exception as e:
            await queue.done.put(item)
            LOG.exception(e)
            LOG.error(f"Failed to retry item '{item_ref}'. {e!s}")


async def delete_old_history(queue: "DownloadQueue") -> None:
    """
    Automatically delete old download history based on user specified days.

    Removes finished downloads from history that are older than the configured
    auto_clear_history_days setting. 0 or negative value disables this feature.

    Args:
        queue: DownloadQueue instance

    """
    if queue.config.auto_clear_history_days < 0 or queue.is_paused() or queue.done.empty():
        return

    cutoff_date: datetime = datetime.now(UTC) - timedelta(days=queue.config.auto_clear_history_days)
    items_to_delete: list[tuple[str, ItemDTO]] = []

    for key, download in queue.done.items():
        info: ItemDTO = download.info
        if not info or not info.timestamp:
            continue

        if "finished" != info.status or not info.filename:
            continue

        try:
            timestamp_seconds: float = info.timestamp / 1e9
            item_datetime: datetime = datetime.fromtimestamp(timestamp_seconds, tz=UTC)
            if item_datetime < cutoff_date:
                items_to_delete.append((key, info))
        except (OSError, ValueError, OverflowError) as e:
            LOG.error(f"Failed to parse timestamp '{info.timestamp}' for item '{info.title}': {e}")

    titles: list[str] = []
    for key, info in items_to_delete:
        item_name: str = info.title or info.id or info._id
        queue._notify.emit(
            Events.ITEM_DELETED,
            data=info,
            title="Download Cleared",
            message=f"'{item_name}' record removed from history.",
        )
        titles.append(item_name)
        await queue.done.delete(key)

    if titles:
        LOG.info(f"Automatically cleared '{', '.join(titles)}' from download history due to age.")
