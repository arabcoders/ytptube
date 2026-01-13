"""
Item addition and entry routing.

This module handles the complete flow of adding items to the download queue:
- Preset and CLI validation
- Cookie file management
- Archive checking (early and post-extraction)
- Info extraction with yt-dlp
- Conditions matching and re-queuing
- Entry type routing (playlist, video, URL)
"""

import asyncio
import functools
import logging
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import yt_dlp.utils

from app.library.conditions import Conditions
from app.library.Events import Events
from app.library.ItemDTO import ItemDTO
from app.library.Presets import Presets
from app.library.Utils import (
    archive_add,
    archive_read,
    arg_converter,
    create_cookies_file,
    extract_info,
    get_extras,
    merge_dict,
    ytdlp_reject,
)

from .core import Download
from .playlist_processor import process_playlist
from .video_processor import add_video

if TYPE_CHECKING:
    from app.library.ItemDTO import Item
    from app.library.Presets import Preset

    from .queue_manager import DownloadQueue

LOG: logging.Logger = logging.getLogger(__name__)


async def add_item(
    queue: "DownloadQueue",
    entry: dict,
    item: "Item",
    already=None,
    logs: list | None = None,
    yt_params: dict | None = None,
) -> dict[str, str]:
    """
    Route an entry to the appropriate processor based on type.

    Args:
        queue: DownloadQueue instance
        entry: Entry dict from yt-dlp
        item: Item configuration
        already: Set of already processed URLs
        logs: yt-dlp logs
        yt_params: yt-dlp parameters

    Returns:
        dict: Status dict with "status" and optional "msg" keys

    """
    if not entry:
        return {"status": "error", "msg": "Invalid/empty data was given."}

    event_type = entry.get("_type", "video")

    if event_type.startswith("playlist"):
        return await process_playlist(queue=queue, entry=entry, item=item, already=already, yt_params=yt_params)

    if event_type.startswith("url"):
        return await add(queue=queue, item=item.new_with(url=entry.get("url")), already=already)

    if event_type.startswith("video"):
        return await add_video(queue=queue, entry=entry, item=item, logs=logs)

    return {"status": "error", "msg": f'Unsupported event type "{event_type}".'}


