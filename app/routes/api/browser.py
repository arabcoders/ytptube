import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus

from aiohttp import web
from aiohttp.web import Request, Response

from app.features.core.utils import build_pagination, normalize_pagination
from app.features.streaming.library.ffprobe import ffprobe
from app.library.cache import Cache
from app.library.config import Config
from app.library.downloads import DownloadQueue
from app.library.encoder import Encoder
from app.library.Events import EventBus, Events
from app.library.log import get_logger
from app.library.router import route
from app.library.Utils import delete_dir, get_file, get_file_sidecar, get_files, get_mime_type, move_file, rename_file

LOG = get_logger()


@route("GET", "api/file/ffprobe/{file:.*}", "ffprobe")
async def get_ffprobe(request: Request, config: Config, encoder: Encoder, app: web.Application) -> Response:
    """
    Get the ffprobe data.

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        encoder (Encoder): The encoder object.
        app (web.Application): The aiohttp application object.

    Returns:
        Response: The response object.

    """
    file: str = request.match_info.get("file")
    if not file:
        return web.json_response(data={"error": "file is required."}, status=web.HTTPBadRequest.status_code)

    try:
        realFile, status = get_file(download_path=config.download_path, file=file)
        if web.HTTPFound.status_code == status:
            return Response(
                status=web.HTTPFound.status_code,
                headers={
                    "Location": str(
                        app.router["ffprobe"].url_for(
                            file=str(realFile.relative_to(config.download_path).as_posix()).strip("/")
                        )
                    ),
                },
            )

        if web.HTTPNotFound.status_code == status:
            return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

        return web.json_response(data=await ffprobe(realFile), status=web.HTTPOk.status_code, dumps=encoder.encode)
    except Exception as e:
        return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)


@route("GET", "api/file/info/{file:.*}", "file_info")
async def get_file_info(request: Request, config: Config, encoder: Encoder, app: web.Application) -> Response:
    """
    Get file info

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        encoder (Encoder): The encoder object.
        app (web.Application): The aiohttp application object.

    Returns:
        Response: The response object.

    """
    file: str = request.match_info.get("file")
    if not file:
        return web.json_response(data={"error": "file is required."}, status=web.HTTPBadRequest.status_code)

    try:
        realFile, status = get_file(download_path=config.download_path, file=file)
        if web.HTTPFound.status_code == status:
            return Response(
                status=web.HTTPFound.status_code,
                headers={
                    "Location": str(
                        app.router["file_info"].url_for(
                            file=str(realFile.relative_to(config.download_path).as_posix()).strip("/")
                        )
                    ),
                },
            )

        if web.HTTPNotFound.status_code == status:
            return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

        ff_info = await ffprobe(realFile)

        response = {
            "title": realFile.stem,
            "ffprobe": ff_info,
            "mimetype": get_mime_type(ff_info.get("metadata", {}), realFile),
            "sidecar": get_file_sidecar(realFile),
        }

        for key in response["sidecar"]:
            for i, f in enumerate(response["sidecar"][key]):
                response["sidecar"][key][i]["file"] = str(
                    realFile.with_name(f["file"].name).relative_to(config.download_path)
                ).strip("/")

        return web.json_response(data=response, status=web.HTTPOk.status_code, dumps=encoder.encode)
    except Exception as e:
        LOG.exception(
            "Failed to load file info for '%s' because %s.",
            file,
            e,
            extra={"route": "file_info", "file_path": file},
        )
        return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)


