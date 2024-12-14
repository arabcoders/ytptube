import asyncio
import copy
from datetime import datetime, timezone
import json
import logging
import os
import pathlib
import re
from typing import Any
import yt_dlp
from socketio import AsyncServer
from Webhooks import Webhooks

LOG = logging.getLogger('Utils')

AUDIO_FORMATS: tuple[str] = ('m4a', 'mp3', 'opus', 'wav',)
IGNORED_KEYS: tuple[str] = ('cookiefile', 'paths', 'outtmpl', 'progress_hooks', 'postprocessor_hooks',)

YTDLP_INFO_CLS: yt_dlp.YoutubeDL = None


def get_format(format: str, quality: str) -> str:
    """
    Returns format for download

    Args:
      format (str): format selected
      quality (str): quality selected

    Raises:
      Exception: unknown quality, unknown format

    Returns:
      dl_format: Formatted download string
    """
    format = format or "any"

    if format.startswith("custom:"):
        return format[7:]

    if format == "thumbnail":
        # Quality is irrelevant in this case since we skip the download
        return "bestaudio/best"

    if format in AUDIO_FORMATS:
        # Audio quality needs to be set post-download, set in opts
        return "bestaudio/best"

    if format in ('mp4', 'any'):
        if quality == 'audio':
            return "bestaudio/best"

        videoFormat, audioFormat = ('[ext=mp4]', '[ext=m4a]') if format == "mp4" else ('', '')

        videoResolution = f'[height<={quality}]' if quality != 'best' else ''

        videoCombo = videoResolution + videoFormat

        return f'bestvideo{videoCombo}+bestaudio{audioFormat}/best{videoCombo}'

    raise Exception(f"Unknown format {format}")


def get_opts(format: str, quality: str, ytdl_opts: dict) -> dict:
    """
    Returns extra download options
    Mostly postprocessing options

    Args:
      format (str): format selected
      quality (str): quality of format selected (needed for some formats)
      ytdl_opts (dict): current options selected

    Returns:
      ytdl_opts: Extra options
    """
    opts = copy.deepcopy(ytdl_opts)
    if not opts:
        opts: dict = {
            "postprocessors": [],
        }

    postprocessors = []

    if format in AUDIO_FORMATS:
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": format,
            "preferredquality": 0 if quality == "best" else quality,
        })

        # Audio formats without thumbnail
        if format not in ("wav") and "writethumbnail" not in opts:
            opts["writethumbnail"] = True
            postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
            postprocessors.append({"key": "FFmpegMetadata"})
            postprocessors.append({"key": "EmbedThumbnail"})

    if format == "thumbnail":
        opts["skip_download"] = True
        opts["writethumbnail"] = True
        postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})

    opts["postprocessors"] = postprocessors + (opts["postprocessors"] if "postprocessors" in opts else [])
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
    """Calculates download path and prevents directory traversal.

    Returns:
        Download path with base directory factored in.
    """
    if not folder:
        return basePath

    realBasePath = os.path.realpath(basePath)
    download_path = os.path.realpath(os.path.join(basePath, folder))

    if not download_path.startswith(realBasePath):
        raise Exception(f'Folder "{folder}" must resolve inside the base download directory "{realBasePath}".')

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


class ObjectSerializer(json.JSONEncoder):
    """
    This class is used to serialize objects to JSON.
    The only difference between this and the default JSONEncoder is that this one
    will call the __dict__ method of an object if it exists.
    """

    def default(self, obj):
        if isinstance(obj, object) and hasattr(obj, '__dict__'):
            return obj.__dict__
        return json.JSONEncoder.default(self, obj)


class Notifier:
    '''
    This class is used to send events to the frontend.
    '''

    sio: AsyncServer = None
    "SocketIO server instance"

    serializer: ObjectSerializer = None
    "Serializer used to serialize objects to JSON"

    webhooks: Webhooks = None
    "Send webhooks events."

    webhooks_allowed_events: tuple = (
        'added', 'completed', 'error', 'not_live'
    )
    "Events that are allowed to be sent to webhooks."

    def __init__(self, sio: AsyncServer, serializer: ObjectSerializer, webhooks: Webhooks = None):
        self.sio = sio
        self.serializer = serializer
        self.webhooks = webhooks

    async def added(self, dl: dict):
        await self.emit('added', dl)

    async def updated(self, dl: dict):
        await self.emit('updated', dl)

    async def completed(self, dl: dict):
        await self.emit('completed', dl)

    async def canceled(self, id: str):
        await self.emit('canceled', id)

    async def cleared(self, id: str):
        await self.emit('cleared', id)

    async def error(self, dl: dict, message: str):
        await self.emit('error', (dl, message))

    async def warning(self, message: str):
        await self.emit('error', message)

    async def emit(self, event: str, data):
        tasks = []
        tasks.append(self.sio.emit(event, self.serializer.encode(data)))

        if self.webhooks and event in self.webhooks_allowed_events:
            tasks.append(self.webhooks.send(event, data))

        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=60)
        except asyncio.TimeoutError:
            LOG.error(f"Timed out sending event {event} to webhooks.")


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
