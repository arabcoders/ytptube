import copy
import glob
import ipaddress
import json
import logging
import os
import pathlib
import re
import shlex
import socket
import uuid
from functools import lru_cache
from typing import Any

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget

from .LogWrapper import LogWrapper

LOG = logging.getLogger("Utils")

IGNORED_KEYS: tuple[str] = ("paths", "outtmpl", "progress_hooks", "postprocessor_hooks", "download_archive")
YTDLP_INFO_CLS: yt_dlp.YoutubeDL = None

ALLOWED_SUBS_EXTENSIONS: tuple[str] = (".srt", ".vtt", ".ass")


class StreamingError(Exception):
    """Raised when an error occurs during streaming."""


def get_opts(preset: str, ytdl_opts: dict) -> dict:
    """
    Returns ytdlp options download options

    Args:
      preset (str): the name of the preset selected.
      ytdl_opts (dict): current options selected

    Returns:
      ytdl extra options

    """
    if "format" in ytdl_opts and len(ytdl_opts["format"]) > 2:
        format = ytdl_opts["format"]
        LOG.info(f"Format '{format}' was given via yt-dlp options. Therefore, the preset will be ignored.")
        return ytdl_opts

    opts = copy.deepcopy(ytdl_opts)

    if "default" == preset:
        LOG.debug("Using default preset.")
        return opts

    from .config import Config

    presets = Config.get_instance().presets

    found = False
    for _preset in presets:
        if _preset["name"] == preset:
            found = True
            preset_opts = _preset
            break

    if not found:
        LOG.error(f"Preset '{preset}' is not defined in the presets.")
        return opts

    opts["format"] = preset_opts.get("format")

    if "postprocessors" in preset_opts:
        opts["postprocessors"] = preset_opts["postprocessors"]

    if "args" in preset_opts:
        for key, value in preset_opts["args"].items():
            opts[key] = value

    LOG.debug(f"Using preset '{preset}', altered options: {opts}")
    return opts


def get_video_info(url: str, ytdlp_opts: dict = None, no_archive: bool = True) -> Any | dict[str, Any] | None:
    """
    Extracts video information from the given URL.

    Args:
        url (str): URL to extract information from.
        ytdlp_opts (dict): Additional options to pass to yt-dlp.
        no_archive (bool): Do not use download archive.

    Returns:
        dict: Video information.

    """
    params: dict = {
        "quiet": True,
        "color": "no_color",
        "extract_flat": True,
        "ignoreerrors": True,
        "skip_download": True,
        "ignore_no_formats_error": True,
    }

    if ytdlp_opts:
        params = {**params, **ytdlp_opts}

    if no_archive and "download_archive" in params:
        del params["download_archive"]

    return yt_dlp.YoutubeDL(params=params).extract_info(url, download=False)


def calc_download_path(base_path: str, folder: str | None = None, create_path: bool = True) -> str:
    """
    Calculates download path and prevents folder traversal.

    Returns:
        Download path with base folder factored in.

    """
    if not folder:
        return base_path

    if folder.startswith("/"):
        folder = folder[1:]

    realBasePath = os.path.realpath(base_path)
    download_path = os.path.realpath(os.path.join(base_path, folder))

    if not download_path.startswith(realBasePath):
        msg = f'Folder "{folder}" must resolve inside the base download folder "{realBasePath}".'
        raise Exception(msg)

    if not os.path.isdir(download_path) and create_path:
        os.makedirs(download_path, exist_ok=True)

    return download_path


def extract_info(config: dict, url: str, debug: bool = False) -> dict:
    log_wrapper = LogWrapper()

    params: dict = {
        "color": "no_color",
        "extract_flat": True,
        "skip_download": True,
        "ignoreerrors": True,
        "ignore_no_formats_error": True,
        **config,
    }

    # Remove keys that are not needed for info extraction.
    keys: list = [
        "writeinfojson",
        "writethumbnail",
        "writedescription",
        "writeautomaticsub",
        "postprocessors",
    ]

    for key in keys:
        if key in params:
            params.pop(key)

    log_wrapper.add_target(target=logging.getLogger("yt-dlp"), level=logging.DEBUG if debug else logging.WARNING)
    if debug:
        params["verbose"] = True
    else:
        params["quiet"] = True

    if "callback" in params:
        # callback can be a function or dict with {level: level, func: target}
        if isinstance(params["callback"], dict):
            log_wrapper.add_target(
                target=params["callback"]["func"],
                level=params["callback"]["level"] or logging.ERROR,
            )
        else:
            log_wrapper.add_target(target=params["callback"], level=logging.ERROR)
        del params["callback"]

    if log_wrapper.has_targets():
        if "logger" in params:
            log_wrapper.add_target(target=params["logger"], level=logging.DEBUG)

        params["logger"] = log_wrapper

    return yt_dlp.YoutubeDL(params=params).extract_info(url, download=False)


def merge_dict(source: dict, destination: dict) -> dict:
    """Merge data from source into destination"""
    destination_copy = copy.deepcopy(destination)

    for key, value in source.items():
        destination_key_value = destination_copy.get(key)
        if isinstance(value, dict) and isinstance(destination_key_value, dict):
            destination_copy[key] = merge_dict(source=value, destination=destination_copy.setdefault(key, {}))
        elif isinstance(value, list) and isinstance(destination_key_value, list):
            destination_copy[key] = destination_key_value + value
        else:
            destination_copy[key] = value

    return destination_copy


def merge_config(config: dict, new_config: dict) -> dict:
    """
    Merge user provided config into default config

    Args:
        config (dict): Default config
        new_config (dict): User provided config

    Returns:
        dict: Merged config

    """
    for key in IGNORED_KEYS:
        if key in new_config:
            LOG.error(f"Key '{key}' is not allowed to be manually set via config.")
            del new_config[key]

    conf = merge_dict(new_config, config)

    if "impersonate" in conf:
        conf["impersonate"] = ImpersonateTarget.from_str(conf["impersonate"])

    return conf


def is_downloaded(archive_file: str, url: str) -> tuple[bool, dict[str | None, str | None, str | None]]:
    global YTDLP_INFO_CLS  # noqa: PLW0603

    idDict = {
        "id": None,
        "ie_key": None,
        "archive_id": None,
    }

    if not url or not archive_file or not os.path.exists(archive_file):
        return (
            False,
            idDict,
        )

    if YTDLP_INFO_CLS is None:
        YTDLP_INFO_CLS = yt_dlp.YoutubeDL(
            params={
                "color": "no_color",
                "extract_flat": True,
                "skip_download": True,
                "ignoreerrors": True,
                "ignore_no_formats_error": True,
                "quiet": True,
            }
        )

    for key, ie in YTDLP_INFO_CLS._ies.items():
        if not ie.suitable(url):
            continue

        if not ie.working():
            break

        temp_id = ie.get_temp_id(url)
        if not temp_id:
            break

        idDict["id"] = temp_id
        idDict["ie_key"] = key
        idDict["archive_id"] = YTDLP_INFO_CLS._make_archive_id(idDict)
        break

    if not idDict["archive_id"]:
        return (False, idDict)

    with open(archive_file) as f:
        for line in f:
            if idDict["archive_id"] in line:
                return (True, idDict)

    return (False, idDict)


def load_file(file: str, check_type=None) -> tuple[dict | list, bool, str]:
    """
    Load a JSON or JSON5 file and return the contents as a dictionary

    Args:
        file (str): File path
        check_type (type): Type to check the loaded file against.

    Returns tuple:
        dict|list: Dictionary or list of the file contents. Empty dict if the file could not be loaded.
        bool: True if the file was loaded successfully.
        str: Error message if the file could not be loaded.

    """
    try:
        with open(file) as json_data:
            opts = json.load(json_data)

        if check_type:
            assert isinstance(opts, check_type)  # noqa: S101

        return (
            opts,
            True,
            "",
        )
    except Exception:
        with open(file) as json_data:
            from pyjson5 import load as json5_load

            try:
                opts = json5_load(json_data)

                if check_type:
                    assert isinstance(opts, check_type)  # noqa: S101

                return (
                    opts,
                    True,
                    "",
                )
            except AssertionError:
                return (
                    {},
                    False,
                    f"Failed to assert that the contents '{type(opts)}' are of type '{check_type}'.",
                )
            except Exception as e:
                return (
                    {},
                    False,
                    f"{e}",
                )


def check_id(file: pathlib.Path) -> bool | str:
    """
    Check if we are able to get an id from the file name.
    if so check if any video file with the same id exists.

    :param basePath: Base path to strip.
    :param file: File to check.

    :return: False if no id found, otherwise the id.
    """
    match = re.search(r"(?<=\[)(?:youtube-)?(?P<id>[a-zA-Z0-9\-_]{11})(?=\])", file.stem, re.IGNORECASE)
    if not match:
        return False

    id = match.groupdict().get("id")

    for f in file.parent.iterdir():
        if id not in f.stem:
            continue

        if f.suffix != file.suffix:
            continue

        return f.absolute()

    return False


def get_value(value):
    return value() if callable(value) else value


def ag(array: dict | list, path: list[str | int] | str | int, default: Any = None, separator: str = ".") -> Any:
    """
    dict/array getter: Retrieve a value from a nested dict or object using a path.

    :param array_or_object: dict-like or object from which to retrieve values
    :param path: string, list, or None. Represents the path to retrieve:
                 - If None or empty string, returns the entire structure.
                 - If list, tries each path and returns the first found.
                 - If string, navigates through nested dict keys separated by `separator`.
    :param default: Value (or callable) returned if nothing is found.
    :param separator: Separator for nested paths in strings.
    :return: The found value or the default if not found.
    """
    if path is None or path == "":
        return array

    if not isinstance(array, dict):
        try:
            array = vars(array)
        except TypeError:
            array = dict(array)

    if isinstance(path, list):
        randomValue = str(uuid.uuid4())
        for key in path:
            val = ag(array, key, randomValue, separator)
            if val != randomValue:
                return val

        return get_value(default)

    if path in array and array[path] is not None:
        return array[path]

    if separator not in path:
        return array.get(path, get_value(default))

    keys = path.split(separator)
    current = array

    for segment in keys:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return get_value(default)

    return current