@route("GET", "api/file/browser/{path:.*}", "file_browser")
async def file_browser(request: Request, config: Config, encoder: Encoder) -> Response:
    """
    Get the file browser.

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        encoder (Encoder): The encoder object.

    Returns:
        Response: The response object.

    """
    req_path: str = request.match_info.get("path")
    req_path: str = "/" if not req_path else unquote_plus(req_path)

    raw_req: str = (req_path or "").strip()
    root_dir: Path = Path(config.download_path).resolve()
    if raw_req in ("", "/"):
        test: Path = root_dir
        rel_for_listing: str = "/"
    else:
        # Strip leading slash so joinpath doesn't ignore the base path.
        test = root_dir.joinpath(raw_req.lstrip("/")).resolve(strict=False)
        rel_for_listing: str = raw_req.lstrip("/")

    try:
        test.relative_to(root_dir)
    except Exception:
        return web.json_response(
            data={"error": f"path '{req_path}' does not exist."}, status=web.HTTPNotFound.status_code
        )

    if not test.exists():
        return web.json_response(
            data={"error": f"path '{req_path}' does not exist."}, status=web.HTTPNotFound.status_code
        )

    if not test.is_dir() and not test.is_symlink():
        return web.json_response(
            data={"error": f"path '{req_path}' is not a directory."}, status=web.HTTPBadRequest.status_code
        )

    try:
        page, per_page = normalize_pagination(request)
        sort_by: str = request.query.get("sort_by", "name")
        sort_order: str = request.query.get("sort_order", "asc")
        search: str | None = request.query.get("search")

        if sort_by not in ("name", "size", "date", "type"):
            sort_by = "name"

        if sort_order not in ("asc", "desc"):
            sort_order = "asc"

        contents, total = get_files(
            base_path=root_dir,
            dir=rel_for_listing,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            search=search,
        )

        total_pages: int = (total + per_page - 1) // per_page if total > 0 else 1

        return web.json_response(
            data={
                "path": rel_for_listing,
                "contents": contents,
                "pagination": build_pagination(total, page, per_page, total_pages),
            },
            status=web.HTTPOk.status_code,
            dumps=encoder.encode,
        )
    except OSError as e:
        LOG.exception(
            "Failed to browse file path '%s' because %s.",
            req_path,
            e,
            extra={"route": "file_browser", "request_path": req_path},
        )
        return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)


