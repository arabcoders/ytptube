from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path

from app.features.streaming.library.ffprobe import ffprobe
from app.library.cache import Cache
from app.library.config import Config
from app.library.Utils import FILES_TYPE, get_file_sidecar

LOG: logging.Logger = logging.getLogger("player.thumbnail")

IMAGE_TYPES: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")
FOLDER_IMAGE_ORDER: tuple[str, ...] = ("thumbnail", "poster", "artwork", "cover", "fanart")
THUMBNAIL_SAMPLE_FRAMES = 200
THUMBNAIL_DEFAULT_SEEK_SECONDS = 3.0
THUMBNAIL_MIN_SEEK_SECONDS = 1.0
THUMBNAIL_MAX_SEEK_SECONDS = 15.0
THUMBNAIL_END_MARGIN_SECONDS = 0.1
THUMBNAIL_MISS_TTL = 3600.0

_LOCK = asyncio.Lock()
_IN_PROCESS: dict[str, asyncio.Task[Path | None]] = {}
_SEM: asyncio.Semaphore | None = None
_SEM_LIMIT: int | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _SEM, _SEM_LIMIT  # noqa: PLW0603

    limit: int = max(1, int(Config.get_instance().thumb_concurrency))
    if _SEM is None or _SEM_LIMIT != limit:
        _SEM = asyncio.Semaphore(limit)
        _SEM_LIMIT = limit
        LOG.info("Configured thumbnail generation to run %s job(s) at a time.", limit, extra={"limit": limit})

    return _SEM


def _is_same_stem_image(media_file: Path, image_file: Path) -> bool:
    if image_file.parent != media_file.parent:
        return False

    for image_type in FILES_TYPE:
        if "image" != image_type.get("type"):
            continue

        rx = image_type.get("rx")
        if rx and rx.search(image_file.name):
            break
    else:
        return False

    return image_file.stem == media_file.stem


def pick_local_thumb(media_file: Path) -> Path | None:
    sidecar: dict[str, list[dict[str, str]]] = get_file_sidecar(media_file)
    images: list[dict[str, str]] = sidecar.get("image", [])
    local_images: list[Path] = [Path(item["file"]) for item in images if isinstance(item.get("file"), Path)]

    for image_file in local_images:
        if image_file.suffix.lower() in IMAGE_TYPES and _is_same_stem_image(media_file, image_file):
            return image_file

    by_name: dict[str, Path] = {
        image_file.stem.lower(): image_file for image_file in local_images if image_file.suffix.lower() in IMAGE_TYPES
    }
    for name in FOLDER_IMAGE_ORDER:
        if image_file := by_name.get(name):
            return image_file

    return None


def _seek_seconds(ff_info) -> float | None:
    duration: float = 0.0
    try:
        duration = float(ff_info.metadata.get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0

    if duration <= 0:
        return THUMBNAIL_DEFAULT_SEEK_SECONDS

    if duration <= THUMBNAIL_END_MARGIN_SECONDS:
        return None

    return min(
        max(duration * 0.10, THUMBNAIL_MIN_SEEK_SECONDS),
        THUMBNAIL_MAX_SEEK_SECONDS,
        duration - THUMBNAIL_END_MARGIN_SECONDS,
    )


def _build_ffmpeg_args(media_file: Path, output_file: Path, *, seek_seconds: float | None) -> list[str]:
    args: list[str] = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
    ]

    if seek_seconds is not None and seek_seconds > 0:
        args.extend(["-ss", f"{seek_seconds:.3f}"])

    args.extend(
        [
            "-i",
            str(media_file),
            "-vf",
            f"thumbnail={THUMBNAIL_SAMPLE_FRAMES},scale=1280:-1:force_original_aspect_ratio=decrease",
            "-frames:v",
            "1",
            "-q:v",
            "3",
            "-an",
            str(output_file),
        ]
    )
    return args


