import base64
import copy
import glob
import ipaddress
import json
import logging
import os
import re
import shlex
import socket
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import TypeVar

from Crypto.Cipher import AES
from yt_dlp.utils import age_restricted, match_str

from .LogWrapper import LogWrapper
from .ytdlp import YTDLP

LOG: logging.Logger = logging.getLogger("Utils")

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
        "forcejson": "-j, --dump-json",
    },
]

YTDLP_INFO_CLS: YTDLP = None

ALLOWED_SUBS_EXTENSIONS: tuple[str] = (".srt", ".vtt", ".ass")

FILES_TYPE: list = [
    {"rx": re.compile(r"\.(avi|ts|mkv|mp4|mp3|mpv|ogm|m4v|webm|m4b)$", re.IGNORECASE), "type": "video"},
    {"rx": re.compile(r"\.(mp3|flac|aac|opus|wav|m4a)$", re.IGNORECASE), "type": "audio"},
    {"rx": re.compile(r"\.(srt|ass|ssa|smi|sub|idx)$", re.IGNORECASE), "type": "subtitle"},
    {"rx": re.compile(r"\.(jpg|jpeg|png|gif|bmp|webp)$", re.IGNORECASE), "type": "image"},
    {"rx": re.compile(r"\.(txt|nfo|md|json|yml|yaml|plexmatch)$", re.IGNORECASE), "type": "text"},
    {"rx": re.compile(r"\.(nfo|json|jpg|torrent|\.info\.json)$", re.IGNORECASE), "type": "metadata"},
]

TAG_REGEX: re.Pattern[str] = re.compile(r"%{([^:}]+)(?::([^}]*))?}c")
DT_PATTERN: re.Pattern[str] = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}))\s?")

T = TypeVar("T")


class StreamingError(Exception):
    """Raised when an error occurs during streaming."""


class FileLogFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):  # noqa: ARG002, N802
        return datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="milliseconds")


def calc_download_path(base_path: str | Path, folder: str | None = None, create_path: bool = True) -> str:
    """
    Calculates download path and prevents folder traversal.

    Args:
        base_path (str): Base download path.
        folder (str): Folder to add to the base path.
        create_path (bool): Create the path if it does not exist.

    Returns:
        Download path with base folder factored in.

    """
    if not isinstance(base_path, Path):
        base_path = Path(base_path)

    if not folder:
        return str(base_path)

    folder = folder.removeprefix("/")

    realBasePath = base_path.resolve()
    download_path = Path(realBasePath).joinpath(folder).resolve(strict=False)

    if not str(download_path).startswith(str(realBasePath)):
        msg = f'Folder "{folder}" must resolve inside the base download folder "{realBasePath}".'
        raise Exception(msg)

    try:
        download_path.relative_to(realBasePath)
    except ValueError as e:
        msg = f'Folder "{folder}" must resolve inside the base download folder "{realBasePath}".'
        raise Exception(msg) from e

    if not download_path.is_dir() and create_path:
        download_path.mkdir(parents=True, exist_ok=True)

    return str(download_path)