@route("POST", "api/file/actions", "browser.file.actions")
async def path_actions(request: Request, config: Config, queue: DownloadQueue, notify: EventBus) -> Response:
    """
    Browser actions.

    Args:
        request (Request): The request object.
        config (Config): The configuration object.
        queue (DownloadQueue): The download queue instance.
        notify (EventBus): The event bus instance.

    Returns:
        Response: The response object.

    """
    if not config.browser_control_enabled:
        return web.json_response(
            data={"error": "File browser actions is disabled."}, status=web.HTTPForbidden.status_code
        )

    rootPath: Path = Path(config.download_path)

    try:
        actions = await request.json()
        if not actions or not isinstance(actions, list):
            return web.json_response(
                data={"error": "Invalid parameters expecting list of dicts."}, status=web.HTTPBadRequest.status_code
            )
    except Exception as e:
        LOG.debug(
            "Ignoring invalid file browser actions JSON.",
            extra={"route": "browser.file.actions", "error": str(e)},
        )
        return web.json_response(data={"error": "Invalid JSON."}, status=web.HTTPBadRequest.status_code)

    # validate each action before performing any operations
    for params in actions:
        action = params.get("action").lower()
        if not action or action not in ["rename", "delete", "move", "directory"]:
            return web.json_response(
                data={"error": f"Invalid action '{action}'. Must be one of rename, delete, move, directory."},
                status=web.HTTPBadRequest.status_code,
            )

        if "rename" == action and not params.get("new_name"):
            return web.json_response(
                data={"error": "New name is required for rename action."}, status=web.HTTPBadRequest.status_code
            )

        if "move" == action and not params.get("new_path"):
            return web.json_response(
                data={"error": "New path is required for move action."}, status=web.HTTPBadRequest.status_code
            )

        if "directory" == action and not params.get("new_dir"):
            return web.json_response(
                data={"error": "New directory name is required for directory action."},
                status=web.HTTPBadRequest.status_code,
            )

    operations_status: list[dict[str, Any]] = []

    def record(
        op_path: str | Path,
        *,
        ok: bool,
        error: str | None = None,
        action: str | None = None,
        extra: dict | None = None,
    ) -> None:
        try:
            if isinstance(op_path, Path):
                rel: str = str(op_path.relative_to(rootPath)).strip("/")
            else:
                rel: str = str(op_path).strip("/")
        except Exception:
            rel = str(op_path)
        if not rel or rel == ".":
            rel = "/"

        entry: dict = {"path": rel, "status": ok, "error": error}

        if action:
            entry["action"] = action

        if extra:
            norm_extra: dict = {}
            for k, v in extra.items():
                if isinstance(v, Path):
                    try:
                        norm_extra[k] = str(v.relative_to(rootPath)).strip("/") or "/"
                    except Exception:
                        norm_extra[k] = str(v)
                else:
                    norm_extra[k] = v
            entry.update(norm_extra)

        operations_status.append(entry)

    # perform each action
    for params in actions:
        req_path: str = params.get("path")
        if not req_path:
            record("no_path", ok=False, error="Path is required.", extra={"item": params})
            continue

        action: str = params.get("action", "").lower()
        if not action:
            record(req_path, ok=False, error="Action is required.", extra={"item": params})
            continue

        req_path: str = "/" if not req_path else unquote_plus(req_path)

        test: Path = Path(config.download_path)
        if req_path and "/" != req_path:
            test = test.joinpath(req_path)

        if not test.exists():
            record(req_path, ok=False, error=f"path '{req_path}' does not exist.", action=action)
            continue

        try:
            path, status = get_file(
                download_path=config.download_path, file=str(test.relative_to(config.download_path))
            )
            if web.HTTPOk.status_code != status:
                record(req_path, ok=False, error="Invalid path.", action=action)
                continue
            if not path.is_relative_to(rootPath):
                record(req_path, ok=False, error="Path outside download root.", action=action)
                continue
        except Exception as e:
            LOG.exception(
                "Failed to resolve file browser action '%s' for path '%s' because %s.",
                action,
                req_path,
                e,
                extra={"route": "browser.file.actions", "action": action, "request_path": req_path},
            )
            record(req_path, ok=False, error=str(e), action=action, extra={"item": params})
            continue

        if "directory" != action:
            if path == rootPath:
                record(path, ok=False, error="Cannot operate on root directory.", action=action)
                continue

            if not path.is_relative_to(rootPath):
                record(path, ok=False, error="Path outside download root.", action=action)
                continue

        if "directory" == action:
            new_dir = params.get("new_dir").lstrip("/").strip()
            if not new_dir:
                record(path, ok=False, error="New directory name is required.", action=action)
                continue

            new_path = path.joinpath(*new_dir.split("/"))
            try:
                new_path = new_path.resolve(strict=False)
            except Exception:
                record(path, ok=False, error="Invalid directory path.", action=action, extra={"new_dir": new_dir})
                continue

            root_real = Path(config.download_path).resolve()
            if not new_path.is_relative_to(root_real):
                record(path, ok=False, error="Destination outside root.", action=action, extra={"new_dir": new_path})
                continue

            if new_path.exists():
                dst = new_path.relative_to(config.download_path)
                record(path, ok=False, error="Directory already exists.", action=action, extra={"new_dir": dst})
                continue

            try:
                new_path.mkdir(parents=True, exist_ok=True)
                record(path, ok=True, action=action, extra={"new_dir": new_path.relative_to(config.download_path)})
                LOG.info(
                    "Created directory '%s'.",
                    new_path.relative_to(config.download_path),
                    extra={
                        "route": "browser.file.actions",
                        "directory": str(new_path.relative_to(config.download_path)),
                    },
                )
            except OSError as e:
                LOG.exception(
                    "Failed to create directory '%s' because %s.",
                    new_dir,
                    e,
                    extra={
                        "route": "browser.file.actions",
                        "action": action,
                        "request_path": req_path,
                        "new_dir": new_dir,
                    },
                )
                record(path, ok=False, error=str(e), action=action, extra={"item": params})
                continue

        if "rename" == action:
            new_name: str = params.get("new_name")
            if not new_name:
                record(path, ok=False, error="New name is required for rename action.", action=action)
                continue

            new_path: Path = path.parent.joinpath(new_name)
            if new_path.exists():
                record(
                    new_path, ok=False, error="Destination already exists.", action=action, extra={"new_path": new_path}
                )
                continue

            try:
                sidecar_count: int = 0
                sidecar_renamed: list[tuple[Path, Path]] = []
                if path.is_dir():
                    renamed: Path = path.rename(new_path)
                else:
                    renamed, sidecar_renamed = rename_file(path, new_name)
                    sidecar_count: int = len(sidecar_renamed)

                LOG.info(
                    "Renamed '%s' to '%s'.",
                    path.relative_to(config.download_path),
                    renamed.relative_to(config.download_path),
                    extra={
                        "route": "browser.file.actions",
                        "old_path": str(path.relative_to(config.download_path)),
                        "new_path": str(renamed.relative_to(config.download_path)),
                        "sidecar_count": sidecar_count,
                    },
                )
            except OSError as e:
                LOG.exception(
                    "Failed to rename file browser path '%s' because %s.",
                    path.relative_to(config.download_path),
                    e,
                    extra={
                        "route": "browser.file.actions",
                        "action": action,
                        "file_path": str(path.relative_to(config.download_path)),
                        "new_name": new_name,
                    },
                )
                record(path, ok=False, error=str(e), action=action, extra={"item": params})
                continue
            except ValueError as e:
                record(path, ok=False, error=str(e), action=action, extra={"item": params})
                continue
            else:
                extra_info: dict[str, Path] = {"new_path": renamed}
                if sidecar_renamed:
                    extra_info["sidecar_count"] = len(sidecar_renamed)
                record(path, ok=True, action=action, extra=extra_info)

                for old_sidecar, new_sidecar in sidecar_renamed:
                    record(old_sidecar, ok=True, action=action, extra={"new_path": new_sidecar})

                if item := await queue.done.get_item(filename=str(path.relative_to(config.download_path))):
                    item.info.filename = str(renamed.relative_to(config.download_path))
                    if sidecar_renamed:
                        item.info.get_file_sidecar()

                    await queue.done.put(item)
                    notify.emit(Events.ITEM_UPDATED, data=item.info)

        if "delete" == action:
            try:
                if not path.exists():
                    record(path, ok=False, error="Path does not exist.", action=action)
                    continue

                if path.is_dir():
                    delete_dir(path)
                else:
                    path.unlink(missing_ok=True)

                LOG.info(
                    "Deleted '%s'.",
                    path.relative_to(config.download_path),
                    extra={"route": "browser.file.actions", "file_path": str(path.relative_to(config.download_path))},
                )
            except OSError as e:
                LOG.exception(
                    "Failed to delete file browser path '%s' because %s.",
                    path.relative_to(config.download_path),
                    e,
                    extra={
                        "route": "browser.file.actions",
                        "action": action,
                        "file_path": str(path.relative_to(config.download_path)),
                    },
                )
                record(path, ok=False, error=str(e), action=action, extra={"item": params})
                continue
            else:
                record(path, ok=True, action=action, extra={"deleted": True})

        if "move" == action:
            new_path = params.get("new_path")
            if not new_path:
                record(path, ok=False, error="New path is required for move.", action=action, extra={"item": params})
                continue

            raw_new: str = unquote_plus(str(new_path)).strip()
            target_dir: Path = (
                Path(config.download_path)
                if not raw_new or raw_new in ("/", ".")
                else Path(config.download_path).joinpath(raw_new.lstrip("/"))
            )

            try:
                target_dir = target_dir.resolve()
            except Exception:
                record(
                    path, ok=False, error="Destination path is invalid.", action=action, extra={"new_path": target_dir}
                )
                continue

            root_real: Path = Path(config.download_path).resolve()
            if not target_dir.exists() or not target_dir.is_dir():
                record(
                    path, ok=False, error="Destination path is invalid.", action=action, extra={"new_path": target_dir}
                )
                continue

            if not target_dir.is_relative_to(root_real):
                record(
                    path,
                    ok=False,
                    error="Destination outside download root.",
                    action=action,
                    extra={"new_path": target_dir},
                )
                continue

            if path.parent == target_dir:
                record(path, ok=False, error="Source and destination are the same.", action=action)
                continue

            try:
                sidecar_count: int = 0
                sidecar_moved: list[tuple[Path, Path]] = []

                if path.is_dir():
                    dest: Path = target_dir.joinpath(path.name)
                    moved: Path = path.rename(dest)
                else:
                    moved, sidecar_moved = move_file(path, target_dir)
                    sidecar_count: int = len(sidecar_moved)

                LOG.info(
                    "Moved '%s' to '%s'.",
                    path.relative_to(config.download_path),
                    moved.relative_to(config.download_path),
                    extra={
                        "route": "browser.file.actions",
                        "old_path": str(path.relative_to(config.download_path)),
                        "new_path": str(moved.relative_to(config.download_path)),
                        "sidecar_count": sidecar_count,
                    },
                )
            except OSError as e:
                LOG.exception(
                    "Failed to move file browser path '%s' because %s.",
                    path.relative_to(config.download_path),
                    e,
                    extra={
                        "route": "browser.file.actions",
                        "action": action,
                        "file_path": str(path.relative_to(config.download_path)),
                        "new_path": raw_new,
                    },
                )
                record(path, ok=False, error=str(e), action=action, extra={"item": params})
                continue
            except ValueError as e:
                record(path, ok=False, error=str(e), action=action, extra={"item": params})
                continue
            else:
                extra_info: dict[str, Path] = {"new_path": moved}
                if sidecar_moved:
                    extra_info["sidecar_count"] = len(sidecar_moved)

                record(path, ok=True, action=action, extra=extra_info)

                for old_sidecar, new_sidecar in sidecar_moved:
                    record(old_sidecar, ok=True, action=action, extra={"new_path": new_sidecar})

                if item := await queue.done.get_item(filename=str(path.relative_to(config.download_path))):
                    item.info.filename = str(moved.relative_to(config.download_path))
                    if sidecar_moved:
                        item.info.get_file_sidecar()

                    await queue.done.put(item)
                    notify.emit(Events.ITEM_UPDATED, data=item.info)

    return web.json_response(data=operations_status, status=web.HTTPOk.status_code)


