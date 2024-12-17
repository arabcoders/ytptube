import copy
from datetime import datetime, timezone
from functools import lru_cache
import ipaddress
import json
import logging
import os
import pathlib
import re
import socket
from typing import Any
import uuid
import yt_dlp

LOG = logging.getLogger('Utils')

IGNORED_KEYS: tuple[str] = ('cookiefile', 'paths', 'outtmpl', 'progress_hooks', 'postprocessor_hooks',)
YTDLP_INFO_CLS: yt_dlp.YoutubeDL = None


def get_opts(preset: str, ytdl_opts: dict) -> dict:
    """
    Returns ytdlp options download options

    Args:
      preset (str): the name of the preset selected.
      ytdl_opts (dict): current options selected

    Returns:
      ytdl extra options
    """
    opts = copy.deepcopy(ytdl_opts)

    if 'default' == preset:
        return opts

    from .config import Config
    presets = Config.get_instance().presets

    if preset not in presets:
        LOG.error(f"Preset '{preset}' is not defined in the presets.")
        return opts

    preset_opts = presets[preset]

    opts['format'] = preset_opts.get('format')

    if 'postprocessors' in preset_opts:
        if 'postprocessors' not in opts:
            opts['postprocessors'] = []

        opts['postprocessors'].extend(preset_opts['postprocessors'])

    if 'args' in preset_opts:
        for ignored_key in IGNORED_KEYS:
            for key, value in preset_opts['args'].items():
                if key == ignored_key:
                    continue

                opts[key] = value

    return opts


def getVideoInfo(url: str, ytdlp_opts: dict = None) -> (Any | dict[str, Any] | None):
    params: dict = {
        'quiet': True,
        'color': 'no_color',
        'extract_flat': True,
    }

    if ytdlp_opts:
        params = {**params, **ytdlp_opts}

    return yt_dlp.YoutubeDL().extract_info(url, download=False)


def calcDownloadPath(basePath: str, folder: str = None, createPath: bool = True) -> str:
    """Calculates download path and prevents folder traversal.

    Returns:
        Download path with base folder factored in.
    """
    if not folder:
        return basePath

    realBasePath = os.path.realpath(basePath)
    download_path = os.path.realpath(os.path.join(basePath, folder))

    if not download_path.startswith(realBasePath):
        raise Exception(f'Folder "{folder}" must resolve inside the base download folder "{realBasePath}".')

    if not os.path.isdir(download_path) and createPath:
        os.makedirs(download_path, exist_ok=True)

    return download_path


def ExtractInfo(config: dict, url: str, debug: bool = False) -> dict:
    params: dict = {
        'color': 'no_color',
        'extract_flat': True,
        'skip_download': True,
        'ignoreerrors': True,
        'ignore_no_formats_error': True,
        **config,
    }

    # Remove keys that are not needed for info extraction as those keys generate files when used with extract_info.
    for key in ('writeinfojson', 'writethumbnail', 'writedescription', 'writeautomaticsub',):
        if key in params:
            params.pop(key)

    if debug:
        params['verbose'] = True
        params['logger'] = logging.getLogger('YTPTube-ytdl')
    else:
        params['quiet'] = True

    return yt_dlp.YoutubeDL(params=params).extract_info(url, download=False)


def mergeDict(source: dict, destination: dict) -> dict:
    """ Merge data from source into destination """
    destination_copy = copy.deepcopy(destination)

    for key, value in source.items():
        destination_key_value = destination_copy.get(key)
        if isinstance(value, dict) and isinstance(destination_key_value, dict):
            destination_copy[key] = mergeDict(source=value, destination=destination_copy.setdefault(key, {}))
        elif isinstance(value, list) and isinstance(destination_key_value, list):
            destination_copy[key] = destination_key_value + value
        else:
            destination_copy[key] = value

    return destination_copy


def mergeConfig(config: dict, new_config: dict) -> dict:
    """ Merge user provided config into default config """

    ignored_keys: tuple = (
        'cookiefile',
        'download_archive'
        'paths',
        'outtmpl',
        'progress_hooks',
        'postprocessor_hooks',
    )

    for key in ignored_keys:
        if key in new_config:
            del new_config[key]

    return mergeDict(new_config, config)