def extract_info(
    config: dict,
    url: str,
    debug: bool = False,
    no_archive: bool = False,
    follow_redirect: bool = False,
    sanitize_info: bool = False,
    **kwargs,  # noqa: ARG001
) -> dict:
    """
    Extracts video information from the given URL.

    Args:
        config (dict): Configuration options.
        url (str): URL to extract information from.
        debug (bool): Enable debug logging.
        no_archive (bool): Disable download archive.
        follow_redirect (bool): Follow URL redirects.
        sanitize_info (bool): Sanitize the extracted information
        **kwargs: Additional arguments.

    Returns:
        dict: Video information.

    """
    params: dict = {
        **config,
        "color": "no_color",
        "extract_flat": True,
        "skip_download": True,
        "ignoreerrors": True,
        "ignore_no_formats_error": True,
    }

    # Remove keys that are not needed for info extraction.
    keys_to_remove = [key for key in params if str(key).startswith("write") or key in ["postprocessors"]]
    for key in keys_to_remove:
        params.pop(key, None)

    if debug:
        params["verbose"] = True
    else:
        params["quiet"] = True

    log_wrapper = LogWrapper()
    idDict = get_archive_id(url=url)
    archive_id = f".{idDict['id']}" if idDict.get("id") else None

    log_wrapper.add_target(
        target=logging.getLogger(f"yt-dlp{archive_id if archive_id else '.extract_info'}"),
        level=logging.DEBUG if debug else logging.WARNING,
    )

    if "callback" in params:
        if isinstance(params["callback"], dict):
            log_wrapper.add_target(
                target=params["callback"]["func"],
                level=params["callback"]["level"] or logging.ERROR,
                name=params["callback"]["name"] or "callback",
            )
        else:
            log_wrapper.add_target(target=params["callback"], level=logging.ERROR, name="callback")

        params.pop("callback", None)

    if log_wrapper.has_targets():
        if "logger" in params:
            log_wrapper.add_target(target=params["logger"], level=logging.DEBUG)

        params["logger"] = log_wrapper

    if no_archive and "download_archive" in params:
        del params["download_archive"]

    data = YTDLP(params=params).extract_info(url, download=False)

    if data and follow_redirect and "_type" in data and "url" == data["_type"]:
        return extract_info(
            config,
            data["url"],
            debug=debug,
            no_archive=no_archive,
            follow_redirect=follow_redirect,
            sanitize_info=sanitize_info,
        )

    if not data:
        return data

    data["is_premiere"] = match_str("media_type=video & duration & is_live", data)
    if not data["is_premiere"]:
        data["is_premiere"] = "video" == data.get("media_type") and "is_upcoming" == data.get("live_status")

    return YTDLP.sanitize_info(data) if sanitize_info else data


def merge_dict(source: dict, destination: dict) -> dict:
    """
    Merge data from source into destination safely.

    Args:
        source (dict): Source data
        destination (dict): Destination data

    Returns:
        dict: The merged dictionary

    """
    if not isinstance(source, dict) or not isinstance(destination, dict):
        msg = "Both source and destination must be dictionaries."
        raise TypeError(msg)

    destination_copy = copy.deepcopy(destination)

    for key, value in source.items():
        if key in {"__class__", "__dict__", "__globals__", "__builtins__"}:
            continue

        destination_value = destination_copy.get(key)

        # Recursively merge dictionaries
        if isinstance(value, dict) and isinstance(destination_value, dict):
            destination_copy[key] = merge_dict(value, destination_value)

        # Safely extend lists without reference issues
        elif isinstance(value, list) and isinstance(destination_value, list):
            destination_copy[key] = copy.deepcopy(destination_value) + copy.deepcopy(value)

        else:
            destination_copy[key] = copy.deepcopy(value)

    return destination_copy


def is_downloaded(archive_file: str, url: str) -> tuple[bool, dict[str | None, str | None, str | None]]:
    """
    Check if the video is already downloaded.

    Args:
        archive_file (str): Archive file path.
        url (str): URL to check.

    Returns:
        bool: True if the video is already downloaded.
        dict: Video information.

    """
    idDict = {"id": None, "ie_key": None, "archive_id": None}

    if not url or not archive_file:
        return (False, idDict)

    if not Path(archive_file).exists():
        return (False, idDict)

    idDict = get_archive_id(url=url)

    if idDict.get("archive_id"):
        with open(archive_file) as f:
            for line in f:
                if idDict["archive_id"] in line:
                    return (True, idDict)

    return (False, idDict)


def remove_from_archive(archive_file: str | Path, url: str) -> bool:
    """
    Remove the downloaded video record from the archive file.

    Args:
        archive_file (str): Archive file path.
        url (str): URL to check and remove.

    Returns:
        bool: True if the record removed, False otherwise.

    """
    if not url or not archive_file:
        return False

    archive_path: Path = Path(archive_file) if not isinstance(archive_file, Path) else archive_file
    if not archive_path.exists():
        return False

    idDict = get_archive_id(url=url)
    archive_id: str | None = idDict.get("archive_id")

    if not archive_id:
        return False

    lines: list[str] = archive_path.read_text(encoding="utf-8").splitlines()
    new_lines: list[str] = [line for line in lines if archive_id not in line]

    if len(lines) == len(new_lines):
        return False

    archive_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


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
            assert isinstance(opts, check_type)

        return (opts, True, "")
    except Exception:
        with open(file) as json_data:
            from pyjson5 import load as json5_load

            try:
                opts = json5_load(json_data)

                if check_type:
                    assert isinstance(opts, check_type)

                return (opts, True, "")
            except AssertionError:
                return ({}, False, f"Failed to assert that the contents '{type(opts)}' are of type '{check_type}'.")
            except Exception as e:
                return ({}, False, f"{e}")


