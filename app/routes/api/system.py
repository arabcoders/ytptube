import asyncio
import logging
import os
import time
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response
from aiohttp.web_runner import GracefulExit

from app.features.dl_fields.service import DLFields
from app.features.presets.service import Presets
from app.library.config import Config
from app.library.downloads import DownloadQueue
from app.library.downloads.core import Download
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.router import route
from app.library.TerminalSessionManager import TerminalSessionConflictError, TerminalSessionManager
from app.library.UpdateChecker import UpdateChecker
from app.library.Utils import list_folders

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/system/configuration", "system.configuration")
async def system_config(queue: DownloadQueue, config: Config, encoder: Encoder) -> Response:
    """
    Pause non-active downloads.

    Args:
        queue (DownloadQueue): The download queue instance.
        config (Config): The config instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    return web.json_response(
        data={
            "app": config.frontend(),
            "presets": Presets.get_instance().get_all(),
            "dl_fields": await DLFields.get_instance().get_all_serialized(),
            "paused": queue.is_paused(),
            "folders": list_folders(
                path=Path(config.download_path),
                base=Path(config.download_path),
                depth_limit=config.download_path_depth - 1,
            ),
            "history_count": await queue.done.get_total_count(),
            "queue": (await queue.get("queue"))["queue"],
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/system/pause", "system.pause")
async def downloads_pause(queue: DownloadQueue, encoder: Encoder, notify: EventBus) -> Response:
    """
    Pause non-active downloads.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    if queue.is_paused():
        return web.json_response(
            {"message": "Non-active downloads are already paused."},
            status=web.HTTPNotAcceptable.status_code,
            dumps=encoder.encode,
        )

    queue.pause()

    msg = "Non-active downloads have been paused."
    notify.emit(
        Events.PAUSED,
        data={"paused": True, "at": time.time()},
        title="Downloads Paused",
        message=msg,
    )

    return web.json_response(data={"message": msg}, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/system/resume", "system.resume")
async def downloads_resume(queue: DownloadQueue, encoder: Encoder, notify: EventBus) -> Response:
    """
    Resume non-active downloads.

    Args:
        request (Request): The request object.
        queue (DownloadQueue): The download queue instance.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    if not queue.is_paused():
        return web.json_response(
            {"message": "Non-active downloads are not paused."},
            status=web.HTTPNotAcceptable.status_code,
            dumps=encoder.encode,
        )

    queue.resume()

    msg = "Resumed all downloads."
    notify.emit(
        Events.RESUMED,
        data={"paused": False, "at": time.time()},
        title="Downloads Resumed",
        message=msg,
    )

    return web.json_response(data={"message": msg}, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/system/shutdown", "system.shutdown")
async def shutdown_system(request: Request, config: Config, encoder: Encoder, notify: EventBus) -> Response:
    """
    Initiate application shutdown.

    Args:
        request (Request): The request object.
        config (Config): The config instance.
        encoder (Encoder): The encoder instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    if config.is_native is not True:
        return web.json_response(
            {"error": "Shutdown is only available in the native mode."},
            status=web.HTTPBadRequest.status_code,
        )

    app = request.app

    async def do_shutdown():
        notify.emit(
            Events.SHUTDOWN,
            data={"app": app},
            title="Application Shutdown",
            message="Shutdown initiated by user request.",
        )
        await asyncio.sleep(0.5)
        await app.shutdown()
        await app.cleanup()
        raise GracefulExit

    # Schedule shutdown after response
    asyncio.create_task(do_shutdown())
    LOG.info("Shutdown initiated by user request. Stopping the server...")
    return web.json_response(
        data={
            "message": "The application shutting down.",
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/system/check-updates", "system.check_updates")
async def check_updates(config: Config, encoder: Encoder, update_checker: UpdateChecker) -> Response:
    """
    Manually trigger update check.

    Args:
        config (Config): The config instance.
        encoder (Encoder): The encoder instance.
        update_checker (UpdateChecker): The update checker instance.

    Returns:
        Response: The response object.

    """
    if config.new_version or config.yt_new_version:
        return web.json_response(
            data={
                "app": {
                    "status": "update_available" if config.new_version else "up_to_date",
                    "current_version": config.app_version,
                    "new_version": config.new_version or None,
                },
                "ytdlp": {
                    "status": "update_available" if config.yt_new_version else "up_to_date",
                    "current_version": config._ytdlp_version(),
                    "new_version": config.yt_new_version or None,
                },
            },
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )

    (app_status, app_new_version), (ytdlp_status, ytdlp_new_version) = await update_checker.check_for_updates()

    return web.json_response(
        data={
            "app": {
                "status": app_status,
                "current_version": config.app_version,
                "new_version": app_new_version,
            },
            "ytdlp": {
                "status": ytdlp_status,
                "current_version": config._ytdlp_version(),
                "new_version": ytdlp_new_version,
            },
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


async def _validate_terminal_command_request(request: Request) -> str | Response:
    if not request.can_read_body:
        return web.json_response(
            {"error": "Request body is required."},
            status=web.HTTPBadRequest.status_code,
        )

    payload = await request.json()
    if not isinstance(payload, dict):
        return web.json_response(
            {"error": "Invalid request payload."},
            status=web.HTTPBadRequest.status_code,
        )

    raw_command = payload.get("command")
    if not isinstance(raw_command, str) or not raw_command.strip():
        return web.json_response(
            {"error": "Command is required."},
            status=web.HTTPBadRequest.status_code,
        )

    return raw_command


@route("POST", "api/system/terminal", "system.terminal")
async def create_terminal_session(
    request: Request, config: Config, encoder: Encoder, terminal_manager: TerminalSessionManager
) -> Response:
    if not config.console_enabled:
        return web.json_response(
            {"error": "Console feature is disabled."},
            status=web.HTTPForbidden.status_code,
        )

    raw_command = await _validate_terminal_command_request(request)
    if isinstance(raw_command, Response):
        return raw_command

    try:
        metadata = await terminal_manager.create_session(raw_command)
    except TerminalSessionConflictError as exc:
        return web.json_response(
            {"error": str(exc)},
            status=web.HTTPConflict.status_code,
        )

    return web.json_response(data=metadata, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("GET", "api/system/terminal/active", "system.terminal.active")
async def get_active_terminal_session(
    config: Config, encoder: Encoder, terminal_manager: TerminalSessionManager
) -> Response:
    if not config.console_enabled:
        return web.json_response(
            {"error": "Console feature is disabled."},
            status=web.HTTPForbidden.status_code,
        )

    metadata = await terminal_manager.get_active_session()
    return web.json_response(data=metadata, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("GET", "api/system/terminal/{session_id}", "system.terminal.session")
async def get_terminal_session(
    request: Request, config: Config, encoder: Encoder, terminal_manager: TerminalSessionManager
) -> Response:
    if not config.console_enabled:
        return web.json_response(
            {"error": "Console feature is disabled."},
            status=web.HTTPForbidden.status_code,
        )

    session_id = request.match_info.get("session_id", "")
    metadata = await terminal_manager.get_session(session_id)
    if metadata is None:
        return web.json_response(
            {"error": "Terminal session not found."},
            status=web.HTTPNotFound.status_code,
        )

    return web.json_response(data=metadata, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("DELETE", "api/system/terminal/{session_id}", "system.terminal.cancel")
async def cancel_terminal_session(
    request: Request, config: Config, encoder: Encoder, terminal_manager: TerminalSessionManager
) -> Response:
    if not config.console_enabled:
        return web.json_response(
            {"error": "Console feature is disabled."},
            status=web.HTTPForbidden.status_code,
        )

    session_id = request.match_info.get("session_id", "")
    try:
        await terminal_manager.cancel_session(session_id)
    except FileNotFoundError:
        return web.json_response(
            {"error": "Terminal session not found."},
            status=web.HTTPNotFound.status_code,
        )
    except RuntimeError as exc:
        return web.json_response(
            {"error": str(exc)},
            status=web.HTTPConflict.status_code,
        )

    return web.json_response(
        data={"message": "Terminal session cancellation requested.", "session_id": session_id},
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/system/terminal/{session_id}/stream", "system.terminal.stream")
async def stream_terminal_session(
    request: Request, config: Config, terminal_manager: TerminalSessionManager
) -> Response | web.StreamResponse:
    if not config.console_enabled:
        return web.json_response(
            {"error": "Console feature is disabled."},
            status=web.HTTPForbidden.status_code,
        )

    session_id = request.match_info.get("session_id", "")
    metadata = await terminal_manager.get_session(session_id)
    if metadata is None:
        return web.json_response(
            {"error": "Terminal session not found."},
            status=web.HTTPNotFound.status_code,
        )

    try:
        return await terminal_manager.stream_session(session_id=session_id, request=request)
    except ValueError as exc:
        return web.json_response(
            {"error": str(exc)},
            status=web.HTTPBadRequest.status_code,
        )


@route("GET", "api/system/limits", "system.limits")
async def system_limits(queue: DownloadQueue, config: Config, encoder: Encoder) -> Response:
    """Return user-facing operational limits for downloads and extraction."""
    active_downloads: dict[str, Download] = queue.pool.get_active_downloads()
    queue_items: list[tuple[str, Download]] = list(queue.queue.items())

    active_non_live: list[Download] = [download for download in active_downloads.values() if not download.is_live]
    active_live: list[Download] = [download for download in active_downloads.values() if download.is_live]
    queued_non_live: list[Download] = [
        download
        for _, download in queue_items
        if not download.started() and not download.is_live and getattr(download.info, "auto_start", True) is not False
    ]

    def _get_extractor_override_limits(config: Config) -> dict[str, dict[str, int | str]]:
        overrides: dict[str, dict[str, int | str]] = {}
        prefix = "YTP_MAX_WORKERS_FOR_"

        for env_key, raw_value in os.environ.items():
            if not env_key.startswith(prefix):
                continue

            if not (extractor := env_key.removeprefix(prefix).strip().lower()):
                continue

            if not raw_value.isdigit() or int(raw_value) < 1:
                continue

            configured = int(raw_value)
            overrides[extractor] = {
                "configured": raw_value,
                "effective": min(configured, config.max_workers),
                "source": "env_override",
            }

        return overrides

    overrides: dict[str, dict[str, int | str]] = _get_extractor_override_limits(config)
    per_extractor: dict[str, dict[str, int | str]] = {}

    for download in [*active_non_live, *queued_non_live]:
        extractor = (download.info.get_extractor() or "unknown").lower()
        entry = per_extractor.setdefault(
            extractor,
            {
                "name": extractor,
                "limit": config.max_workers_per_extractor,
                "source": "default",
                "active": 0,
                "queued": 0,
                "available": config.max_workers_per_extractor,
            },
        )

        if extractor in overrides:
            entry["limit"] = overrides[extractor]["effective"]
            entry["source"] = overrides[extractor]["source"]

        if download in active_non_live:
            entry["active"] += 1
        else:
            entry["queued"] += 1

    for extractor, override in overrides.items():
        per_extractor.setdefault(
            extractor,
            {
                "name": extractor,
                "limit": override["effective"],
                "source": override["source"],
                "active": 0,
                "queued": 0,
                "available": override["effective"],
            },
        )

    for entry in per_extractor.values():
        entry["available"] = max(int(entry["limit"]) - int(entry["active"]), 0)

    return web.json_response(
        data={
            "downloads": {
                "paused": queue.is_paused(),
                "live_bypasses_limits": True,
                "global": {
                    "limit": config.max_workers,
                    "active": len(active_non_live),
                    "available": max(config.max_workers - len(active_non_live), 0),
                    "live_active": len(active_live),
                    "queued": len(queued_non_live),
                },
                "per_extractor": {
                    "default_limit": config.max_workers_per_extractor,
                    "items": sorted(per_extractor.values(), key=lambda item: str(item["name"])),
                },
            },
            "extraction": {
                "concurrency": config.extract_info_concurrency,
                "timeout_seconds": config.extract_info_timeout,
                "info_cache_ttl_seconds": config.download_info_expires,
            },
            "live": {
                "prevent_premiere": config.prevent_live_premiere,
                "premiere_buffer_minutes": config.live_premiere_buffer,
            },
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )
