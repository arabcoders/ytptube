import json
import logging
import os
import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import formatdate
from pathlib import Path
from typing import Any

from app.features.ytdlp.ytdlp import YTDLP
from app.library.Utils import merge_dict, timed_lru_cache

LOG: logging.Logger = logging.getLogger("ytdlp.utils")


class _DATA:
    YTDLP_INFO_CLS: Any = None
    YTDLP_PARAMS: dict[str, Any] = {
        "simulate": True,
        "color": "no_color",
        "extract_flat": True,
        "skip_download": True,
        "ignoreerrors": True,
        "ignore_no_formats_error": True,
        "quiet": True,
    }
    REMOVE_KEYS: list = [
        {
            "paths": "-P, --paths",
            "outtmpl": "-o, --output",
            "progress_hooks": "--progress_hooks",
            "postprocessor_hooks": "--postprocessor_hooks",
            "post_hooks": "--post_hooks",
        },
        {
            "quiet": "-q, --quiet",
            "no_warnings": "--no-warnings",
            "skip_download": "--skip-download",
            "forceprint": "-O, --print",
            "simulate": "--simulate",
            "noprogress": "--no-progress",
            "wait_for_video": "--wait-for-video",
            "progress_delta": " --progress-delta",
            "progress_template": "--progress-template",
            "consoletitle": "--console-title",
            "progress_with_newline": "--newline",
            "forcejson": "-j, --dump-single-json",
            "opt_update_to": "--update-to",
            "opt_ap_list_mso": "--ap-list-mso",
            "opt_batch_file": "-a, --batch-file",
            "opt_alias": "--alias",
            "opt_list_extractors": "--list-extractors",
            "opt_version": "--version",
            "opt_help": "-h, --help",
            "opt_update": "-U, --update",
            "opt_list_subtitles": "--list-subs",
            "opt_list_thumbnails": "--list-thumbnails",
            "opt_list_format": "-F, --list-formats",
            "opt_dump_agent": "--dump-user-agent",
            "opt_extractor_descriptions": "--extractor-descriptions",
            "opt_list_impersonate_targets": "--list-impersonate-targets",
        },
    ]
    "Keys to remove from yt-dlp options at various levels."


@dataclass(kw_only=True)
class LogTarget:
    """
    A data class that represents a logging target with its level and type.

    Attributes:
        name (str): The name of the logging target.
        target: The logging target, which can be a logging.Logger instance or a callable.
        level (int): The logging level for the target.
        logger (bool): True if the target is a logging.Logger instance, False otherwise.
        type: The type of the target.

    """

    name: str | None = None
    target: logging.Logger | Callable
    level: int
    logger: bool


