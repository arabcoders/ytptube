"""Playlist processing."""

from typing import TYPE_CHECKING, Any

from app.features.ytdlp.utils import ytdlp_reject
from app.library.log import get_logger
from app.library.Utils import merge_dict

if TYPE_CHECKING:
    from app.library.ItemDTO import Item

    from .queue_manager import DownloadQueue

LOG = get_logger()


async def process_playlist(
    queue: "DownloadQueue", entry: dict, item: "Item", already=None, yt_params: dict | None = None
) -> dict[str, str]:
    """
    Process a playlist entry.

    Args:
        queue: DownloadQueue instance for accessing queue/config
        entry: Playlist entry dict from yt-dlp
        item: Item configuration
        already: Set of already processed IDs
        yt_params: yt-dlp parameters

    Returns:
        dict: Status dict with "status" and optional "msg" keys

    """
    if not yt_params:
        yt_params = {}

    entries = entry.get("entries", [])

    playlist_name: str = f"{entry.get('id')}: {entry.get('title')}"

    LOG.info(
        "Processing playlist '%s' with %s entrie(s).",
        playlist_name,
        len(entries),
        extra={
            "playlist_id": entry.get("id"),
            "playlist_title": entry.get("title"),
            "entry_count": len(entries),
            "preset": getattr(item, "preset", None),
        },
    )

    playlistCount = entry.get("playlist_count")
    playlistCount: int = int(playlistCount) if playlistCount else len(entries)

    playlist_keys: dict[str, Any] = {
        "playlist_count": playlistCount,
        "playlist": entry.get("title") or entry.get("id"),
        "playlist_id": entry.get("id"),
        "playlist_title": entry.get("title"),
        "playlist_uploader": entry.get("uploader"),
        "playlist_uploader_id": entry.get("uploader_id"),
        "playlist_channel": entry.get("channel"),
        "playlist_channel_id": entry.get("channel_id"),
        "playlist_webpage_url": entry.get("webpage_url"),
        "__last_playlist_index": playlistCount - 1,
        "n_entries": len(entries),
    }

    async def process_item(i: int, etr: dict) -> dict[str, str]:
        """Process a single playlist item."""
        item_name: str = (
            f"'{entry.get('title')}: {i}/{playlist_keys['n_entries']}' - '{etr.get('id')}: {etr.get('title')}'"
        )
        LOG.info(
            "Processing playlist item '%s'.",
            item_name,
            extra={
                "playlist_id": entry.get("id"),
                "playlist_title": entry.get("title"),
                "playlist_index": i,
                "entry_count": playlist_keys["n_entries"],
                "item_id": etr.get("id"),
                "title": etr.get("title"),
            },
        )

        _status, _msg = ytdlp_reject(entry=etr, yt_params=yt_params)
        if not _status:
            return {"status": "error", "msg": _msg}

        extras: dict[str, Any] = {
            **playlist_keys,
            "playlist_index": i,
            "playlist_index_number": i,
            "playlist_autonumber": i,
        }

        for property in ("id", "title", "uploader", "uploader_id"):
            if property in entry:
                extras[f"playlist_{property}"] = entry.get(property)

        extractor_key = entry.get("ie_key") or entry.get("extractor_key") or entry.get("extractor") or ""
        if "thumbnail" not in etr and "youtube" in str(extractor_key).lower():
            extras["thumbnail"] = "https://img.youtube.com/vi/{id}/maxresdefault.jpg".format(**etr)

        ignore_conditions = item.extras.get("ignore_conditions") if isinstance(item.extras, dict) else None
        if isinstance(ignore_conditions, list) and ignore_conditions:
            extras["ignore_conditions"] = ignore_conditions

        newItem: Item = item.new_with(url=etr.get("url") or etr.get("webpage_url"), extras=extras)

        if ("video" == etr.get("_type") and etr.get("url")) or (
            "formats" in etr and isinstance(etr["formats"], list) and len(etr["formats"]) > 0
        ):
            dct = merge_dict(merge_dict({"_type": "video"}, etr), entry)
            dct.pop("entries", None)
            return await queue.add(item=newItem, entry=dct, already=already)

        return await queue.add(item=newItem, already=already)

    max_downloads: int = -1
    ytdlp_opts: dict[str, Any] = item.get_ytdlp_opts().get_all()
    if isinstance(ytdlp_opts.get("max_downloads"), int):
        max_downloads = ytdlp_opts["max_downloads"]

    results: list[dict[str, str]] = []
    for i, etr in enumerate(entries, start=1):
        if max_downloads > 0 and i > max_downloads:
            break

        results.append(await process_item(i, etr))

    skipped = 0
    if max_downloads > 0 and len(entries) > max_downloads:
        skipped = len(entries) - max_downloads

    LOG.info(
        "Playlist '%s' processing completed with %s item(s).",
        playlist_name,
        len(results),
        extra={
            "playlist_id": entry.get("id"),
            "playlist_title": entry.get("title"),
            "processed_count": len(results),
            "entry_count": len(entries),
            "max_downloads": max_downloads,
            "skipped_count": skipped,
        },
    )

    if any("error" == res["status"] for res in results):
        return {
            "status": "error",
            "msg": ", ".join(res["msg"] for res in results if "error" == res["status"] and "msg" in res),
        }

    return {"status": "ok"}