async def add(
    queue: "DownloadQueue", item: "Item", already: set | None = None, entry: dict | None = None
) -> dict[str, str]:
    """
    Add an item to the download queue.

    Args:
        queue: DownloadQueue instance
        item: Item to be added to the queue
        already: Set of already downloaded items
        entry: Entry associated with the item (if already extracted)

    Returns:
        dict[str, str]: Status dict with "status" and optional "msg" keys

    """
    _preset: Preset | None = Presets.get_instance().get(item.preset)

    if item.has_cli():
        try:
            arg_converter(args=item.cli, level=True)
        except Exception as e:
            LOG.error(f"Invalid command options for yt-dlp '{item.cli}'. {e!s}")
            return {"status": "error", "msg": f"Invalid command options for yt-dlp '{item.cli}'. {e!s}"}

    if _preset:
        if _preset.folder and not item.folder:
            item.folder = _preset.folder

        if _preset.template and not item.template:
            item.template = _preset.template

    yt_conf = {}
    cookie_file: Path = Path(queue.config.temp_path) / f"c_{uuid.uuid4().hex}.txt"

    LOG.info(f"Adding '{item!r}'.")

    already = set() if already is None else already

    if item.url in already:
        LOG.warning(f"Recursion detected with url '{item.url}' skipping.")
        return {"status": "ok"}

    already.add(item.url)

    try:
        logs: list = []

        yt_conf: dict = {
            "callback": {
                "func": lambda _, msg: logs.append(msg),
                "level": logging.WARNING,
                "name": "callback-logger",
            },
            **item.get_ytdlp_opts().get_all(),
        }

        if yt_conf.get("external_downloader"):
            LOG.warning(f"Using external downloader '{yt_conf.get('external_downloader')}' for '{item.url}'.")
            item.extras.update({"external_downloader": True})

        archive_id: str | None = item.get_archive_id()

        # Early archive check to avoid unnecessary extraction calls
        # This sometimes can be different from the final extracted ID, so we need to verify again after extraction.
        if archive_id and item.is_archived():
            store_type, dlInfo = await queue.get_item(archive_id=archive_id)
            if not store_type and not queue.config.ignore_archived_items:
                dlInfo = Download(
                    info=ItemDTO(
                        id=archive_id.split()[1],
                        title=archive_id,
                        url=item.url,
                        preset=item.preset,
                        folder=item.folder,
                        status="skip",
                        cookies=item.cookies,
                        template=item.template,
                        msg="URL is already downloaded.",
                        extras=item.extras,
                    )
                )

                if archive_file := dlInfo.info.get_ytdlp_opts().get_all().get("download_archive"):
                    dlInfo.info.msg += f" Found in archive '{archive_file}'."

                await queue.done.put(dlInfo)

                queue._notify.emit(
                    Events.ITEM_MOVED,
                    data={"to": "history", "preset": dlInfo.info.preset, "item": dlInfo.info},
                    title="Download History Update",
                    message=f"Download history updated with '{item.url}'.",
                )
                return {"status": "ok"}

            message: str = f"The URL '{item.url}':'{archive_id}' is already downloaded and recorded in archive."
            LOG.warning(message)
            queue._notify.emit(
                Events.LOG_INFO, data={"preset": item.preset}, title="Already Downloaded", message=message
            )
            return {"status": "error", "msg": message, "hidden": True}

        started: float = time.perf_counter()

        if item.cookies:
            try:
                yt_conf["cookiefile"] = str(create_cookies_file(item.cookies, cookie_file))
            except Exception as e:
                msg = f"Failed to create cookie file for '{item.url}'. '{e!s}'."
                LOG.error(msg)
                return {"status": "error", "msg": msg}

        LOG.info(f"Extracting '{item.url}'{' with cookies' if yt_conf.get('cookiefile') else ''}.")

        if not entry:
            entry: dict | None = await asyncio.wait_for(
                fut=asyncio.get_running_loop().run_in_executor(
                    None,
                    functools.partial(
                        extract_info,
                        config=yt_conf,
                        url=item.url,
                        debug=bool(queue.config.ytdlp_debug),
                        no_archive=False,
                        follow_redirect=True,
                    ),
                ),
                timeout=queue.config.extract_info_timeout,
            )

        if not entry:
            LOG.error(f"Unable to extract info for '{item.url}'. Logs: {logs}")
            return {"status": "error", "msg": "Unable to extract info." + "\n".join(logs)}

        # Sometimes playlists or extractor returns different ID than what we get from the make_archive_id()
        # So, we need to re-check the archive after extraction to be sure the item was not downloaded.
        # This also apply to old archive IDs that might have been used before.
        if _archive_file := item.get_archive_file():
            extra_ids: list[str] = []

            if entry.get("_old_archive_ids") and isinstance(entry.get("_old_archive_ids"), list):
                extra_ids.extend(entry.get("_old_archive_ids", []))

            new_archive_id: str | None = None

            if entry.get("extractor_key") and entry.get("id"):
                new_archive_id: str = f"{entry.get('extractor_key').lower()} {entry.get('id')}"
                if new_archive_id != archive_id:
                    extra_ids.append(new_archive_id)

            if len(extra_ids) > 0:
                archive_ids: list[str] = archive_read(_archive_file, extra_ids)
                if len(archive_ids) > 0:
                    store_type = None
                    for n in archive_ids:
                        store_type, dlInfo = await queue.get_item(archive_id=n)
                        if store_type:
                            break

                    if not store_type and not queue.config.ignore_archived_items:
                        new_archive_id = new_archive_id or extra_ids.pop(0)
                        dlInfo = Download(
                            info=ItemDTO(
                                id=new_archive_id.split()[1],
                                title=new_archive_id,
                                url=entry.get("url") or entry.get("webpage_url") or item.url,
                                preset=item.preset,
                                folder=item.folder,
                                status="skip",
                                cookies=item.cookies,
                                template=item.template,
                                msg="URL is already downloaded.",
                                extras=merge_dict(item.extras, get_extras(entry)),
                            )
                        )

                        dlInfo.info.msg += f" Found in archive '{_archive_file}'."
                        await queue.done.put(dlInfo)

                        queue._notify.emit(
                            Events.ITEM_MOVED,
                            data={"to": "history", "preset": dlInfo.info.preset, "item": dlInfo.info},
                            title="Download History Update",
                            message=f"Download history updated with '{item.url}'.",
                        )
                        return {"status": "ok"}

                    message: str = (
                        f"The URL '{item.url}':'{archive_ids.pop(0)}' is already downloaded and recorded in archive."
                    )
                    LOG.warning(message)
                    queue._notify.emit(
                        Events.LOG_INFO, data={"preset": item.preset}, title="Already Downloaded", message=message
                    )
                    return {"status": "error", "msg": message, "hidden": True}

        if not item.requeued and (condition := Conditions.get_instance().match(info=entry)):
            already.pop()

            message = f"Condition '{condition.name}' matched for '{item!r}'."

            if condition.cli:
                message += f" Re-queuing with '{condition.cli}'."

            LOG.info(message)

            if condition.extras.get("ignore_download", False):
                extra_msg: str = ""
                if _archive_file and not condition.extras.get("no_archive", False):
                    archive_add(_archive_file, [archive_id])
                    extra_msg = f" and added to archive file '{_archive_file}'"

                _name = entry.get("title", entry.get("id"))
                log_message = f"Ignoring download of '{_name!r}' as per condition '{condition.name}'{extra_msg}."

                store_type, dlInfo = await queue.get_item(archive_id=archive_id)
                if not store_type:
                    dlInfo = Download(
                        info=ItemDTO(
                            id=entry.get("id"),
                            title=_name,
                            url=item.url,
                            preset=item.preset,
                            folder=item.folder,
                            status="skip",
                            cookies=item.cookies,
                            template=item.template,
                            msg=log_message,
                            extras=merge_dict(item.extras, get_extras(entry)),
                        )
                    )
                    await queue.done.put(dlInfo)

                LOG.info(log_message)
                queue._notify.emit(Events.LOG_INFO, data={}, title="Ignored Download", message=log_message)
                queue._notify.emit(
                    Events.ITEM_MOVED,
                    data={"to": "history", "preset": dlInfo.info.preset, "item": dlInfo.info},
                    title="Download History Update",
                    message=f"Download history updated with '{item.url}'.",
                )
                return {"status": "ok"}

            if condition.extras.get("set_preset") and (target_preset := condition.extras.get("set_preset")):
                if Presets.get_instance().has(target_preset):
                    log_message: str = f"Switching preset from '{item.preset}' to '{target_preset}' for '{item!r}' as per condition '{condition.name}'."
                    LOG.info(log_message)
                    queue._notify.emit(Events.LOG_INFO, data={}, title="Preset Switched", message=log_message)
                    item = item.new_with(preset=target_preset)
                else:
                    LOG.warning(
                        f"Preset '{target_preset}' specified in condition '{condition.name}' does not exist. Ignoring set_preset."
                    )

            return await add(queue=queue, item=item.new_with(requeued=True, cli=condition.cli), already=already)

        _status, _msg = ytdlp_reject(entry=entry, yt_params=yt_conf)
        if not _status:
            LOG.debug(_msg)
            return {"status": "error", "msg": _msg}

        end_time = time.perf_counter() - started
        LOG.debug(f"extract_info: for 'URL: {item.url}' is done in '{end_time:.3f}'. Length: '{len(entry)}/keys'.")
    except yt_dlp.utils.ExistingVideoReached as exc:
        LOG.error(f"Video has been downloaded already and recorded in archive.log file. '{exc!s}'.")
        return {"status": "error", "msg": "Video has been downloaded already and recorded in archive.log file."}
    except yt_dlp.utils.YoutubeDLError as exc:
        LOG.error(f"YoutubeDLError: Unable to extract info. '{exc!s}'.")
        return {"status": "error", "msg": str(exc)}
    except asyncio.exceptions.TimeoutError as exc:
        LOG.error(f"TimeoutError: Unable to extract info. '{exc!s}'.")
        return {
            "status": "error",
            "msg": f"TimeoutError: {queue.config.extract_info_timeout}s reached Unable to extract info.",
        }
    finally:
        if cookie_file and cookie_file.exists():
            try:
                cookie_file.unlink(missing_ok=True)
                yt_conf.pop("cookiefile", None)
            except Exception as e:
                LOG.error(f"Failed to remove cookie file '{yt_conf['cookiefile']}'. {e!s}")

    return await add_item(queue=queue, entry=entry, item=item, already=already, logs=logs, yt_params=yt_conf)