def isDownloaded(archive_file: str, url: str) -> tuple[bool, dict[str | None, str | None, str | None]]:
    global YTDLP_INFO_CLS

    idDict = {
        'id': None,
        'ie_key': None,
        'archive_id': None,
    }

    if not url or not archive_file or not os.path.exists(archive_file):
        return False, idDict,

    if not YTDLP_INFO_CLS:
        YTDLP_INFO_CLS = yt_dlp.YoutubeDL(params={
            'color': 'no_color',
            'extract_flat': True,
            'skip_download': True,
            'ignoreerrors': True,
            'ignore_no_formats_error': True,
            'quiet': True,
        })

    for key, ie in YTDLP_INFO_CLS._ies.items():
        if not ie.suitable(url):
            continue

        if not ie.working():
            break

        temp_id = ie.get_temp_id(url)
        if not temp_id:
            break

        idDict['id'] = temp_id
        idDict['ie_key'] = key
        idDict['archive_id'] = YTDLP_INFO_CLS._make_archive_id(idDict)
        break

    if not idDict['archive_id']:
        return False, idDict,

    with open(archive_file, 'r') as f:
        for line in f.readlines():
            if idDict['archive_id'] in line:
                return True, idDict,

    return False, idDict,


def jsonCookie(cookies: dict[dict[str, any]]) -> str | None:
    """Converts JSON cookies to Netscape cookies

       Returns None if no cookies are found, otherwise returns a string of cookies in Netscape format.
    """

    netscapeCookies = "# Netscape HTTP Cookie File\n# https://curl.haxx.se/docs/http-cookies.html\n# This file was generated by libcurl! Edit at your own risk.\n\n"
    hasCookies: bool = False

    for domain in cookies:
        if not isinstance(cookies[domain], dict):
            continue

        for subDomain in cookies[domain]:
            if not isinstance(cookies[domain][subDomain], dict):
                continue

            for cookie in cookies[domain][subDomain]:
                if not isinstance(cookies[domain][subDomain][cookie], dict):
                    continue

                cookieDict = cookies[domain][subDomain][cookie]

                if 0 == int(cookieDict['expirationDate']):
                    cookieDict['expirationDate'] = datetime.now(timezone.utc).timestamp() + (86400 * 1000)

                hasCookies = True
                netscapeCookies += "\t".join([
                    cookieDict['domain'] if str(cookieDict['domain']).startswith('.') else '.' + cookieDict['domain'],
                    'TRUE',
                    cookieDict['path'],
                    'TRUE' if cookieDict['secure'] else 'FALSE',
                    str(int(cookieDict['expirationDate'])),
                    cookieDict['name'],
                    cookieDict['value']
                ])+"\n"

    return netscapeCookies if hasCookies else None


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

        return (opts, True, '',)
    except Exception:
        with open(file) as json_data:
            from pyjson5 import load as json5_load
            try:
                opts = json5_load(json_data)

                if check_type:
                    assert isinstance(opts, check_type)

                return (opts, True, '',)
            except AssertionError:
                return ({}, False, f"Failed to assert that the contents '{type(opts)}' are of type '{check_type}'.",)
            except Exception as e:
                return ({}, False, f'{e}',)


def checkId(basePath: str, file: pathlib.Path) -> bool | str:
    """
    Check if we are able to get an id from the file name.
    if so check if any video file with the same id exists.

    :param basePath: Base path to strip.
    :param file: File to check.

    :return: False if no id found, otherwise the id.
    """

    match = re.search(r'(?<=\[)(?:youtube-)?(?P<id>[a-zA-Z0-9\-_]{11})(?=\])', file.stem, re.IGNORECASE)
    if not match:
        return False

    id = match.groupdict().get('id')

    for f in file.parent.iterdir():
        if id not in f.stem:
            continue

        if f.suffix not in ('.mp4', '.mkv', '.webm', '.m4v', '.m4a', '.mp3', '.aac', '.ogg',):
            continue

        return f.absolute()

    return False


def get_value(value):
    return value() if callable(value) else value


def ag(array: dict | list, path: list[str | int] | str | int, default: Any = None, separator: str = '.') -> Any:
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

    if path is None or path == '':
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
        return (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local)
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
        raise ValueError("URL is required.")

    try:
        from yarl import URL
        parsed_url = URL(url)
    except ValueError:
        raise ValueError("Invalid URL.")

    # Check allowed schemes
    if parsed_url.scheme not in ["http", "https"]:
        raise ValueError("Invalid scheme usage. Only HTTP or HTTPS allowed.")

    hostname = parsed_url.host
    if not hostname or is_private_address(hostname):
        raise ValueError("Access to internal urls or private networks is not allowed.")

    return True