def check_id(file: Path) -> bool | str:
    """
    Check if we are able to get an id from the file name.
    if so check if any video file with the same id exists.

    Args:
        file (Path): File to check.

    Returns:
        bool|str: False if no file found, else the file path.

    """
    match = re.search(r"(?<=\[)(?:youtube-)?(?P<id>[a-zA-Z0-9\-_]{11})(?=\])", file.stem, re.IGNORECASE)
    if not match:
        return False

    id = match.groupdict().get("id")

    try:
        for f in file.parent.iterdir():
            if id not in f.stem:
                continue

            if f.suffix != file.suffix:
                continue

            return f.absolute()
    except OSError as e:
        LOG.error(f"Error checking file '{file}': {e!s}")
        return False

    return False


@lru_cache(maxsize=512)
def is_private_address(hostname: str) -> bool:
    try:
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local
    except socket.gaierror:
        # Could not resolve - treat as invalid or restricted
        return True


def validate_url(url: str, allow_internal: bool = False) -> bool:
    """
    Validate if the url is valid and allowed.

    Args:
        url (str): URL to validate.
        allow_internal (bool): If True, allow internal URLs or private networks.

    Returns:
        bool: True if the URL is valid and allowed.

    Raises:
        ValueError: If the URL is invalid or not allowed.

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

    hostname: str | None = parsed_url.host
    if allow_internal is False and (not hostname or is_private_address(hostname)):
        msg = "Access to internal urls or private networks is not allowed."
        raise ValueError(msg)

    return True


def arg_converter(
    args: str,
    level: int | bool | None = None,
    dumps: bool = False,
    removed_options: list | None = None,
) -> dict:
    """
    Convert yt-dlp options to a dictionary.

    Args:
        args (str): yt-dlp options string.
        level (int|bool|None): Level of options to remove, True for all.
        dumps (bool): Dump options as JSON.
        removed_options (list|None): List of removed options.

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

    if "_warnings" in diff:
        diff.pop("_warnings", None)

    if level is True or isinstance(level, int):
        bad_options = {}
        if isinstance(level, bool) or not isinstance(level, int):
            level = len(REMOVE_KEYS)

        for i, item in enumerate(REMOVE_KEYS):
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
        from .encoder import Encoder

        if "match_filter" in diff:
            import inspect

            matchFilter = inspect.getclosurevars(diff["match_filter"].func).nonlocals["filters"]
            if isinstance(matchFilter, set):
                diff["match_filter"] = {"filters": list(matchFilter)}

        return json.loads(json.dumps(diff, cls=Encoder, default=str))

    return diff


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


def get_file_sidecar(file: Path) -> list[dict]:
    """
    Get sidecar files for the given file.

    Args:
        file (Path): The video file.

    Returns:
        list: List of sidecar files.

    """
    files = {}

    for i, f in enumerate(file.parent.glob(f"{glob.escape(file.stem)}.*")):
        if f == file or f.is_file() is False or f.stem.startswith("."):
            continue

        if f.stat().st_size < 1:
            continue

        content_type = "Unknown"
        for pattern in FILES_TYPE:
            if pattern["rx"].search(f.name):
                content_type = pattern["type"]
                break

        if content_type == "subtitle":
            if f.suffix not in ALLOWED_SUBS_EXTENSIONS:
                continue
            lg = re.search(r"\.(?P<lang>\w{2,3})\.\w{3}$", f.name)
            lang = lg.groupdict().get("lang") if lg else "und"
            content = {"file": f, "lang": lang, "name": f"{f.suffix[1:].upper()} ({i}) - {lang}"}
        else:
            content = {"file": f}

        if content_type not in files:
            files[content_type] = []

        files[content_type].append(content)

    images = get_possible_images(str(file.parent))
    if len(images) > 0:
        if "image" not in files:
            files["image"] = []

        files["image"].extend(images)

    return files


@lru_cache(maxsize=512)
def get_possible_images(dir: str) -> list[dict]:
    images = []

    path_loc = Path(dir, "test.jpg")

    for filename in ["poster", "thumbnail", "artwork", "cover", "fanart"]:
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            f = path_loc.with_stem(filename).with_suffix(ext)
            if f.exists():
                images.append({"file": f})

    return images


