"""Video entry processing."""

import logging
import time
from datetime import UTC, datetime, timedelta
from email.utils import formatdate
from typing import TYPE_CHECKING

from app.library.Events import Events
from app.library.ItemDTO import ItemDTO
from app.library.Utils import calc_download_path, extract_ytdlp_logs, get_extras, merge_dict, str_to_dt

from .core import Download

if TYPE_CHECKING:
    from app.library.ItemDTO import Item

    from .queue_manager import DownloadQueue

LOG: logging.Logger = logging.getLogger(__name__)


async def add_video(queue: "DownloadQueue", entry: dict, item: "Item", logs: list[str] | None = None) -> dict[str, str]:
    """
    Process and add a video entry to the queue.

    Args:
        queue: DownloadQueue instance
        entry: Video entry dict from yt-dlp
        item: Item configuration
        logs: Optional yt-dlp logs

    Returns:
        dict: Status dict with "status" and optional "msg" keys

    """
    if not logs:
        logs: list[str] = []

    options: dict = {}
    error: str | None = None
    live_in: str | None = None
    is_premiere: bool = bool(entry.get("is_premiere", False))

    release_in: str | None = None
    if entry.get("release_timestamp"):
        release_in = formatdate(entry.get("release_timestamp"), usegmt=True)
        item.extras["release_in"] = release_in

    # check if the video is live stream.
    if "is_upcoming" == entry.get("live_status"):
        if release_in:
            live_in = release_in
            item.extras["live_in"] = live_in
        else:
            error = f"No start time is set for {'premiere' if is_premiere else 'live stream'}."
    else:
        error = entry.get("msg")

    LOG.debug(f"Entry id '{entry.get('id')}' url '{entry.get('webpage_url')} - {entry.get('url')}'.")

    try:
        _item: Download = await queue.done.get(key=entry.get("id"), url=entry.get("webpage_url") or entry.get("url"))
        err_msg: str = f"Removing {_item.info.name()} from history list."
        LOG.warning(err_msg)
        await queue.clear([_item.info._id], remove_file=False)
    except KeyError:
        pass

    try:
        _item: Download = await queue.queue.get(
            key=str(entry.get("id")), url=str(entry.get("webpage_url") or entry.get("url"))
        )
        err_msg: str = f"Item {_item.info.name()} is already in download queue."
        LOG.info(err_msg)
        return {"status": "error", "msg": err_msg}
    except KeyError:
        pass

    live_status: list = ["is_live", "is_upcoming"]
    is_live = bool(entry.get("is_live") or live_in or entry.get("live_status") in live_status)

    try:
        download_dir: str = calc_download_path(base_path=queue.config.download_path, folder=item.folder)
    except Exception as e:
        LOG.exception(e)
        return {"status": "error", "msg": str(e)}

    for field in ("uploader", "channel", "thumbnail"):
        if entry.get(field):
            item.extras[field] = entry.get(field)

    for key in entry:
        if isinstance(key, str) and key.startswith("playlist") and entry.get(key):
            item.extras[key] = entry.get(key)

    item.extras["duration"] = entry.get("duration", item.extras.get("duration"))

    if not item.extras.get("live_in") and live_in:
        item.extras["live_in"] = live_in

    if not item.extras.get("is_premiere") and is_premiere:
        item.extras["is_premiere"] = is_premiere

    dl = ItemDTO(
        id=str(entry.get("id")),
        title=str(entry.get("title")),
        description=str(entry.get("description", "")),
        url=str(entry.get("webpage_url") or entry.get("url")),
        preset=item.preset,
        folder=item.folder,
        download_dir=download_dir,
        temp_dir=queue.config.temp_path,
        cookies=item.cookies,
        template=item.template if item.template else queue.config.output_template,
        template_chapter=queue.config.output_template_chapter,
        datetime=formatdate(time.time()),
        error=error,
        is_live=is_live,
        live_in=live_in if live_in else item.extras.get("live_in", None),
        options=options,
        cli=item.cli,
        auto_start=item.auto_start,
        extras=merge_dict(item.extras, get_extras(entry)),
    )

    try:
        dlInfo: Download = Download(info=dl, info_dict=entry if item.auto_start else None, logs=logs)
        nEvent: str | None = None
        nTitle: str | None = None
        nMessage: str | None = None
        nStore: str = "queue"
        hasFormats: bool = len(entry.get("formats", [])) > 0 or entry.get("url")

        text_logs: str = ""
        if filtered_logs := extract_ytdlp_logs(logs):
            text_logs = " " + ", ".join(filtered_logs)

        if "is_upcoming" == entry.get("live_status"):
            nEvent = Events.ITEM_MOVED
            nStore = "history"
            nTitle = "Upcoming Premiere" if is_premiere else "Upcoming Live Stream"
            nMessage = f"{'Premiere video' if is_premiere else 'Stream'} '{dlInfo.info.title}' is not available yet. {text_logs}"

            dlInfo.info.status = "not_live"
            dlInfo.info.msg = nMessage.replace(f" '{dlInfo.info.title}'", "")
            queue._notify.emit(
                Events.LOG_INFO,
                data={"preset": dlInfo.info.preset, "lowPriority": True},
                title=nTitle,
                message=nMessage,
            )

            itemDownload: Download = await queue.done.put(dlInfo)
        elif not hasFormats:
            ava: str = entry.get("availability", "public")
            nTitle = "Download Error"
            nMessage: str = f"No formats for '{dl.title}'."
            nEvent = Events.ITEM_MOVED
            nStore = "history"

            if ava and ava not in ("public",):
                nMessage += f" Availability is set for '{ava}'."

            dlInfo.info.error = nMessage.replace(f" for '{dl.title}'.", ".") + text_logs
            dlInfo.info.status = "error"
            itemDownload = await queue.done.put(dlInfo)

            queue._notify.emit(
                Events.LOG_WARNING,
                data={"preset": dlInfo.info.preset, "logs": text_logs},
                title=nTitle,
                message=nMessage,
            )
        elif is_premiere and queue.config.prevent_live_premiere:
            nStore = "history"
            nTitle = "Premiere Video"
            dlInfo.info.error = "Premiering right now."

            _requeue = True
            if release_in:
                try:
                    starts_in: datetime = str_to_dt(release_in)
                    starts_in: datetime = (
                        starts_in.replace(tzinfo=UTC) if starts_in.tzinfo is None else starts_in.astimezone(UTC)
                    )
                    starts_in = starts_in + timedelta(minutes=5, seconds=dl.extras.get("duration", 0))
                    dlInfo.info.error += f" Download will start at {starts_in.astimezone().isoformat()}."
                    _requeue = False
                except Exception as e:
                    LOG.error(f"Failed to parse live_in date '{release_in}'. {e!s}")
                    dlInfo.info.error += f" Failed to parse live_in date '{release_in}'."
            else:
                dlInfo.info.error += f" Delaying download by '{300 + dl.extras.get('duration', 0)}' seconds."

            nMessage = f"'{dlInfo.info.title}': '{dlInfo.info.error.strip()}'."

            if _requeue:
                nEvent = Events.ITEM_ADDED
                itemDownload = await queue.queue.put(dlInfo)
                if item.auto_start:
                    queue.pool.trigger_download()
            else:
                dlInfo.info.status = "not_live"
                itemDownload = await queue.done.put(dlInfo)
                nStore = "history"
                nEvent = Events.ITEM_MOVED
                nTitle = "Premiering right now"
                queue._notify.emit(Events.LOG_INFO, data={"preset": dlInfo.info.preset}, title=nTitle, message=nMessage)
        else:
            nEvent = Events.ITEM_ADDED
            nTitle = "Item Added"
            nMessage = f"Item '{dlInfo.info.title}' has been added to the download queue."
            itemDownload = await queue.queue.put(dlInfo)
            if item.auto_start:
                queue.pool.trigger_download()
            else:
                LOG.debug(f"Item {itemDownload.info.name()} is not set to auto-start.")

        queue._notify.emit(
            nEvent,
            data={"to": nStore, "preset": itemDownload.info.preset, "item": itemDownload.info}
            if Events.ITEM_MOVED == nEvent
            else itemDownload.info,
            title=nTitle,
            message=nMessage,
        )

        return {"status": "ok"}
    except Exception as e:
        LOG.exception(e)
        LOG.error(f"Failed to download item. '{e!s}'")
        return {"status": "error", "msg": str(e)}