async def _run_ffmpeg(media_file: Path, output_file: Path) -> Path | None:
    ff_info = await ffprobe(media_file)
    if not ff_info.has_video():
        LOG.debug(
            "Skipping thumbnail generation for '%s' because no video stream exists.",
            media_file,
            extra={"media_file": str(media_file)},
        )
        return None

    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = output_file.with_suffix(".tmp.jpg")

    if temp_file.exists():
        temp_file.unlink(missing_ok=True)

    seek_seconds: float | None = _seek_seconds(ff_info)
    attempts: list[float | None] = [seek_seconds]
    if seek_seconds is not None and seek_seconds > 0:
        attempts.append(None)

    sem = _get_semaphore()
    if sem.locked():
        limit = _SEM_LIMIT or 1
        LOG.debug(
            "Waiting for a thumbnail generation slot for '%s' (limit=%s).",
            media_file,
            limit,
            extra={"media_file": str(media_file), "limit": limit},
        )

    async with sem:
        last_error: str = "ffmpeg produced an empty thumbnail file"
        for idx, attempt_seek in enumerate(attempts, start=1):
            temp_file.unlink(missing_ok=True)
            args: list[str] = _build_ffmpeg_args(media_file, temp_file, seek_seconds=attempt_seek)
            LOG.debug(
                "Generating thumbnail for '%s'. attempt=%s/%s seek=%s",
                media_file,
                idx,
                len(attempts),
                "none" if attempt_seek is None else f"{attempt_seek:.3f}s",
                extra={
                    "media_file": str(media_file),
                    "attempt": idx,
                    "attempt_count": len(attempts),
                    "seek": "none" if attempt_seek is None else f"{attempt_seek:.3f}s",
                },
            )

            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except FileNotFoundError as exc:
                msg = "ffmpeg not found."
                raise OSError(msg) from exc

            stdout, stderr = await proc.communicate()
            if 0 == proc.returncode and temp_file.exists() and temp_file.stat().st_size > 0:
                temp_file.replace(output_file)
                LOG.info(
                    "Generated thumbnail '%s' for '%s'.",
                    output_file,
                    media_file,
                    extra={"media_file": str(media_file), "output_file": str(output_file)},
                )
                return output_file

            if 0 != proc.returncode:
                last_error: str = (
                    f"ffmpeg thumbnail generation failed (rc={proc.returncode}).\n"
                    f"stdout:\n{stdout.decode('utf-8', errors='replace')}\n"
                    f"stderr:\n{stderr.decode('utf-8', errors='replace')}"
                )
            else:
                last_error: str = "ffmpeg produced an empty thumbnail file"

            LOG.debug(
                "Thumbnail generation attempt failed for '%s'. seek=%s",
                media_file,
                "none" if attempt_seek is None else f"{attempt_seek:.3f}s",
                extra={
                    "media_file": str(media_file),
                    "seek": "none" if attempt_seek is None else f"{attempt_seek:.3f}s",
                },
            )

    temp_file.unlink(missing_ok=True)
    raise OSError(last_error)


async def ensure_thumb(media_file: Path, cache_root: Path, item_id: str | None = None) -> Path | None:
    config: Config = Config.get_instance()
    cache: Cache = Cache.get_instance()
    if bool(config.thumb_generate) is not True:
        return None

    sidecar: bool = bool(config.thumb_sidecar)
    if not sidecar and not item_id:
        msg = "item_id is required when thumbnail sidecar is disabled."
        raise ValueError(msg)

    thumb_id: str = str(media_file.resolve()) if sidecar else str(item_id)
    cache_file: Path = media_file.with_name(f"{media_file.name}.jpg") if sidecar else cache_root / f"{item_id}.jpg"

    miss_key: str = f"thumbnail-miss:{thumb_id}"

    if cache_file.exists() and cache_file.stat().st_size > 0:
        cache.delete(miss_key)
        return cache_file

    if cache.has(miss_key):
        return None

    async with _LOCK:
        if cache_file.exists() and cache_file.stat().st_size > 0:
            cache.delete(miss_key)
            return cache_file

        if cache.has(miss_key):
            return None

        task = _IN_PROCESS.get(thumb_id)
        if task is not None and not task.done():
            LOG.debug("Waiting for thumbnail generation for '%s'.", media_file, extra={"media_file": str(media_file)})
        else:
            task = asyncio.create_task(_run_ffmpeg(media_file, cache_file), name=f"thumb-{item_id or media_file.stem}")
            _IN_PROCESS[thumb_id] = task
            LOG.debug(
                "Starting thumbnail generation for '%s' -> '%s'.",
                media_file,
                cache_file,
                extra={"media_file": str(media_file), "cache_file": str(cache_file)},
            )

    try:
        result: Path | None = await task
        if result is None:
            cache.set(miss_key, value=True, ttl=THUMBNAIL_MISS_TTL)
        else:
            cache.delete(miss_key)
        return result
    except OSError:
        cache.set(miss_key, value=True, ttl=THUMBNAIL_MISS_TTL)
        raise
    finally:
        async with _LOCK:
            current = _IN_PROCESS.get(thumb_id)
            if current is task and task.done():
                _IN_PROCESS.pop(thumb_id, None)