class LogWrapper:
    def __init__(self):
        self.targets: list[LogTarget] = []

    def add_target(self, target: logging.Logger | Callable, level: int = logging.DEBUG, name: str | None = None):
        """
        Adds a new logging target with the specified logging level.

        Args:
            target (logging.Logger|Callable): The logging target, which can be a logging.Logger instance or a Callable.
            level (int): The logging level for the target. Defaults to logging.DEBUG.
            name (str|None): The name of the logging target. Defaults to None.

        """
        if not isinstance(target, logging.Logger | Callable):
            msg = "Target must be a logging.Logger instance or a callable."
            raise TypeError(msg)

        if name is None:
            name = target.name if isinstance(target, logging.Logger) else target.__name__

        self.targets.append(
            LogTarget(
                name=name,
                target=target,
                level=level,
                logger=isinstance(target, logging.Logger),
            )
        )

    def has_targets(self):
        return len(self.targets) > 0

    def _log(self, level, msg, *args, **kwargs):
        for target in self.targets:
            if level < target.level:
                continue

            if target.logger:
                target.target.log(level, msg, *args, **kwargs)
            else:
                target.target(level, msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._log(logging.CRITICAL, msg, *args, **kwargs)


def patch_metadataparser() -> None:
    """
    Patches yt_dlp MetadataParserPP action to handle subprocess pickling issues.
    """
    try:
        from yt_dlp.postprocessor.metadataparser import MetadataParserPP
        from yt_dlp.utils import Namespace
    except Exception as exc:
        LOG.warning(f"Unable to import yt_dlp metadata parser for patching: {exc!s}")
        return

    if getattr(MetadataParserPP.Actions, "_ytptube_patched", False):
        return

    class _ActionNS(Namespace):
        _ACTIONS_STR: list[str] = []

        @staticmethod
        def _get_name(func) -> str | None:
            if not callable(func):
                return None

            target = getattr(func, "__func__", func)
            module_name = getattr(target, "__module__", None)
            qual_name = getattr(target, "__qualname__", getattr(target, "__name__", None))

            return f"{module_name}.{qual_name}" if module_name and qual_name else None

        def __contains__(self, candidate: object) -> bool:
            if candidate in self.__dict__.values():
                return True

            if func_name := _ActionNS._get_name(candidate):
                if len(_ActionNS._ACTIONS_STR) < 1:
                    _ActionNS._ACTIONS_STR.extend([_ActionNS._get_name(value) for value in self.__dict__.values()])

                return func_name in _ActionNS._ACTIONS_STR

            return False

    actions_dict: dict[str, Any] = dict(MetadataParserPP.Actions.items_)
    MetadataParserPP.Actions = _ActionNS(**actions_dict)
    MetadataParserPP.Actions._ytptube_patched = True
    LOG.debug("MetadataParserPP action namespace patch applied successfully.")


def arg_converter(
    args: str,
    level: int | bool | None = None,
    dumps: bool = False,
    removed_options: list | None = None,
    keep_defaults: bool = False,
) -> dict:
    """
    Convert yt-dlp options to a dictionary.

    Args:
        args (str): yt-dlp options string.
        level (int|bool|None): Level of options to remove, True for all.
        dumps (bool): Dump options as JSON.
        removed_options (list|None): List of removed options.
        keep_defaults (bool): Keep default options.

    Returns:
        dict: yt-dlp options dictionary.

    """
    import yt_dlp.options

    create_parser = yt_dlp.options.create_parser

    def _default_opts(args: str):
        patched_parser = create_parser()
        try:
            yt_dlp.options.create_parser = lambda: patched_parser
            return yt_dlp.parse_options(args)
        finally:
            yt_dlp.options.create_parser = create_parser

    try:
        patch_metadataparser()
    except Exception as exc:
        LOG.debug("Metadata parser patch failed to apply: %s", exc)

    default_opts = _default_opts([]).ydl_opts

    if args:
        # important to ignore external config files.
        args = "--ignore-config " + args

    opts = yt_dlp.parse_options(shlex.split(args, posix=os.name != "nt")).ydl_opts
    diff = {k: v for k, v in opts.items() if default_opts[k] != v} if not keep_defaults else opts.items()
    if "postprocessors" in diff:
        diff["postprocessors"] = [pp for pp in diff["postprocessors"] if pp not in default_opts["postprocessors"]]

    if "_warnings" in diff:
        diff.pop("_warnings", None)

    if level is True or isinstance(level, int):
        bad_options = {}
        if isinstance(level, bool) or not isinstance(level, int):
            level = len(_DATA.REMOVE_KEYS)

        for i, item in enumerate(_DATA.REMOVE_KEYS):
            if i > level:
                break

            bad_options.update(item.items())

        for key in diff.copy():
            if key not in bad_options:
                continue

            if isinstance(removed_options, list):
                removed_options.append(bad_options[key])

            diff.pop(key, None)

    if dumps is True:
        from app.library.encoder import Encoder

        if "match_filter" in diff:
            import inspect

            matchFilter = inspect.getclosurevars(diff["match_filter"].func).nonlocals["filters"]
            if isinstance(matchFilter, set):
                diff["match_filter"] = {"filters": list(matchFilter)}

        return json.loads(json.dumps(diff, cls=Encoder, default=str))

    return diff


def extract_ytdlp_logs(logs: list[str], filters: list[str | re.Pattern] = None) -> list[str]:
    """
    Extract yt-dlp log lines matching built-in filters plus any extras.

    Args:
        logs (list): log strings.
        filters (list[str|Re.Pattern]): Optional extra filters of strings and/or regex.

    Returns:
        (list): List of matching log lines.

    """
    all_patterns: list[str | re.Pattern] = [
        "This live event will begin",
        "Video unavailable. This video is private",
        "This video is available to this channel",
        "Private video. Sign in if you've been granted access to this video",
        "[youtube] Premieres in",
        "Falling back on generic information extractor",
        "URL could be a direct video link, returning it as such",
    ] + (filters or [])

    compiled: list[re.Pattern] = [
        p if isinstance(p, re.Pattern) else re.compile(re.escape(p), re.IGNORECASE) for p in all_patterns
    ]

    matched: list[str] = []
    matched.extend(line for line in logs if line and any(p.search(line) for p in compiled))

    return list(dict.fromkeys(matched))


def ytdlp_reject(entry: dict, yt_params: dict) -> tuple[bool, str]:
    """
    Implement yt-dlp reject filter logic.

    Args:
        entry (dict): The entry to check.
        yt_params (dict): The yt-dlp parameters containing filters.

    Returns:
        tuple[bool, str]: A tuple where the first element is True if the entry passes the filters, or False if it does not,
                          and the second element is a message explaining the reason for rejection or an empty string if it passes.

    """
    if title := entry.get("title"):
        if (matchtitle := yt_params.get("matchtitle")) and not re.search(matchtitle, title, re.IGNORECASE):
            return (False, f'"{title}" title did not match pattern "{matchtitle}". Skipping download.')

        if (rejecttitle := yt_params.get("rejecttitle")) and re.search(rejecttitle, title, re.IGNORECASE):
            return (False, f'"{title}" title matched reject pattern "{rejecttitle}". Skipping download.')

    date = entry.get("upload_date")
    date_range = yt_params.get("daterange")
    if (date and date_range) and date not in date_range:
        return (False, f"Upload date '{date}' is not in range '{date_range}'.")

    view_count = entry.get("view_count")
    if view_count is not None:
        min_views = yt_params.get("min_views")
        if min_views is not None and view_count < min_views:
            return (
                False,
                f"Skipping {entry.get('title', 'video')}, because it has not reached minimum view count ({view_count}/{min_views}).",
            )

        max_views = yt_params.get("max_views")
        if max_views is not None and view_count > max_views:
            return (
                False,
                f"Skipping {entry.get('title', 'video')}, because it has exceeded maximum view count ({view_count}/{max_views}).",
            )

    try:
        from yt_dlp.utils import age_restricted

        if entry.get("age_limit") and age_restricted(entry.get("age_limit"), yt_params.get("age_limit")):
            return (False, f'Video "{entry.get("title", "unknown")}" is age restricted.')
    except ImportError:
        pass

    return (True, "")


def get_ytdlp(params: dict | None = None) -> YTDLP:
    if params:
        return YTDLP(params=merge_dict(params, _DATA.YTDLP_PARAMS))

    if _DATA.YTDLP_INFO_CLS is None:
        _DATA.YTDLP_INFO_CLS = YTDLP(params=_DATA.YTDLP_PARAMS)

    return _DATA.YTDLP_INFO_CLS


def get_thumbnail(thumbnails: list) -> str | None:
    """
    Extract thumbnail URL from a yt-dlp entry.

    Args:
        thumbnails (list): The list of thumbnail dictionaries from yt-dlp entry.

    Returns:
        str | None: The thumbnail URL if available, otherwise None.

    """
    if not thumbnails or not isinstance(thumbnails, list):
        return None

    def _thumb_sort_key(thumb: dict) -> tuple:
        return (
            thumb.get("preference") if thumb.get("preference") is not None else -1,
            thumb.get("width") if thumb.get("width") is not None else -1,
            thumb.get("height") if thumb.get("height") is not None else -1,
            thumb.get("id") if thumb.get("id") is not None else "",
            thumb.get("url"),
        )

    return max(thumbnails, key=_thumb_sort_key, default=None)


def get_extras(entry: dict, kind: str = "video") -> dict:
    """
    Extract useful information from a yt-dlp entry.

    Args:
        entry (dict): The entry data from yt-dlp.
        kind (str): The type of the item (e.g., "video", "playlist").

    Returns:
        dict: The extracted data.

    """
    extras = {}

    if not entry or not isinstance(entry, dict):
        return extras

    if "playlist" == kind:
        for property in ("id", "title", "uploader", "uploader_id"):
            if val := entry.get(property):
                extras[f"playlist_{property}"] = val

    if thumbnail := get_thumbnail(entry.get("thumbnails", [])):
        extras["thumbnail"] = thumbnail.get("url")
    elif thumbnail := entry.get("thumbnail"):
        extras["thumbnail"] = thumbnail

    for property in ("uploader", "channel"):
        if val := entry.get(property):
            extras[property] = val

    if release_in := entry.get("release_timestamp"):
        extras["release_in"] = formatdate(release_in, usegmt=True)

    if release_in and "is_upcoming" == entry.get("live_status"):
        extras["is_live"] = release_in

    if duration := entry.get("duration"):
        extras["duration"] = duration

    extras["is_premiere"] = bool(entry.get("is_premiere", False))

    extractor_key = entry.get("ie_key") or entry.get("extractor_key") or entry.get("extractor") or ""
    if "thumbnail" not in extras and "youtube" in str(extractor_key).lower():
        extras["thumbnail"] = "https://img.youtube.com/vi/{id}/maxresdefault.jpg".format(**entry)

    return extras


def parse_outtmpl(output_template: str, info_dict: dict, params: dict | None = None) -> str:
    """
    Parse yt-dlp output template with given info_dict.

    Args:
        output_template (str): The output template string.
        info_dict (dict): The info dictionary from yt-dlp.
        params (dict|None): Additional parameters for yt-dlp.

    Returns:
        str: The parsed output string.

    """
    return get_ytdlp(params=params).prepare_filename(info_dict=info_dict, outtmpl=output_template)


@timed_lru_cache(ttl_seconds=300, max_size=256)
def get_archive_id(url: str) -> dict[str, str | None]:
    """
    Get the archive ID for a given URL.

    Args:
        url (str): URL to check.

    Returns:
        dict: {
            "id": str | None,
            "ie_key": str | None,
            "archive_id": str | None
        }

    """
    idDict: dict[str, None] = {
        "id": None,
        "ie_key": None,
        "archive_id": None,
    }
    from yt_dlp.utils import make_archive_id

    for key, _ie in get_ytdlp()._ies.items():
        try:
            if not _ie.suitable(url):
                continue

            if not _ie.working():
                continue

            temp_id = _ie.get_temp_id(url)
            if not temp_id:
                continue

            idDict["id"] = temp_id
            idDict["ie_key"] = key
            idDict["archive_id"] = make_archive_id(_ie, temp_id)
            break
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Error getting archive ID: {e}")

    return idDict


def archive_add(file: str | Path, ids: list[str], skip_check: bool = False) -> bool:
    """
    Add IDs to an archive file (delegates to the global Archiver).

    Args:
        file (str|Path): The archive file path.
        ids (list[str]): List of IDs to add.
        skip_check (bool): If True, skip checking for existing IDs.

    Returns:
        bool: True if any new IDs were appended, False otherwise.

    """
    from app.features.ytdlp.archiver import Archiver

    return Archiver.get_instance().add(file, ids, skip_check)


def archive_read(file: str | Path, ids: list[str] | None = None) -> list[str]:
    """
    Read IDs from an archive file with optional filtering (delegates to Archiver).

    Args:
        file (str|Path): The archive file path.
        ids (list[str]|None): Optional list of IDs to query; None/empty returns all.

    Returns:
        list[str]: IDs present in the archive, optionally filtered.

    """
    from app.features.ytdlp.archiver import Archiver

    return Archiver.get_instance().read(file, ids)


def archive_delete(file: str | Path, ids: list[str]) -> bool:
    """
    Delete IDs from an archive file (delegates to Archiver).

    Args:
        file (str|Path): The archive file path.
        ids (list[str]): List of IDs to remove.

    Returns:
        bool: True on success (including no-op), False on error.

    """
    from app.features.ytdlp.archiver import Archiver

    return Archiver.get_instance().delete(file, ids)
