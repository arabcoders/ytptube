import logging
from collections.abc import Iterable

from aiohttp import web
from aiohttp.web import Request, Response

from app.library.Archiver import Archiver
from app.library.Presets import Presets
from app.library.router import route
from app.library.YTDLPOpts import YTDLPOpts

LOG: logging.Logger = logging.getLogger(__name__)


def _get_archive_file_from_preset(preset: str) -> str | None:
    """
    Resolve the archive file path for a given preset.

    Validates that the preset exists and that applying the preset results
    in yt-dlp options that contain a 'download_archive' path.
    """
    if not preset or not Presets.get_instance().has(preset):
        return None

    try:
        opts: dict = YTDLPOpts.get_instance().preset(preset).get_all()
    except Exception as e:
        LOG.error(f"Failed to build yt-dlp opts for preset '{preset}'. {e!s}")
        return None

    if not (archive_file := opts.get("download_archive")):
        return None

    if not isinstance(archive_file, str) or len(archive_file.strip()) < 1:
        return None

    return archive_file.strip()


def _normalize_ids(items: Iterable[str] | None) -> tuple[list[str], list[str]]:
    """
    Validate and normalize archive IDs.

    - Trims whitespace
    - Enforces that each ID has at least two whitespace-separated tokens
      (e.g., "youtube ABC123") as required by yt-dlp's archive format
    - De-duplicates while preserving order

    Returns a tuple: (valid_ids, invalid_inputs)
    """
    if not items:
        return ([], [])

    seen: set[str] = set()
    valid: list[str] = []
    invalid: list[str] = []

    for raw in items:
        if raw is None:
            continue

        s = str(raw).strip()
        if not s:
            continue

        if len(s.split()) < 2:
            invalid.append(s)
            continue

        if s in seen:
            continue

        seen.add(s)
        valid.append(s)

    return (valid, invalid)


@route("GET", "api/archiver/", "archiver")
async def archiver_get(request: Request) -> Response:
    """
    Read IDs from the download archive for a given preset.

    Query params:
      - preset: required preset name/id
      - ids: optional comma-separated list to filter; when omitted, returns all
    """
    preset: str | None = request.query.get("preset")
    if not preset:
        return web.json_response(data={"error": "preset is required."}, status=web.HTTPBadRequest.status_code)

    archive_file: str | None = _get_archive_file_from_preset(preset)
    if not archive_file:
        return web.json_response(
            data={"error": f"Preset '{preset}' does not provide a download_archive."},
            status=web.HTTPBadRequest.status_code,
        )

    ids_param: str | None = request.query.get("ids")
    ids: list[str] = []
    if ids_param:
        ids_list = [s.strip() for s in ids_param.split(",") if s and s.strip()]
        ids, invalid = _normalize_ids(ids_list)
        if invalid:
            return web.json_response(
                data={"error": "invalid ids provided.", "invalid_items": invalid},
                status=web.HTTPBadRequest.status_code,
            )

    try:
        data: list[str] = Archiver.get_instance().read(archive_file, ids or None)
        return web.json_response(
            data={"file": archive_file, "items": data, "count": len(data)}, status=web.HTTPOk.status_code
        )
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": f"Failed to read archive file for preset '{preset}'.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )


@route("POST", "api/archiver/", "archiver_add")
async def archiver_add(request: Request) -> Response:
    """
    Append IDs to the download archive for a given preset.

    Body: { "preset": string, "items": [string, ...], "skip_check": bool? }
    """
    post = await request.json()
    preset: str | None = post.get("preset") if isinstance(post, dict) else None
    if not preset:
        return web.json_response(data={"error": "preset is required."}, status=web.HTTPBadRequest.status_code)

    archive_file: str | None = _get_archive_file_from_preset(preset)
    if not archive_file:
        return web.json_response(
            data={"error": f"Preset '{preset}' does not provide a download_archive."},
            status=web.HTTPBadRequest.status_code,
        )

    items, invalid = _normalize_ids((post or {}).get("items", [])) if isinstance(post, dict) else ([], [])
    if invalid:
        return web.json_response(
            data={"error": "invalid ids provided.", "invalid_items": invalid},
            status=web.HTTPBadRequest.status_code,
        )
    if len(items) < 1:
        return web.json_response(
            data={"error": "items is required and must be a non-empty list."}, status=web.HTTPBadRequest.status_code
        )

    skip_check: bool = bool(post.get("skip_check", False)) if isinstance(post, dict) else False

    try:
        status: bool = Archiver.get_instance().add(archive_file, items, skip_check=skip_check)
        return web.json_response(
            data={"file": archive_file, "status": status, "items": items},
            status=web.HTTPOk.status_code if status else web.HTTPNotModified.status_code,
        )
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": f"Failed to add items to archive for preset '{preset}'.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )


@route("DELETE", "api/archiver/", "archiver_delete")
async def archiver_delete(request: Request) -> Response:
    """
    Remove IDs from the download archive for a given preset.

    Body: { "preset": string, "items": [string, ...] }
    """
    post = await request.json()
    preset: str | None = post.get("preset") if isinstance(post, dict) else None
    if not preset:
        return web.json_response(data={"error": "preset is required."}, status=web.HTTPBadRequest.status_code)

    archive_file: str | None = _get_archive_file_from_preset(preset)
    if not archive_file:
        return web.json_response(
            data={"error": f"Preset '{preset}' does not provide a download_archive."},
            status=web.HTTPBadRequest.status_code,
        )

    items, invalid = _normalize_ids((post or {}).get("items", [])) if isinstance(post, dict) else ([], [])
    if invalid:
        return web.json_response(
            data={"error": "invalid ids provided.", "invalid_items": invalid},
            status=web.HTTPBadRequest.status_code,
        )
    if len(items) < 1:
        return web.json_response(
            data={"error": "items is required and must be a non-empty list."}, status=web.HTTPBadRequest.status_code
        )

    try:
        status: bool = Archiver.get_instance().delete(archive_file, items)
        return web.json_response(
            data={"file": archive_file, "status": status, "items": items},
            status=web.HTTPOk.status_code if status else web.HTTPNotModified.status_code,
        )
    except Exception as e:
        LOG.exception(e)
        return web.json_response(
            data={"error": f"Failed to delete items from archive for preset '{preset}'.", "message": str(e)},
            status=web.HTTPInternalServerError.status_code,
        )