def get_mime_type(metadata: dict, file_path: Path) -> str:
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


def get_file(download_path: str | Path, file: str | Path) -> tuple[Path, int]:
    """
    Get the real file path.

    Args:
        download_path (str|Path): Base download path.
        file (str|Path): File path.

    Returns:
        Path: Real file path.
        int: http status code.

    """
    if not isinstance(download_path, Path):
        download_path = Path(download_path)

    try:
        realFile: str = Path(calc_download_path(base_path=download_path, folder=str(file), create_path=False))
        if realFile.exists():
            return (realFile, 200)
    except Exception as e:
        LOG.error(f"Error calculating download path. {e!s}")
        return (Path(file), 404)

    possibleFile = check_id(file=realFile)
    if not possibleFile:
        return (realFile, 404)

    return (Path(possibleFile), 302)


def encrypt_data(data: str, key: bytes) -> str:
    """
    Encrypts data using AES-GCM

    Args:
        data (str): The data to encrypt
        key (bytes): The encryption key

    Returns:
        str: The encrypted data as a base64 encoded string

    """
    iv = os.urandom(12)  # AES-GCM requires a 12-byte IV
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(data.encode())

    return base64.urlsafe_b64encode(iv + ciphertext + tag).decode()


def decrypt_data(data: str, key: bytes) -> str:
    """
    Decrypts AES-GCM encrypted data

    Args:
        data (str): The encrypted data as a base64 encoded string
        key (bytes): The encryption key

    Returns:
        str: The decrypted data

    """
    try:
        data = base64.urlsafe_b64decode(data)
        iv, ciphertext, tag = data[:12], data[12:-16], data[-16:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode()
    except Exception:
        return None


def get(
    data: dict | list,
    path: str | list | None = None,
    default: any = None,
    separator=".",
):
    """
    Access data in a nested dictionary or list using a path string or list of keys.

    Args:
        data (dict | list): The data to traverse.
        path (str | list, optional): The path to the desired data. Defaults to None.
        default (any, optional): The default value to return if the path is not found. Defaults to None.
        separator (str, optional): The separator used to split the path string. Defaults to ".".

    Returns:
        any: The value at the specified path, or the default value if not found.

    """
    # If path is empty, return the entire data.
    if not path:
        return data

    # If data is not a dict or list, attempt to convert it.
    if not isinstance(data, dict | list):
        try:
            data = vars(data)
        except Exception:
            pass

    # If path is a list, try each key in order.
    if isinstance(path, list):
        for key in path:
            val = get(data, key, "__not_set", separator)
            if val != "__not_set":
                return val

        return default() if callable(default) else default

    # For non-list path, attempt a direct lookup.
    if isinstance(data, dict):
        if path in data and data[path] is not None:
            return data[path]
    elif isinstance(data, list):
        # If path is an integer index.
        if isinstance(path, int):
            if 0 <= path < len(data) and data[path] is not None:
                return data[path]
        # If path is a numeric string, convert it.
        elif isinstance(path, str) and path.isdigit():
            idx = int(path)
            if 0 <= idx < len(data) and data[idx] is not None:
                return data[idx]

    # If path doesn't contain the separator, return the default.
    if not (isinstance(path, str) and separator in path):
        return default() if callable(default) else default

    # Split the path by the separator and traverse the data structure.
    segments = path.split(separator)
    for segment in segments:
        if isinstance(data, dict):
            if segment in data:
                data = data[segment]
            else:
                return default() if callable(default) else default
        elif isinstance(data, list):
            try:
                idx = int(segment)
            except ValueError:
                return default() if callable(default) else default
            if 0 <= idx < len(data):
                data = data[idx]
            else:
                return default() if callable(default) else default
        else:
            return default() if callable(default) else default
    return data


def get_files(base_path: Path | str, dir: str | None = None):
    """
    Get directory contents.

    Args:
        base_path (Path|str): Base download path.
        dir (str): Directory to check.

    Returns:
        list: List of files and directories.

    Raises:
        OSError: If the directory is invalid or not a directory.

    """
    if not isinstance(base_path, Path):
        base_path = Path(base_path)

    base_path = base_path.resolve()

    dir_path = base_path
    if dir and dir != "/":
        dir_path: Path = base_path.joinpath(dir)

    try:
        dir_path = dir_path.resolve()
    except OSError as e:
        LOG.warning(f"Failed to resolve '{dir}' - {e}")
        return []

    try:
        dir_path.relative_to(base_path)
    except ValueError:
        LOG.warning(f"Invalid path: '{dir_path}' - must be inside '{base_path}'.")
        return []

    if not str(dir_path).startswith(str(base_path)):
        LOG.warning(f"Invalid path: '{dir_path}' - must be inside '{base_path}'.")
        return []

    if not dir_path.is_dir():
        LOG.warning(f"Invalid path: '{dir_path}' - must be a directory.")
        return []

    contents: list = []
    for file in dir_path.iterdir():
        if file.name.startswith(".") or file.name.startswith("_"):
            continue

        is_symlink: bool = file.is_symlink()
        if is_symlink:
            try:
                test: Path = file.resolve()
                test.relative_to(base_path)
                if not str(test).startswith(str(base_path)):
                    LOG.warning(f"Invalid symlink: '{file}' - must resolve inside '{base_path}'.")
                    continue
            except ValueError:
                LOG.warning(f"Invalid symlink: '{file}' - must resolve inside '{base_path}'.")
                continue
            except OSError:
                LOG.warning(f"Skipping broken symlink: {file}")
                continue

        content_type = None

        for pattern in FILES_TYPE:
            if pattern["rx"].search(file.name):
                content_type = pattern["type"]
                break

        if not content_type and file.is_dir():
            content_type = "dir"

        if not content_type:
            content_type = "download"

        stat = file.stat()

        contents.append(
            {
                "type": "file" if file.is_file() else "link" if is_symlink else "dir",
                "content_type": content_type,
                "name": file.name,
                "path": str(file.relative_to(base_path)).strip("/"),
                "size": stat.st_size,
                "mime": get_mime_type({}, file) if file.is_file() else "directory",
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                "ctime": datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat(),
                "is_dir": file.is_dir(),
                "is_file": file.is_file(),
                "is_symlink": is_symlink,
            }
        )

    return contents


def clean_item(item: dict, keys: list | tuple) -> tuple[dict, bool]:
    """
    Remove given keys from a dictionary.
    This function modifies the dictionary in place and returns a tuple
    containing the modified dictionary and a boolean indicating
    whether any keys were removed.

    Args:
        item (dict): The item to clean.
        keys (list|tuple): The keys to remove.

    Returns:
        tuple[dict, bool]: The cleaned item and a the status of cleaning operation.

    Raises:
        TypeError: If item is not a dictionary or keys is not a list or tuple.

    """
    status = False

    if not isinstance(item, dict):
        msg = "Item must be a dictionary."
        raise TypeError(msg)

    if not isinstance(keys, list | tuple):
        msg = "Keys must be a list or tuple."
        raise TypeError(msg)

    for key in keys:
        if key not in item:
            continue

        status = True
        item.pop(key)

    return item, status


def strip_newline(string: str) -> str:
    """
    Remove newlines from a string.

    Args:
        string (str): The string to process.

    Returns:
        str: The string without newlines.

    """
    if not string:
        return ""

    res = re.sub(r"(\r\n|\r|\n)", " ", string)

    return res.strip() if res else ""


async def read_logfile(file: Path, offset: int = 0, limit: int = 50) -> dict:
    """
    Read a log file and return a set of log lines along with pagination metadata.

    Args:
        file (Path): The log file path.
        offset (int): Number of lines to skip from the end (newer entries).
        limit (int): Number of lines to return.

    Returns:
        dict: A dictionary containing:
            - logs: List of log entries.
            - next_offset: Offset for the next page or None.
            - end_is_reached: True if there are no older logs.

    """
    from hashlib import sha256

    from anyio import open_file

    if not file.exists():
        return {"logs": [], "next_offset": None, "end_is_reached": True}

    result = []
    try:
        async with await open_file(file, "rb") as f:
            await f.seek(0, os.SEEK_END)
            file_size = await f.tell()

            block_size = 1024
            block_end = file_size
            buffer = b""
            lines = []

            required_count = offset + limit + 1

            while len(lines) < required_count and block_end > 0:
                block_start = max(0, block_end - block_size)
                await f.seek(block_start)
                chunk = await f.read(block_end - block_start)
                buffer = chunk + buffer  # prepend the chunk
                lines = buffer.splitlines()
                block_end = block_start

            if len(lines) > offset + limit:
                next_offset = offset + limit
                end_is_reached = False
            else:
                next_offset = None
                end_is_reached = True

            for line in lines[-(offset + limit) : -offset] if offset else lines[-limit:]:
                line_bytes = line if isinstance(line, bytes) else line.encode()
                msg = line.decode(errors="replace")
                dt_match = DT_PATTERN.match(msg)
                result.append(
                    {
                        "id": sha256(line_bytes).hexdigest(),
                        "line": msg[dt_match.end() :] if dt_match else msg,
                        "datetime": dt_match.group(1) if dt_match else None,
                    }
                )

            return {"logs": result, "next_offset": next_offset, "end_is_reached": end_is_reached}
    except Exception:
        return {"logs": [], "next_offset": None, "end_is_reached": True}


async def tail_log(file: Path, emitter: callable, sleep_time: float = 0.5):
    """
    Continuously read a log file and emit new lines.

    Args:
        file (str): The log file path.
        emitter (callable): A callable to emit new lines.
        sleep_time (float): The time to sleep between reads.

    """
    from asyncio import sleep as asyncio_sleep
    from hashlib import sha256

    from anyio import open_file

    if not file.exists():
        return

    try:
        async with await open_file(file, "rb") as f:
            await f.seek(0, os.SEEK_END)
            while True:
                line = await f.readline()
                if not line:
                    await asyncio_sleep(sleep_time)
                    continue

                msg = line.decode(errors="replace")
                dt_match = DT_PATTERN.match(msg)

                await emitter(
                    {
                        "id": sha256(line if isinstance(line, bytes) else line.encode()).hexdigest(),
                        "line": msg[dt_match.end() :] if dt_match else msg,
                        "datetime": dt_match.group(1) if dt_match else None,
                    }
                )
    except Exception as e:
        LOG.error(f"Error while tailing log file '{file!s}': {e!s}")
        return


def load_cookies(file: str | Path) -> tuple[bool, MozillaCookieJar]:
    """
    Validate and load a cookie file.

    Args:
        file (str): The cookie file path.

    Returns:
        bool: True if the cookie file is valid.

    """
    try:
        from http.cookiejar import MozillaCookieJar

        cookies = MozillaCookieJar(str(file), None, None)
        cookies.load()

        return (True, cookies)
    except Exception as e:
        msg = f"Invalid cookie file '{file}'. '{e!s}'"
        raise ValueError(msg) from e


def get_archive_id(url: str) -> tuple[bool, dict[str | None, str | None, str | None]]:
    """
    Get the archive ID for a given URL.

    Args:
        url (str): URL to check.

    Returns:
        bool: True if the video is already downloaded.
        dict: Video information.

    """
    global YTDLP_INFO_CLS  # noqa: PLW0603

    idDict = {
        "id": None,
        "ie_key": None,
        "archive_id": None,
    }

    if YTDLP_INFO_CLS is None:
        YTDLP_INFO_CLS = YTDLP(
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
        try:
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
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Error getting archive ID: {e}")

    return idDict


def dt_delta(delta: timedelta) -> str:
    """
    Convert a timedelta object to a human-readable string.

    Args:
        delta (timedelta): The timedelta object.

    Returns:
        str: A human-readable string representing the timedelta.

    """
    total_secs = int(delta.total_seconds())
    days, rem = divmod(total_secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")

    # if it's under one second
    if not parts:
        parts.append("<1s")

    return " ".join(parts)


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


def delete_dir(dir: Path) -> bool:
    """
    Delete a directory and all its contents.

    Args:
        dir (Path): The directory to delete.

    Returns:
        bool: True if the directory was deleted successfully, False otherwise.

    """
    if not dir or not dir.exists() or not dir.is_dir():
        return False

    try:
        for item in dir.iterdir():
            if item.is_dir():
                delete_dir(item)
            else:
                item.unlink()
        dir.rmdir()
        return True
    except Exception as e:
        LOG.error(f"Failed to delete directory '{dir}': {e}")
        return False


def init_class(cls: type[T], data: dict) -> T:
    """
    Initialize a class instance with data from a dictionary, filtering out keys not present in the class fields.

    Args:
        cls (type): The class to initialize.
        data (dict): The data to use for initialization.

    Returns:
        T: An instance of the class initialized with the provided data.

    """
    from dataclasses import fields

    return cls(**{k: v for k, v in data.items() if k in {f.name for f in fields(cls)}})


def load_modules(root_path: Path, directory: Path):
    """
    Load all modules from a given directory relative to the root path.

    Args:
        root_path (Path): The root path of the application.
        directory (Path): The directory from which to load modules.

    """
    import importlib
    import pkgutil

    package_name: str = str(directory.relative_to(root_path).as_posix()).replace("/", ".")

    LOG.debug(f"Loading routes from '{directory}' with package name '{package_name}'.")

    for _, name, _ in pkgutil.iter_modules([directory]):
        full_name: str = f"{package_name}.{name}"
        if name.startswith("_"):
            continue
        try:
            LOG.debug(f"Loading module '{full_name}'.")
            importlib.import_module(full_name)
        except ImportError as e:
            LOG.error(f"Failed to import module '{full_name}': {e}")


def parse_tags(text: str) -> tuple[str, dict[str, str | bool]]:
    """
    Parse tags from a string formatted with %{tag_name[:value]}c.

    Args:
        text (str): The input string containing tags.

    Returns:
        tuple[str, dict[str, str | bool]]: A tuple containing the string with tags removed and a dictionary of tags.

    """
    tags: dict[str, str | bool] = {}

    def replacer(match: re.Match) -> str:
        name = match.group(1)
        value = match.group(2)
        tags[name] = value if value is not None else True
        return ""

    return TAG_REGEX.sub(replacer, text).strip(), tags


def str_to_dt(time_str: str, now=None) -> datetime:
    """
    Convert a string representation of time into a datetime object.

    Args:
        time_str (str): The string representation of time.
        now (datetime, optional): The base datetime to use for relative times. Defaults to None, which uses the current UTC time.

    Returns:
        datetime: A datetime object representing the parsed time.

    Raises:
        ValueError: If the time string cannot be parsed.

    """
    from dateparser import parse as _parse

    dt = _parse(
        time_str,
        settings={
            "RELATIVE_BASE": now or datetime.now(tz=UTC),
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TO_TIMEZONE": "UTC",
        },
    )

    if dt is None:
        msg = f"Couldn't parse date: {time_str!r}"
        raise ValueError(msg)

    return dt


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

    if entry.get("age_limit") and age_restricted(entry.get("age_limit"), yt_params.get("age_limit")):
        return (False, f'Video "{entry.get("title", "unknown")}" is age restricted.')

    return (True, "")


def find_unpickleable(obj, name="root", seen=None):
    import pickle

    if seen is None:
        seen = set()

    if id(obj) in seen:
        return

    seen.add(id(obj))

    try:
        pickle.dumps(obj)
    except Exception as e:
        LOG.error(f"[UNPICKLEABLE] {name}: {e}")

        if isinstance(obj, dict):
            for k, v in obj.items():
                find_unpickleable(v, f"{name}[{repr(k)!s}]", seen)
        elif hasattr(obj, "__dict__"):
            for attr in vars(obj):
                try:
                    value = getattr(obj, attr)
                    find_unpickleable(value, f"{name}.{attr}", seen)
                except Exception as ie:
                    LOG.error(f"[ERROR] Accessing {name}.{attr}: {ie}")
        elif isinstance(obj, list | tuple | set):
            for idx, item in enumerate(obj):
                find_unpickleable(item, f"{name}[{idx}]", seen)


def list_folders(path: Path, base: Path, depth_limit: int) -> list[str]:
    """
    List all folders relative to a base path, up to a specified depth limit.

    Args:
        path (Path): The path to start listing folders from.
        base (Path): The base path to which the folders should be relative.
        depth_limit (int): The maximum depth to traverse from the base path.

    Returns:
        list[str]: A list of folder paths relative to the base path, up to the specified

    """
    rel_depth: int = len(path.relative_to(base).parts)
    if rel_depth > depth_limit:
        return []

    folders: list[str] = []
    for entry in path.iterdir():
        if entry.is_dir():
            folders.append(str(entry.relative_to(base)))
            folders.extend(list_folders(entry, base, depth_limit))

    return folders
