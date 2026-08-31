from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

import regex
from yt_dlp.utils import OUTTMPL_TYPES

if TYPE_CHECKING:
    import re

_FALLBACK_NAME_MAX = 255
_MIN_ARTIFACT_RESERVE = 16
_MIN_TEMP_RESERVE = 32


class _Grapheme(NamedTuple):
    value: str
    start: int
    end: int


def _units(value: str) -> int:
    if os.name == "nt":
        return len(value.encode("utf-16-le", "surrogatepass")) // 2
    return len(os.fsencode(value))


def _existing_parent(directory: str) -> str:
    current = directory or "."
    while True:
        try:
            if os.path.exists(current):
                return current
        except OSError:
            pass
        parent = os.path.dirname(current)
        if not parent or parent == current:
            return "."
        current = parent


def _windows_name_max(root: str) -> int:
    try:
        import ctypes
        from ctypes import wintypes

        if not root:
            return _FALLBACK_NAME_MAX
        maximum = wintypes.DWORD()
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return _FALLBACK_NAME_MAX
        success = windll.kernel32.GetVolumeInformationW(
            root,
            None,
            0,
            None,
            ctypes.byref(maximum),
            None,
            None,
            0,
        )
        return maximum.value if success and maximum.value > 0 else _FALLBACK_NAME_MAX
    except (AttributeError, OSError, ValueError):
        return _FALLBACK_NAME_MAX


@lru_cache(maxsize=128)
def _cached_name_max(location: str) -> int:
    if os.name == "nt":
        return _windows_name_max(location)
    try:
        maximum = int(os.pathconf(location, "PC_NAME_MAX"))
        return maximum if maximum > 0 else _FALLBACK_NAME_MAX
    except (AttributeError, OSError, ValueError):
        return _FALLBACK_NAME_MAX


def _name_max(directory: str) -> int:
    existing = os.path.realpath(_existing_parent(directory))
    location = Path(existing).resolve().anchor if os.name == "nt" else existing
    return _cached_name_max(location)


def _extension(name: str, info: dict[str, Any], dir_type: str | None) -> str:
    candidates: list[str] = []
    forced = OUTTMPL_TYPES.get(dir_type) if dir_type else None
    if forced:
        candidates.append(f".{forced}")
    candidates.extend(
        f".{value}" for value in (info.get("final_ext"), info.get("ext")) if isinstance(value, str) and value
    )
    candidates.append(os.path.splitext(name)[1])
    return max((suffix for suffix in candidates if suffix and name.endswith(suffix)), key=len, default="")


def _temp_reserve(info: dict[str, Any]) -> int:
    suffixes = [".part", ".ytdl", ".part.ytdl"]
    formats = info.get("requested_formats")
    if isinstance(formats, (list, tuple)):
        suffixes.extend(
            f".f{item['format_id']}.part"
            for item in formats
            if isinstance(item, dict) and item.get("format_id") is not None
        )

    fragment_count = info.get("fragment_count")
    digits = len(str(fragment_count)) if isinstance(fragment_count, int) and fragment_count > 0 else 1
    suffixes.append(f".part-Frag{'9' * digits}.part")
    return max(_MIN_TEMP_RESERVE, *map(_units, suffixes))


def _artifact_reserve(info: dict[str, Any], params: dict[str, Any], extension: str) -> int:
    suffixes = [extension]
    subtitles = info.get("requested_subtitles")
    if (params.get("writesubtitles") or params.get("writeautomaticsub")) and isinstance(subtitles, dict):
        suffixes.extend(
            f".{language}.{item['ext']}"
            for language, item in subtitles.items()
            if isinstance(item, dict) and isinstance(item.get("ext"), str)
        )

    thumbnails = info.get("thumbnails")
    if params.get("write_all_thumbnails") and isinstance(thumbnails, list) and len(thumbnails) > 1:
        suffixes.extend(
            f".{item['id']}.{item.get('ext') or 'jpg'}"
            for item in thumbnails
            if isinstance(item, dict) and item.get("id") is not None
        )
    elif params.get("writethumbnail") and isinstance(thumbnails, list):
        suffixes.extend(f".{item.get('ext') or 'jpg'}" for item in thumbnails if isinstance(item, dict))

    return max(_MIN_ARTIFACT_RESERVE, *map(_units, suffixes))


def _protected(
    stem: str,
    patterns: tuple[re.Pattern[str], ...],
    clusters: list[_Grapheme],
) -> set[int]:
    spans = [match.span() for pattern in patterns for match in pattern.finditer(stem)]
    return {
        index
        for index, cluster in enumerate(clusters)
        if any(cluster.start < end and start < cluster.end for start, end in spans)
    }


def _render(clusters: list[_Grapheme], kept: set[int]) -> str:
    runs: list[str] = []
    current: list[str] = []
    previous = -2
    for index in sorted(kept):
        if index != previous + 1 and current:
            runs.append("".join(current))
            current = []
        current.append(clusters[index].value)
        previous = index
    if current:
        runs.append("".join(current))
    if not runs:
        return ""

    result = runs[0]
    for part in runs[1:]:
        separator = "" if result[-1:].isspace() or part[:1].isspace() else " "
        result = f"{result}{separator}{part}"
    return result


def _order(length: int, mode: str) -> list[int]:
    if mode == "end":
        return list(range(length))
    if mode == "start":
        return list(range(length - 1, -1, -1))

    order: list[int] = []
    left, right = 0, length - 1
    while left <= right:
        order.append(left)
        if left != right:
            order.append(right)
        left += 1
        right -= 1
    return order


def trim_filename(
    path: str,
    info: dict[str, Any],
    dir_type: str | None,
    mode: str,
    patterns: tuple[re.Pattern[str], ...],
    params: dict[str, Any] | None = None,
) -> str:
    directory, name = os.path.split(path)
    if not name:
        return path

    trimmed = trim_component(name, info, dir_type, mode, patterns, _name_max(directory), params)
    return os.path.join(directory, trimmed)


def trim_component(
    name: str,
    info: dict[str, Any],
    dir_type: str | None,
    mode: str,
    patterns: tuple[re.Pattern[str], ...],
    name_max: int,
    params: dict[str, Any] | None = None,
) -> str:

    extension = _extension(name, info, dir_type)
    stem = name.removesuffix(extension) if extension else name
    reserve = _temp_reserve(info)
    artifact_reserve = _artifact_reserve(info, params or {}, extension)
    stem_limit = name_max - reserve - artifact_reserve
    if _units(stem) <= stem_limit:
        return name
    if stem_limit < 1:
        msg = "The filesystem filename limit leaves no space for a filename stem."
        raise ValueError(msg)

    clusters = [_Grapheme(match.group(), match.start(), match.end()) for match in regex.finditer(r"\X", stem)]
    protected = _protected(stem, patterns, clusters)
    kept = set(protected)
    result = _render(clusters, kept)
    if _units(result) > stem_limit:
        msg = "The protected filename content exceeds the filesystem filename limit."
        raise ValueError(msg)

    for index in _order(len(clusters), mode):
        if index in protected:
            continue
        candidate = kept | {index}
        rendered = _render(clusters, candidate)
        if _units(rendered) <= stem_limit:
            kept = candidate
            result = rendered
        else:
            break

    if not result:
        result = "_"
    return f"{result}{extension}"
