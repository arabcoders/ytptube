"""Queue monitoring functions."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from app.library.ag_utils import ag
from app.library.Events import Events
from app.library.ItemDTO import Item, ItemDTO
from app.library.log import get_logger
from app.library.Utils import dt_delta, str_to_dt

if TYPE_CHECKING:
    from .queue_manager import DownloadQueue

LOG = get_logger()


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
        if not item.is_stale():
            continue

        try:
            LOG.warning(
                f"Cancelling stale download '{item.info.title}' from queue.",
                extra={
                    "download": {
                        "download_id": _id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "url": item.info.url,
                        "status": item.info.status,
                    }
                },
            )
            await queue.cancel([_id])
        except Exception as e:
            LOG.exception(
                f"Failed to cancel stale download '{item.info.title}'.",
                extra={
                    "download": {
                        "download_id": _id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "url": item.info.url,
                        "status": item.info.status,
                        "exception_type": type(e).__name__,
                    }
                },
            )


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

        if not item.is_live:
            LOG.debug(
                "Skipping history item '%s' because it is not a live stream.",
                item.info.title,
                extra={
                    "download": {
                        "download_id": id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "status": item.info.status,
                    }
                },
            )
            continue

        duration: int | None = item.info.extras.get("duration", None)
        is_premiere: bool = item.info.extras.get("is_premiere", False)

        live_in: str | None = item.info.live_in or ag(item.info.extras, ["live_in", "release_in"], None)
        if not live_in:
            LOG.debug(
                "Skipping %s '%s' because no start time is set.",
                "premiere video" if is_premiere else "live stream",
                item.info.title,
                extra={
                    "download": {
                        "download_id": id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "is_premiere": is_premiere,
                    }
                },
            )
            continue

        starts_in = str_to_dt(live_in)
        starts_in = starts_in.replace(tzinfo=UTC) if starts_in.tzinfo is None else starts_in.astimezone(UTC)

        if time_now < (starts_in + timedelta(minutes=1)):
            starts_in_text = dt_delta(starts_in - time_now)
            LOG.debug(
                "Live item '%s' is not ready yet; starts in %s.",
                item.info.title,
                starts_in_text,
                extra={
                    "download": {
                        "download_id": id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "live_in": live_in,
                        "starts_in": starts_in_text,
                    }
                },
            )
            continue

        if queue.config.prevent_live_premiere and is_premiere and duration:
            buffer_time = queue.config.live_premiere_buffer if queue.config.live_premiere_buffer >= 0 else 5
            premiere_ends: datetime = starts_in + timedelta(minutes=buffer_time, seconds=duration)
            if time_now < premiere_ends:
                start_after = premiere_ends.astimezone().isoformat()
                LOG.debug(
                    "Premiere '%s' is still running; download will start after '%s'.",
                    item.info.title,
                    start_after,
                    extra={
                        "download": {
                            "download_id": id,
                            "item_id": item.info.id,
                            "title": item.info.title,
                            "is_premiere": is_premiere,
                            "start_after": start_after,
                        }
                    },
                )
                continue

        LOG.info(
            f"Retrying live download '{item.info.title}' from '{item.info.url}'.",
            extra={
                "download": {
                    "download_id": id,
                    "item_id": item.info.id,
                    "title": item.info.title,
                    "url": item.info.url,
                    "preset": item.info.preset,
                    "live_in": live_in,
                    "is_premiere": is_premiere,
                }
            },
        )

        try:
            await queue.clear([item.info._id], remove_file=False)
        except Exception as e:
            LOG.exception(
                "Failed to clear live download '%s' before retry.",
                item.info.title,
                extra={
                    "download": {
                        "download_id": id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "url": item.info.url,
                        "preset": item.info.preset,
                        "exception_type": type(e).__name__,
                    }
                },
            )
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
            LOG.exception(
                "Failed to retry live download '%s' from '%s'.",
                item.info.title,
                item.info.url,
                extra={
                    "download": {
                        "download_id": id,
                        "item_id": item.info.id,
                        "title": item.info.title,
                        "url": item.info.url,
                        "preset": item.info.preset,
                        "exception_type": type(e).__name__,
                    }
                },
            )


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
            LOG.exception(
                "Failed to parse timestamp for history item '%s'.",
                info.title,
                extra={
                    "download": {
                        "download_id": key,
                        "item_id": info.id,
                        "title": info.title,
                        "timestamp": info.timestamp,
                        "exception_type": type(e).__name__,
                    }
                },
            )

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
        LOG.info(
            "Automatically cleared %s old history item(s), including '%s'.",
            len(titles),
            titles[0],
            extra={"deleted_count": len(titles), "titles": titles},
        )


async def cleanup_thumbnails(queue: "DownloadQueue") -> None:
    """
    Remove cached generated thumbnails whose history item no longer exists.

    Args:
        queue: DownloadQueue instance.

    """
    if queue.config.thumb_sidecar:
        return

    cache_root = Path(queue.config.temp_path) / "thumbnails"
    if not cache_root.exists() or not cache_root.is_dir():
        return

    removed = 0
    for thumb in cache_root.glob("*.jpg"):
        if not thumb.is_file():
            continue

        if await queue.done.get_by_id(thumb.stem):
            continue

        try:
            thumb.unlink(missing_ok=True)
            removed += 1
        except OSError as exc:
            LOG.exception(
                "Failed to remove orphaned thumbnail '%s'.",
                thumb,
                extra={"file_path": str(thumb), "exception_type": type(exc).__name__},
            )

    if removed > 0:
        LOG.info("Removed %s orphaned cached thumbnail(s).", removed, extra={"removed_count": removed})
