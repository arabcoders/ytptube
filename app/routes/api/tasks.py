import asyncio
import functools
import logging
import uuid
from typing import TYPE_CHECKING, Any

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.ag_utils import ag
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.router import route
from app.library.Tasks import Task, TaskFailure, TaskResult, Tasks
from app.library.Utils import get_channel_images, get_file, init_class, parse_outtmpl, validate_url, validate_uuid

if TYPE_CHECKING:
    from pathlib import Path

LOG: logging.Logger = logging.getLogger(__name__)


@route("POST", "api/tasks/inspect", "task_handler_inspect")
async def task_handler_inspect(request: Request, tasks: Tasks, encoder: Encoder, config: Config) -> Response:
    """
    Check if handler can process the given URL.

    Args:
        request (Request): The request object.
        tasks (Tasks): The tasks instance.
        encoder (Encoder): The encoder instance.
        config (Config): The config instance.

    Returns:
        Response: The response object.

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
        result: TaskResult | TaskFailure = await tasks.get_handler().inspect(
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


@route("GET", "api/tasks/", "tasks")
async def tasks(encoder: Encoder) -> Response:
    """
    Get the tasks.

    Args:
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object.

    """
    return web.json_response(data=Tasks.get_instance().get_all(), status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("PUT", "api/tasks/", "tasks_add")
async def tasks_add(request: Request, encoder: Encoder) -> Response:
    """
    Add tasks to the queue.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object

    """
    data = await request.json()

    if not isinstance(data, list):
        return web.json_response(
            {"error": "Invalid request body expecting list with dicts."},
            status=web.HTTPBadRequest.status_code,
        )

    tasks: list = []

    ins = Tasks.get_instance()

    for item in data:
        if not isinstance(item, dict):
            return web.json_response(
                {"error": "Invalid request body expecting list with dicts."},
                status=web.HTTPBadRequest.status_code,
            )

        if not item.get("url"):
            return web.json_response({"error": "url is required.", "data": item}, status=web.HTTPBadRequest.status_code)

        if not item.get("id", None) or not validate_uuid(item.get("id"), version=4):
            item["id"] = str(uuid.uuid4())

        if not item.get("template", None):
            item["template"] = ""

        if not item.get("cli", None):
            item["cli"] = ""

        try:
            Tasks.validate(item)
        except ValueError as e:
            return web.json_response(
                {"error": f"Failed to validate task '{item.get('name', '??')}'. '{e!s}'"},
                status=web.HTTPBadRequest.status_code,
            )

        tasks.append(init_class(Task, item))

    try:
        tasks = ins.save(tasks=tasks).load().get_all()
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            {"error": "Failed to save tasks.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )

    return web.json_response(data=tasks, status=web.HTTPOk.status_code, dumps=encoder.encode)


@route("POST", "api/tasks/{id}/mark", "tasks_mark")
async def task_mark(request: Request, encoder: Encoder) -> Response:
    """
    Mark all items from task as downloaded.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object

    """
    task_id: str = request.match_info.get("id", None)

    if not task_id:
        return web.json_response(data={"error": "No task id."}, status=web.HTTPBadRequest.status_code)

    tasks: Tasks = Tasks.get_instance()
    try:
        task: Task | None = tasks.get(task_id)
        if not task:
            return web.json_response(
                data={"error": f"Task '{task_id}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        _status, _message = task.mark()
        if not _status:
            return web.json_response(data={"error": _message}, status=web.HTTPBadRequest.status_code)

        return web.json_response(data={"message": _message}, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)


@route("DELETE", "api/tasks/{id}/mark", "tasks_unmark")
async def task_unmark(request: Request, encoder: Encoder) -> Response:
    """
    Remove All tasks items from download archive.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object

    """
    task_id: str = request.match_info.get("id", None)

    if not task_id:
        return web.json_response(data={"error": "No task id."}, status=web.HTTPBadRequest.status_code)

    tasks: Tasks = Tasks.get_instance()
    try:
        task: Task | None = tasks.get(task_id)
        if not task:
            return web.json_response(
                data={"error": f"Task '{task_id}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        _status, _message = task.unmark()
        if not _status:
            return web.json_response(data={"error": _message}, status=web.HTTPBadRequest.status_code)

        return web.json_response(data={"message": _message}, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)


@route("POST", "api/tasks/{id}/metadata", "tasks_metadata")
async def task_metadata(request: Request, config: Config, encoder: Encoder) -> Response:
    """
    Generate metadata for the task.

    Args:
        request (Request): The request object.
        config (Config): The config instance.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object

    """
    task_id: str = request.match_info.get("id", None)

    if not task_id:
        return web.json_response(data={"error": "No task id."}, status=web.HTTPBadRequest.status_code)

    tasks: Tasks = Tasks.get_instance()
    try:
        task: Task | None = tasks.get(task_id)
        if not task:
            return web.json_response(
                data={"error": f"Task '{task_id}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        (save_path, _) = get_file(config.download_path, task.folder)
        if not str(save_path or "").startswith(str(config.download_path)):
            return web.json_response(data={"error": "Invalid task folder."}, status=web.HTTPBadRequest.status_code)

        if not save_path.exists():
            save_path.mkdir(parents=True, exist_ok=True)

        metadata, status, message = await asyncio.wait_for(
            fut=asyncio.get_running_loop().run_in_executor(
                None,
                functools.partial(task.fetch_metadata, full=False),
            ),
            timeout=120,
        )
        if not status:
            return web.json_response(data={"error": message}, status=web.HTTPBadRequest.status_code)

        if not task.folder:
            try:
                outtmpl = parse_outtmpl(
                    output_template=task.get_ytdlp_opts().get_all().get("outtmpl", {}).get("default", "{title} [{id}]"),
                    info_dict=metadata,
                )
                if outtmpl:
                    _path = save_path / outtmpl
                    if not _path.is_dir():
                        _path = _path.parent

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

        from yt_dlp.utils import sanitize_filename

        from app.yt_dlp_plugins.postprocessor.nfo_maker import NFOMakerPP

        title: str = sanitize_filename(info.get("title"))
        info_file: Path = save_path / f"{title} [{info.get('id')}].info.json"
        info_file.write_text(encoder.encode(metadata), encoding="utf-8")
        info["json_file"] = str(info_file.relative_to(config.download_path))

        xml_file: Path = save_path / "tvshow.nfo"
        info["nfo_file"] = str(xml_file.relative_to(config.download_path))

        xml_content = "<tvshow>\n"
        xml_content += f"  <title>{NFOMakerPP._escape_text(info.get('title'))}</title>\n"
        if info.get("description"):
            xml_content += (
                f"  <plot>{NFOMakerPP._escape_text(NFOMakerPP._clean_description(info.get('description')))}</plot>\n"
            )
        if info.get("id"):
            xml_content += f"  <id>{NFOMakerPP._escape_text(info.get('id'))}</id>\n"
        if info.get("id_type") and info.get("id"):
            xml_content += f'  <uniqueid type="{NFOMakerPP._escape_text(info.get("id_type"))}" default="true">{NFOMakerPP._escape_text(info.get("id"))}</uniqueid>\n'
        if info.get("uploader"):
            xml_content += f"  <studio>{NFOMakerPP._escape_text(info.get('uploader'))}</studio>\n"
        if info.get("tags", []):
            for tag in info.get("tags", []):
                xml_content += f"  <tags>{NFOMakerPP._escape_text(tag)}</tags>\n"
        if info.get("year"):
            xml_content += f"  <year>{info.get('year')}</year>\n"
        xml_content += "  <status>Continuing</status>\n"
        xml_content += "</tvshow>\n"
        xml_file.write_text(xml_content, encoding="utf-8")

        try:
            from yt_dlp.utils.networking import random_user_agent

            from app.library.httpx_client import async_client

            ytdlp_args: dict = task.get_ytdlp_opts().get_all()
            opts: dict[str, Any] = {
                "headers": {
                    "User-Agent": request.headers.get("User-Agent", ytdlp_args.get("user_agent", random_user_agent())),
                },
            }
            if proxy := ytdlp_args.get("proxy"):
                opts["proxy"] = proxy

            try:
                from httpx_curl_cffi import AsyncCurlTransport, CurlOpt

                opts["transport"] = AsyncCurlTransport(
                    impersonate="chrome",
                    default_headers=True,
                    curl_options={CurlOpt.FRESH_CONNECT: True},
                )
                opts.pop("headers", None)
            except Exception:
                pass

            async with async_client(**opts) as client:
                for key in info.get("thumbnails", {}):
                    try:
                        url = info["thumbnails"][key]
                        LOG.info(f"Fetching thumbnail '{key}' from '{url}'")
                        if not url:
                            continue

                        try:
                            validate_url(url, allow_internal=config.allow_internal_urls)
                        except ValueError:
                            LOG.warning(f"Invalid thumbnail url '{url}'")
                            continue

                        resp = await client.request(method="GET", url=url, follow_redirects=True)

                        img_file = save_path / f"{key}.jpg"
                        img_file.write_bytes(resp.content)
                        info["thumbnails"][key] = str(img_file.relative_to(config.download_path))
                    except Exception as e:
                        LOG.warning(f"Failed to fetch thumbnail '{key}' from '{url}'. '{e!s}'")
                        continue
        except Exception as e:
            LOG.warning(f"Failed to fetch thumbnails. '{e!s}'")

        return web.json_response(data=info, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except ValueError as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)


@route("PATCH", "api/tasks/{id}", "tasks_update")
async def task_update(request: Request, encoder: Encoder) -> Response:
    """
    Update specific fields of a task.

    Args:
        request (Request): The request object.
        encoder (Encoder): The encoder instance.

    Returns:
        Response: The response object

    """
    if not (task_id := request.match_info.get("id", None)):
        return web.json_response(data={"error": "No task id."}, status=web.HTTPBadRequest.status_code)

    try:
        data = await request.json()
    except Exception as e:
        return web.json_response(
            data={"error": "Invalid JSON in request body.", "message": str(e)},
            status=web.HTTPBadRequest.status_code,
        )

    if not isinstance(data, dict):
        return web.json_response(
            {"error": "Request body must be a JSON object."},
            status=web.HTTPBadRequest.status_code,
        )

    tasks: Tasks = Tasks.get_instance()
    try:
        task: Task | None = tasks.get(task_id)
        if not task:
            return web.json_response(
                data={"error": f"Task '{task_id}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        task_dict: dict = task.serialize()
        protected_fields: set[str] = {"id"}
        updated: bool = False

        for key, value in data.items():
            if key in protected_fields or key not in task_dict:
                continue

            setattr(task, key, value)
            updated = True

        if not updated:
            return web.json_response(
                data={"error": "No valid fields to update."},
                status=web.HTTPBadRequest.status_code,
            )

        try:
            Tasks.validate(task)
        except ValueError as e:
            return web.json_response({"error": f"Validation failed: {e!s}"}, status=web.HTTPBadRequest.status_code)

        tasks.save(tasks=tasks.get_all()).load()

        return web.json_response(data=task, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": "Failed to update task.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )
