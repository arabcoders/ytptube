import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web
from aiohttp.web import Request, Response
from pydantic import ValidationError

from app.features.core.schemas import CEAction, CEFeature, ConfigEvent, Pagination
from app.features.core.utils import build_pagination, format_validation_errors, normalize_pagination
from app.features.tasks.definitions.results import HandleTask as ExtendedTask
from app.features.tasks.definitions.results import TaskFailure, TaskResult
from app.features.tasks.definitions.service import TaskHandle
from app.features.tasks.repository import TasksRepository
from app.features.tasks.schemas import Task, TaskList, TaskPatch
from app.features.ytdlp.utils import parse_outtmpl
from app.library.ag_utils import ag
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.router import route
from app.library.Utils import get_channel_images, get_file, validate_url

if TYPE_CHECKING:
    from pathlib import Path


LOG: logging.Logger = logging.getLogger(__name__)

TIMER_SLOTS_PER_HOUR: int = 12


def _offset_timer(timer: str, index: int) -> str:
    """
    Add deterministic offset to CRON timer based on index.

    Uses 5-minute increments with 12 slots per hour (0-55 minutes).
    After 12 items, expands to hours.

    Formula:
        hours_offset = index // 12
        minutes_offset = (index % 12) * 5

    Examples:
        index 0: +0min, index 5: +25min, index 11: +55min
        index 12: +1hr 0min, index 24: +2hr 0min

    Args:
        timer: CRON expression string (5 fields)
        index: Task index for offset calculation

    Returns:
        Modified CRON expression with offset applied, or original on error

    """
    if not timer or index <= 0:
        return timer

    try:
        parts = timer.strip().split()
        if len(parts) != 5:
            return timer

        minute, hour, dom, month, dow = parts

        hours_offset = index // TIMER_SLOTS_PER_HOUR
        minutes_offset = (index % TIMER_SLOTS_PER_HOUR) * 5

        original_minute = int(minute) if minute.isdigit() else 0

        if minute.isdigit():
            new_minute = (original_minute + minutes_offset) % 60
            minute = str(new_minute)
        elif "/" in minute:
            base, step = minute.split("/", 1)
            if base.isdigit():
                new_base = (int(base) + minutes_offset) % 60
                minute = f"{new_base}/{step}"
        elif minute == "*":
            minute = str(minutes_offset)

        carry_hour = (original_minute + minutes_offset) // 60

        if hour.isdigit():
            new_hour = (int(hour) + hours_offset + carry_hour) % 24
            hour = str(new_hour)
        elif "/" in hour:
            base, step = hour.split("/", 1)
            if base.isdigit():
                new_base = (int(base) + hours_offset + carry_hour) % 24
                hour = f"{new_base}/{step}"
        elif hour == "*" and (hours_offset > 0 or carry_hour > 0):
            hour = str((hours_offset + carry_hour) % 24)

        return f"{minute} {hour} {dom} {month} {dow}"
    except Exception as e:
        LOG.warning(f"Failed to offset timer '{timer}': {e}")
        return timer


async def _get_info(url: str, preset: str) -> tuple[str | None, str | None]:
    """
    Fetch metadata from URL and extract title for task name.

    Also converts YouTube @handle URLs to channel IDs when possible.

    Args:
        url: URL to fetch metadata from
        preset: Preset name to use for extraction options

    Returns:
        Tuple of (title or None, converted_url or None)

    """
    try:
        from app.features.ytdlp.extractor import fetch_info
        from app.features.ytdlp.ytdlp_opts import YTDLPOpts

        params = YTDLPOpts.get_instance().add_cli("-I0", from_user=False)
        if preset:
            params.preset(name=preset)

        (metadata, _) = await fetch_info(config=params.get_all(), url=url)

        if not metadata or not isinstance(metadata, dict):
            return (None, None)

        title = ag(metadata, ["title", "fulltitle"])
        name = str(title)[:255] if title else None

        converted_url: str | None = None
        channel_id = metadata.get("channel_id")
        if channel_id and "/@" in url:
            import re

            converted_url = re.sub(r"/@[^/]+", f"/channel/{channel_id}", url)

        return (name, converted_url)
    except TimeoutError:
        LOG.debug(f"Timeout while inferring name from '{url}'")
        return (None, None)
    except Exception as e:
        LOG.debug(f"Failed to infer name from '{url}': {e}")
        return (None, None)