@route("POST", "api/file/download", "browser.download.prepare")
async def prepare_zip_file(request: Request, config: Config, cache: Cache):
    json = await request.json()
    if not json or not isinstance(json, list):
        return web.json_response({"error": "Invalid parameters."}, status=400)

    files: list[str] = []
    for f in json:
        if not isinstance(f, str):
            continue

        ref, status = get_file(download_path=config.download_path, file=f)
        if status == web.HTTPNotFound.status_code:
            continue
        files.append(ref)

        sc: list[dict] = get_file_sidecar(ref)
        if sc:
            for side in sc:
                for scf in sc[side]:
                    if isinstance(scf, dict) and "file" in scf:
                        files.append(scf["file"])  # noqa: PERF401

    if not files:
        return web.json_response({"error": "No valid files."}, status=400)

    import uuid

    token = str(uuid.uuid4())

    cache.set(f"download:{token}", files, ttl=600)

    return web.json_response(
        data={"token": token, "files": [str(f.relative_to(config.download_path)) for f in files]},
        status=web.HTTPOk.status_code,
    )


@route("GET", "api/file/download/{token}", "browser.download.stream")
async def stream_zip_download(request: Request, config: Config, cache: Cache) -> Response | web.StreamResponse:
    token: str | None = request.match_info.get("token")
    if not token:
        return web.json_response({"error": "Download token is required."}, status=web.HTTPBadRequest.status_code)

    files: Any | None = cache.get(f"download:{token}")

    if not files or not isinstance(files, list):
        return web.json_response({"error": "Invalid or expired download token."}, status=web.HTTPBadRequest.status_code)

    files: list[Path] = [p for p in files if p.is_file() and p.exists()]

    if len(files) < 1:
        return web.json_response({"error": "No valid files."}, status=web.HTTPBadRequest.status_code)

    from zipstream import ZipStream

    rootPath = Path(config.download_path).resolve()
    zs = ZipStream()
    for file in files:
        zs.add_path(str(file), str(file.relative_to(rootPath)))

    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "application/zip",
            "Content-Disposition": f'attachment; filename="{token}.zip"',
        },
    )
    await response.prepare(request)

    try:
        LOG.info(
            "Started streaming a ZIP download with %d file(s).",
            len(files),
            extra={"route": "browser.download.stream", "token": token, "file_count": len(files)},
        )
        for chunk in zs:
            if request.transport is None or request.transport.is_closing():
                LOG.info(
                    "Stopped streaming the ZIP download because the client disconnected.",
                    extra={"route": "browser.download.stream", "token": token},
                )
                break
            await response.write(chunk)
        await response.write_eof()
    except asyncio.CancelledError:
        LOG.info(
            "Stopped streaming the ZIP download because the client cancelled it.",
            extra={"route": "browser.download.stream", "token": token},
        )
    except Exception as e:
        LOG.exception(
            "Failed to stream the ZIP download.",
            extra={
                "route": "browser.download.stream",
                "token": token,
                "file_count": len(files),
                "exception_type": type(e).__name__,
            },
        )

    return response
