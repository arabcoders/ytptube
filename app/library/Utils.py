import base64
import copy
import datetime
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
from Crypto.Cipher import AES

from .LogWrapper import LogWrapper

LOG = logging.getLogger("Utils")

REMOVE_KEYS: list = [
    {
        "paths": "-P, --paths",
        "outtmpl": "-o, --output",
        "progress_hooks": "--progress_hooks",
        "postprocessor_hooks": "--postprocessor_hooks",
        "post_hooks": "--post_hooks",
        "download_archive": "--download_archive",
    },
    {
        "quiet": "-q, --quiet",
        "no_warnings": "--no-warnings",
        "skip_download": "--skip-download",
        "forceprint": "-O, --print",
        "simulate": "--simulate",
        "noprogress": "--no-progress",
        "wait_for_video": "--wait-for-video",
        "mark_watched": "--mark-watched",
        "color": "--color",
        "verbose": "-v, --verbose",
        "debug_printtraffic": "--print-traffic",
        "write_pages": "--write-pages",
        "dump_intermediate_pages": "--dump-pages",
        "progress_delta": " --progress-delta",
        "progress_template": "--progress-template",
        "consoletitle": "--console-title",
        "progress_with_newline": "--newline",
        "forcejson": "-j, --dump-json",
        "print_to_file": "--print-to-file",
        "cookiesfrombrowser": "--cookies-from-browser",
    },
    {
        "cookiefile": "--cookies",
    },
]

YTDLP_INFO_CLS: yt_dlp.YoutubeDL = None

ALLOWED_SUBS_EXTENSIONS: tuple[str] = (".srt", ".vtt", ".ass")

FILES_TYPE: list = [
    {"rx": re.compile(r"\.(avi|ts|mkv|mp4|mp3|mpv|ogm|m4v|webm|m4b)$", re.IGNORECASE), "type": "video"},
    {"rx": re.compile(r"\.(mp3|flac|aac|opus|wav|m4a)$", re.IGNORECASE), "type": "audio"},
    {"rx": re.compile(r"\.(srt|ass|ssa|smi|sub|idx)$", re.IGNORECASE), "type": "subtitle"},
    {"rx": re.compile(r"\.(jpg|jpeg|png|gif|bmp|webp)$", re.IGNORECASE), "type": "image"},
    {"rx": re.compile(r"\.(txt|nfo|md|json|yml|yaml|plexmatch)$", re.IGNORECASE), "type": "text"},
    {"rx": re.compile(r"\.(nfo|json|jpg|torrent|\.info\.json)$", re.IGNORECASE), "type": "metadata"},
]


class StreamingError(Exception):
    """Raised when an error occurs during streaming."""


def calc_download_path(base_path: str, folder: str | None = None, create_path: bool = True) -> str:
    """
    Calculates download path and prevents folder traversal.

    Args:
        base_path (str): Base download path.
        folder (str): Folder to add to the base path.
        create_path (bool): Create the path if it does not exist.

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


def extract_info(
    config: dict,
    url: str,
    debug: bool = False,
    no_archive: bool = False,
    follow_redirect: bool = False,
    sanitize_info: bool = False,
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

    Returns:
        dict: Video information.

    """
    log_wrapper = LogWrapper()

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

    log_wrapper.add_target(target=logging.getLogger("yt-dlp"), level=logging.DEBUG if debug else logging.WARNING)
    if debug:
        params["verbose"] = True
    else:
        params["quiet"] = True

    if "callback" in params:
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

    if no_archive and "download_archive" in params:
        del params["download_archive"]

    data = yt_dlp.YoutubeDL(params=params).extract_info(url, download=False)

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

    return yt_dlp.YoutubeDL.sanitize_info(data) if sanitize_info else data


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

        return (opts, True, "")
    except Exception:
        with open(file) as json_data:
            from pyjson5 import load as json5_load

            try:
                opts = json5_load(json_data)

                if check_type:
                    assert isinstance(opts, check_type)  # noqa: S101

                return (opts, True, "")
            except AssertionError:
                return ({}, False, f"Failed to assert that the contents '{type(opts)}' are of type '{check_type}'.")
            except Exception as e:
                return ({}, False, f"{e}")


def check_id(file: pathlib.Path) -> bool | str:
    """
    Check if we are able to get an id from the file name.
    if so check if any video file with the same id exists.

    Args:
        file (pathlib.Path): File to check.

    Returns:
        bool|str: False if no file found, else the file path.

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

    Args:
        array (dict|list): dict-like or object from which to retrieve values.
        path (list|str|int): Represents the path to retrieve:
            - If None or empty string, returns the entire structure.
            - If list, tries each path and returns the first found.
            - If string, navigates through nested dict keys separated by `separator`.
        default (Any): Value (or callable) returned if nothing is found.
        separator (str): Separator for nested paths in strings.

    Returns:
        Any: The found value or the default if not found.

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

        LOG.debug("Removed %i the following options: '%s'.", level, ", ".join(bad_options.values()))

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

        return json.loads(json.dumps(diff, cls=Encoder))

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


def get_file_sidecar(file: pathlib.Path) -> list[dict]:
    """
    Get sidecar files for the given file.

    Args:
        file (pathlib.Path): The video file.

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

    path_loc = pathlib.Path(dir, "test.jpg")

    for filename in ["poster", "thumbnail", "artwork", "cover", "fanart"]:
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            f = path_loc.with_stem(filename).with_suffix(ext)
            if f.exists():
                images.append({"file": f})

    return images


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


def get_files(base_path: str, dir: str | None = None):
    """
    Get directory contents.

    Args:
        base_path (str): Base download path.
        dir (str): Directory to check.

    Returns:
        list: List of files and directories.

    Raises:
        OSError: If the directory is invalid or not a directory.

    """
    if dir and dir != "/":
        path = os.path.normpath(os.path.join(base_path, str(dir)))
        if not path.startswith(base_path):
            msg = f"Invalid path: '{dir}' - '{path}' - must be inside '{base_path}'."
            raise OSError(msg)
        dir_path = os.path.realpath(path)
    else:
        dir_path = base_path

    if not os.path.isdir(dir_path):
        msg = f"Invalid path: '{dir_path}' - must be a directory."
        raise OSError(msg)

    contents: list = []
    for file in pathlib.Path(dir_path).iterdir():
        if file.name.startswith(".") or file.name.startswith("_"):
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
                "type": "file" if file.is_file() else "dir",
                "content_type": content_type,
                "name": file.name,
                "path": str(file).replace(base_path, "").strip("/"),
                "size": stat.st_size,
                "mime": get_mime_type({}, file) if file.is_file() else "directory",
                "mtime": datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC).isoformat(),
                "ctime": datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.UTC).isoformat(),
                "is_dir": file.is_dir(),
                "is_file": file.is_file(),
            }
        )

    return contents