@lru_cache(maxsize=512)
def is_private_address(hostname: str) -> bool:
    try:
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local
    except socket.gaierror:
        # Could not resolve - treat as invalid or restricted
        return True


def validate_url(url: str) -> bool:
    """
    Validate if the url is valid and allowed.

    Args:
        url (str): URL to validate.

    Raises:
        ValueError: If the URL is invalid or not allowed.

    Returns:
        bool: True if the URL is valid and allowed.

    """
    if not url:
        msg = "URL is required."
        raise ValueError(msg)

    try:
        from yarl import URL

        parsed_url = URL(url)
    except ValueError:
        msg = "Invalid URL."
        raise ValueError(msg)  # noqa: B904

    # Check allowed schemes
    if parsed_url.scheme not in ["http", "https"]:
        msg = "Invalid scheme usage. Only HTTP or HTTPS allowed."
        raise ValueError(msg)

    hostname = parsed_url.host
    if not hostname or is_private_address(hostname):
        msg = "Access to internal urls or private networks is not allowed."
        raise ValueError(msg)

    return True


def arg_converter(args: str) -> dict:
    """
    Convert yt-dlp options to a dictionary.

    Args:
        args (str): yt-dlp options string.

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

    default_opts = _default_opts([]).ydl_opts

    opts = yt_dlp.parse_options(shlex.split(args)).ydl_opts

    diff = {k: v for k, v in opts.items() if default_opts[k] != v}
    if "postprocessors" in diff:
        diff["postprocessors"] = [pp for pp in diff["postprocessors"] if pp not in default_opts["postprocessors"]]

    return json.loads(json.dumps(diff))


def validate_uuid(uuid_str: str, version: int = 4) -> bool:
    """
    Validate if the UUID is valid.

    Args:
        uuid_str (str): UUID to validate.
        version  (int): The UUID version

    Returns:
        bool: True if the UUID is valid.

    """
    try:
        uuid.UUID(uuid_str, version=version)
        return True
    except ValueError:
        return False


def get_sidecar_subtitles(file: pathlib.Path) -> list[dict]:
    """
    Get sidecar files for the given file.

    :param file: File to get sidecar files for.
    :return: List of sidecar files.
    """
    files = []

    for i, f in enumerate(file.parent.glob(f"{glob.escape(file.stem)}.*")):
        if f == file or f.is_file() is False or f.stem.startswith("."):
            continue

        if f.suffix not in ALLOWED_SUBS_EXTENSIONS:
            continue

        if f.stat().st_size < 1:
            continue

        lg = re.search(r"\.(?P<lang>\w{2,3})\.\w{3}$", f.name)
        lang = lg.groupdict().get("lang") if lg else "und"

        files.append({"file": f, "lang": lang, "name": f"{f.suffix[1:].upper()} ({i}) - {lang}"})

    return files


def get_mime_type(metadata: dict, file_path: pathlib.Path) -> str:
    """
    Determine the correct MIME type for a video file based on ffprobe metadata.

    Args:
        metadata (dict): Parsed JSON output from ffprobe.
        file_path (str): The path to the video file for fallback detection.

    Returns:
        str: MIME type compatible with HTML5 <video> tag.

    """
    # Extract format name from ffprobe
    format_name = metadata.get("format_name", "")

    # Define mappings for HTML5-compatible video types
    format_to_mime = {
        "matroska": "video/x-matroska",  # Default for MKV
        "webm": "video/webm",  # MKV can also be WebM
        "mp4": "video/mp4",
        "mpegts": "video/mp2t",
    }

    # Check format_name against known formats
    if format_name:
        selected = None
        for fmt in format_name.split(","):
            fmt = fmt.strip().lower()
            if fmt in format_to_mime:
                selected = format_to_mime[fmt]

        if selected:
            return selected

    # Fallback: Use Python's mimetypes module
    import mimetypes

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        return mime_type

    # Final fallback: Return generic binary type
    return "application/octet-stream"


def get_file(download_path: str, file: str | pathlib.Path) -> tuple[pathlib.Path, int]:
    """
    Get the real file path.

    Args:
        download_path (str): Base download path.
        file (str|pathlib.Path): File path.

    Returns:
        pathlib.Path: Real file path.
        int: http status code.

    """
    file_path: str = os.path.normpath(os.path.join(download_path, str(file)))
    if not file_path.startswith(download_path):
        return (pathlib.Path(file_path), 404)

    realFile: str = pathlib.Path(calc_download_path(base_path=str(download_path), folder=str(file), create_path=False))
    if realFile.exists():
        return (realFile, 200)

    possibleFile = check_id(file=realFile)
    if not possibleFile:
        return (realFile, 404)

    return (pathlib.Path(possibleFile), 302)