def _model(model: Any) -> Task:
    return Task.model_validate(model)


def _serialize(model: Any) -> dict:
    return _model(model).model_dump()


@route("GET", "api/tasks/", "tasks_list")
async def tasks_list(request: Request, repo: TasksRepository, encoder: Encoder) -> Response:
    page, per_page = normalize_pagination(request)
    items, total, current_page, total_pages = await repo.list_paginated(page, per_page)
    return web.json_response(
        data=TaskList(
            items=[_model(model) for model in items],
            pagination=Pagination.model_validate(build_pagination(total, current_page, per_page, total_pages)),
        ),
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", "api/tasks/", "tasks_add")
async def tasks_add(request: Request, repo: TasksRepository, encoder: Encoder, notify: EventBus) -> Response:
    data = await request.json()

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list) or len(data) == 0:
        return web.json_response(
            {"error": "Invalid request body. Expecting dict or list of dicts."},
            status=web.HTTPBadRequest.status_code,
        )

    first_item = data[0]
    if not isinstance(first_item, dict) or not first_item.get("url"):
        return web.json_response(
            {"error": "First item requires 'url' field."},
            status=web.HTTPBadRequest.status_code,
        )

    if not first_item.get("name"):
        return web.json_response(
            {"error": "First item requires 'name' field."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        first_task: Task = Task.model_validate(first_item)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate first task.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    if await repo.get_by_name(first_task.name):
        return web.json_response(
            data={"error": f"Task with name '{first_task.name}' already exists."},
            status=web.HTTPConflict.status_code,
        )

    created_tasks: list[dict[str, Any]] = []
    base_settings = first_task.model_dump(exclude={"id", "name", "url", "created_at", "updated_at"})

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            LOG.warning(f"Skipping item {idx}: not a dict")
            continue

        url = str(item.get("url", "")).strip()
        if not url:
            LOG.debug(f"Skipping item {idx}: empty URL")
            continue

        inferred_name, converted_url = await _get_info(url, item.get("preset", first_task.preset))
        name = item.get("name", first_task.name if 0 == idx else (inferred_name or f"task-{idx}"))

        final_name = str(name)
        counter = 1
        while await repo.get_by_name(final_name):
            final_name = f"{name}-{counter}"
            counter += 1

        item_settings = base_settings.copy()
        for key in ["timer", "preset", "folder", "template", "cli", "auto_start", "handler_enabled", "enabled"]:
            if key in item and item[key] is not None:
                item_settings[key] = item[key]

        task_dict: dict[str, Any] = {
            "name": final_name,
            "url": converted_url or url,
            **item_settings,
        }

        if not task_dict.get("timer") and first_task.timer and idx > 0:
            task_dict["timer"] = _offset_timer(first_task.timer, idx)

        try:
            validated = Task.model_validate(task_dict)
            task_data = validated.model_dump()
        except ValidationError as exc:
            LOG.warning(f"Skipping task {idx}: validation failed - {exc}")
            continue

        try:
            created = await repo.create(task_data)
            saved = _serialize(created)
            created_tasks.append(saved)
            notify.emit(
                Events.CONFIG_UPDATE,
                data=ConfigEvent(feature=CEFeature.TASKS, action=CEAction.CREATE, data=saved),
            )
        except ValueError as exc:
            LOG.warning(f"Failed to create task {idx}: {exc}")
            continue

    if len(created_tasks) == 0:
        return web.json_response(
            {"error": "Failed to create any tasks."},
            status=web.HTTPBadRequest.status_code,
        )

    if len(created_tasks) == 1:
        return web.json_response(data=created_tasks[0], status=web.HTTPOk.status_code, dumps=encoder.encode)

    return web.json_response(data=created_tasks, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("GET", r"api/tasks/{id:\d+}", "tasks_get")
async def tasks_get(request: Request, repo: TasksRepository, encoder: Encoder) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    model = await repo.get(identifier)
    if not model:
        return web.json_response({"error": "Task not found"}, status=web.HTTPNotFound.status_code)

    return web.json_response(data=_serialize(model), status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("DELETE", r"api/tasks/{id:\d+}", "tasks_delete")
async def tasks_delete(request: Request, repo: TasksRepository, encoder: Encoder, notify: EventBus) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    try:
        deleted = _serialize(await repo.delete(identifier))
        notify.emit(
            Events.CONFIG_UPDATE, data=ConfigEvent(feature=CEFeature.TASKS, action=CEAction.DELETE, data=deleted)
        )
        return web.json_response(
            data=deleted,
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )
    except KeyError as exc:
        return web.json_response({"error": str(exc)}, status=web.HTTPNotFound.status_code)


@route("PATCH", r"api/tasks/{id:\d+}", "tasks_patch")
async def tasks_patch(request: Request, repo: TasksRepository, encoder: Encoder, notify: EventBus) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    model = await repo.get(identifier)
    if not model:
        return web.json_response({"error": "Task not found"}, status=web.HTTPNotFound.status_code)

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = TaskPatch.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate task.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    if validated.name and await repo.get_by_name(validated.name, exclude_id=model.id):
        return web.json_response(
            data={"error": f"Task with name '{validated.name}' already exists."},
            status=web.HTTPConflict.status_code,
        )

    updated = _serialize(await repo.update(model.id, validated.model_dump(exclude_unset=True)))
    notify.emit(Events.CONFIG_UPDATE, data=ConfigEvent(feature=CEFeature.TASKS, action=CEAction.UPDATE, data=updated))
    return web.json_response(
        data=updated,
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("PUT", r"api/tasks/{id:\d+}", "tasks_update")
async def tasks_update(request: Request, repo: TasksRepository, encoder: Encoder, notify: EventBus) -> Response:
    if not (identifier := request.match_info.get("id")):
        return web.json_response({"error": "ID required"}, status=web.HTTPBadRequest.status_code)

    model = await repo.get(identifier)
    if not model:
        return web.json_response({"error": "Task not found"}, status=web.HTTPNotFound.status_code)

    data = await request.json()

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Invalid request body expecting dict."},
            status=web.HTTPBadRequest.status_code,
        )

    try:
        validated = Task.model_validate(data)
    except ValidationError as exc:
        return web.json_response(
            data={"error": "Failed to validate task.", "detail": format_validation_errors(exc)},
            status=web.HTTPBadRequest.status_code,
        )

    if validated.name and await repo.get_by_name(validated.name, exclude_id=model.id):
        return web.json_response(
            data={"error": f"Task with name '{validated.name}' already exists."},
            status=web.HTTPConflict.status_code,
        )

    updated = _serialize(await repo.update(model.id, validated.model_dump(exclude_unset=True)))
    notify.emit(Events.CONFIG_UPDATE, data=ConfigEvent(feature=CEFeature.TASKS, action=CEAction.UPDATE, data=updated))

    return web.json_response(data=updated, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/tasks/inspect", "task_handler_inspect")
async def task_handler_inspect(request: Request, handler: TaskHandle, encoder: Encoder, config: Config) -> Response:
    """
    Check if handler can process the given URL.

    Args:
        request: The request object.
        handler: The handler service instance.
        encoder: The encoder instance.
        config: The config instance.

    Returns:
        The response object.

    """
    data = await request.json()

    url: str | None = data.get("url") if isinstance(data, dict) else None
    if not url:
        return web.json_response({"error": "url is required."}, status=web.HTTPBadRequest.status_code)

    static_only: bool = data.get("static_only", False) if isinstance(data, dict) else False
    if not static_only:
        try:
            validate_url(url, allow_internal=config.allow_internal_urls)
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=web.HTTPBadRequest.status_code)

    preset: str = data.get("preset", "") if isinstance(data, dict) else ""
    handler_name: str | None = data.get("handler") if isinstance(data, dict) else None

    try:
        result: TaskResult | TaskFailure = await handler.inspect(
            url=url, preset=preset, handler_name=handler_name, static_only=static_only
        )
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            {"error": "Failed to inspect handler.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )

    return web.json_response(
        data=result,
        status=web.HTTPBadRequest.status_code if isinstance(result, TaskFailure) else web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("POST", r"api/tasks/{id:\d+}/mark", "tasks_mark")
async def task_mark(request: Request, repo: TasksRepository, encoder: Encoder) -> Response:
    """
    Mark all items from task as downloaded.

    Args:
        request: The request object.
        repo: The tasks repository instance.
        encoder: The encoder instance.

    Returns:
        The response object.

    """
    if not (task_id := request.match_info.get("id")):
        return web.json_response(data={"error": "No task id."}, status=web.HTTPBadRequest.status_code)

    try:
        model = await repo.get(int(task_id))
        if not model:
            return web.json_response(
                data={"error": f"Task '{task_id}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        # Convert to extended Task with handler methods
        task = ExtendedTask.model_validate(model)
        _status, _message = await task.mark()

        if not _status:
            return web.json_response(data={"error": _message}, status=web.HTTPBadRequest.status_code)

        return web.json_response(data={"message": _message}, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)


@route("DELETE", r"api/tasks/{id:\d+}/mark", "tasks_unmark")
async def task_unmark(request: Request, repo: TasksRepository, encoder: Encoder) -> Response:
    """
    Remove all task items from download archive.

    Args:
        request: The request object.
        repo: The tasks repository instance.
        encoder: The encoder instance.

    Returns:
        The response object.

    """
    if not (task_id := request.match_info.get("id")):
        return web.json_response(data={"error": "No task id."}, status=web.HTTPBadRequest.status_code)

    try:
        model = await repo.get(int(task_id))
        if not model:
            return web.json_response(
                data={"error": f"Task '{task_id}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        # Convert to extended Task with handler methods
        task = ExtendedTask.model_validate(model)
        _status, _message = await task.unmark()

        if not _status:
            return web.json_response(data={"error": _message}, status=web.HTTPBadRequest.status_code)

        return web.json_response(data={"message": _message}, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)


@route("POST", r"api/tasks/{id:\d+}/metadata", "tasks_metadata")
async def task_metadata(request: Request, repo: TasksRepository, config: Config, encoder: Encoder) -> Response:
    """
    Generate metadata for the task.

    Args:
        request: The request object.
        repo: The tasks repository instance.
        config: The config instance.
        encoder: The encoder instance.

    Returns:
        The response object.

    """
    if not (task_id := request.match_info.get("id")):
        return web.json_response(data={"error": "No task id."}, status=web.HTTPBadRequest.status_code)

    try:
        if not (model := await repo.get(int(task_id))):
            return web.json_response(
                data={"error": f"Task '{task_id}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        task = ExtendedTask.model_validate(model)

        (save_path, _) = get_file(config.download_path, task.folder)
        if not str(save_path or "").startswith(str(config.download_path)):
            return web.json_response(data={"error": "Invalid task folder."}, status=web.HTTPBadRequest.status_code)

        if not save_path.exists():
            save_path.mkdir(parents=True, exist_ok=True)

        metadata, status, message = await task.fetch_metadata()
        if not status:
            return web.json_response(data={"error": message}, status=web.HTTPBadRequest.status_code)
        if not isinstance(metadata, dict):
            return web.json_response(
                data={"error": "Failed to get metadata."},
                status=web.HTTPBadRequest.status_code,
            )

        if not task.folder:
            try:
                ytdlp_opts: dict = task.get_ytdlp_opts().get_all()
                outtmpl: str = parse_outtmpl(
                    output_template=ytdlp_opts.get("outtmpl", {}).get("default", "{title} [{id}]"),
                    info_dict=metadata,
                    params=ytdlp_opts,
                )
                if outtmpl:
                    _path: Path = save_path / outtmpl
                    if not _path.is_dir():
                        _path: Path = _path.parent

                    (save_path, _) = get_file(config.download_path, _path.relative_to(config.download_path))
                    if not str(save_path or "").startswith(str(config.download_path)):
                        return web.json_response(
                            data={"error": "Invalid final path folder."}, status=web.HTTPBadRequest.status_code
                        )

                    if not save_path.exists():
                        save_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                LOG.warning(f"Failed to resolve final path from outtmpl. '{e!s}'")

        info = {
            "id": ag(metadata, ["id", "channel_id"]),
            "id_type": metadata.get("extractor", "").split(":")[0].lower() if metadata.get("extractor") else None,
            "title": ag(metadata, ["title", "fulltitle"]) or None,
            "description": metadata.get("description", ""),
            "uploader": metadata.get("uploader", ""),
            "tags": metadata.get("tags", []),
            "year": metadata.get("release_year"),
            "thumbnails": get_channel_images(metadata.get("thumbnails", {})),
        }

        if not info.get("title"):
            return web.json_response(
                data={"error": "Failed to get title from metadata."}, status=web.HTTPBadRequest.status_code
            )

        LOG.info(f"Generating metadata for task '{task.name}' in '{save_path!s}'")

        from yt_dlp.utils import sanitize_filename

        from app.yt_dlp_plugins.postprocessor.nfo_maker import NFOMakerPP

        title: str = sanitize_filename(str(info.get("title") or ""))
        info_file: Path = save_path / f"{title} [{info.get('id')}].info.json"
        info_file.write_text(encoder.encode(metadata), encoding="utf-8")
        info["json_file"] = str(info_file.relative_to(config.download_path))

        xml_file: Path = save_path / "tvshow.nfo"
        info["nfo_file"] = str(xml_file.relative_to(config.download_path))

        xml_content = "<tvshow>\n"
        xml_content += f"  <title>{NFOMakerPP._escape_text(info.get('title'))}</title>\n"
        if info.get("description"):
            xml_content += f"  <plot>{NFOMakerPP._escape_text(NFOMakerPP._clean_description(str(info.get('description') or '')))}</plot>\n"
        if info.get("id"):
            xml_content += f"  <id>{NFOMakerPP._escape_text(info.get('id'))}</id>\n"
        if info.get("id_type") and info.get("id"):
            xml_content += f'  <uniqueid type="{NFOMakerPP._escape_text(info.get("id_type"))}" default="true">{NFOMakerPP._escape_text(info.get("id"))}</uniqueid>\n'
        if info.get("uploader"):
            xml_content += f"  <studio>{NFOMakerPP._escape_text(info.get('uploader'))}</studio>\n"
        if info.get("tags", []):
            for tag in info.get("tags", []):
                xml_content += f"  <tag>{NFOMakerPP._escape_text(tag)}</tag>\n"
        if info.get("year"):
            xml_content += f"  <year>{info.get('year')}</year>\n"
        xml_content += "  <status>Continuing</status>\n"
        xml_content += "</tvshow>\n"
        xml_file.write_text(xml_content, encoding="utf-8")

        try:
            from app.library.httpx_client import (
                Globals,
                build_request_headers,
                get_async_client,
                resolve_curl_transport,
            )

            ytdlp_args: dict = task.get_ytdlp_opts().get_all()
            use_curl = resolve_curl_transport()
            request_headers = build_request_headers(
                user_agent=request.headers.get("User-Agent", ytdlp_args.get("user_agent", Globals.get_random_agent())),
                use_curl=use_curl,
            )

            client = get_async_client(proxy=ytdlp_args.get("proxy"), use_curl=use_curl)
            thumbnails = info.get("thumbnails", {})
            if not isinstance(thumbnails, dict):
                thumbnails = {}
                info["thumbnails"] = thumbnails
            for key in thumbnails:
                url: str | None = None
                try:
                    url = thumbnails.get(key)
                    LOG.info(f"Fetching thumbnail '{key}' from '{url}'")
                    if not url:
                        continue

                    try:
                        validate_url(url, allow_internal=config.allow_internal_urls)
                    except ValueError:
                        LOG.warning(f"Invalid thumbnail url '{url}'")
                        continue

                    resp = await client.request(
                        method="GET",
                        url=url,
                        follow_redirects=True,
                        headers=request_headers,
                    )

                    img_file = save_path / f"{key}.jpg"
                    img_file.write_bytes(resp.content)
                    thumbnails[key] = str(img_file.relative_to(config.download_path))
                except Exception as e:
                    url_log = url or "unknown"
                    LOG.warning(f"Failed to fetch thumbnail '{key}' from '{url_log}'. '{e!s}'")
                    continue
        except Exception as e:
            LOG.warning(f"Failed to fetch thumbnails. '{e!s}'")

        return web.json_response(data=info, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)
