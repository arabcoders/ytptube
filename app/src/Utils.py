import copy
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any
import yt_dlp

log = logging.getLogger('Utils')

IGNORED_KEYS: tuple = (
    'cookiefile',
    'paths',
    'outtmpl',
    'progress_hooks',
    'postprocessor_hooks',
)

AUDIO_FORMATS: tuple = (
    'm4a', 'mp3', 'opus', 'wav'
)


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

        vfmt, afmt = (
            '[ext=mp4]', '[ext=m4a]') if format == "mp4" else ('', '')

        vres = f'[height<={quality}]' if quality != 'best' else ''

        vcombo = vres + vfmt

        return f'bestvideo{vcombo}+bestaudio{afmt}/best{vcombo}'

    raise Exception(f"Unkown format {format}")


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
    logging.debug(f"get_opts: {format} {quality} {ytdl_opts}")
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
            postprocessors.append(
                {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
            postprocessors.append({"key": "FFmpegMetadata"})
            postprocessors.append({"key": "EmbedThumbnail"})

    if format == "thumbnail":
        opts["skip_download"] = True
        opts["writethumbnail"] = True
        postprocessors.append(
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})

    logging.debug(
        f"Postprocessors: {opts['postprocessors']} + {postprocessors}")
    opts["postprocessors"] = postprocessors + \
        (opts["postprocessors"] if "postprocessors" in opts else [])
    return opts


def getVideoInfo(url: str, ytdlp_opts: dict = None) -> (Any | dict[str, Any] | None):
    params: dict = {
        'quiet': True,
        'no_color': True,
        'extract_flat': True,

    }

    if ytdlp_opts:
        params = {**params, **ytdlp_opts}

    return yt_dlp.YoutubeDL().extract_info(url, download=False)


def getAttributes(vclass: str | type) -> dict:
    attrs: dict = {}

    if not isinstance(vclass, type):
        vclass = vclass.__class__

    for attribute in vclass.__dict__.keys():
        if not attribute.startswith('_'):
            value = getattr(vclass, attribute)
            if not callable(value):
                attrs[attribute] = value

    return attrs


def calcDownloadPath(basePath: str, folder: str = None) -> str:
    """Calculates download path And prevents directory traversal attacks.

    Returns:
        Dir with base dir factored in.
    """
    if not folder:
        return basePath

    realBasePath = os.path.realpath(basePath)
    download_path = os.path.realpath(os.path.join(basePath, folder))

    if not download_path.startswith(realBasePath):
        raise Exception(
            f'Folder "{folder}" must resolve inside the base download directory "{realBasePath}"')

    if not os.path.isdir(download_path):
        os.makedirs(download_path, exist_ok=True)

    return download_path


def ExtractInfo(config: dict, url: str) -> dict:
    params: dict = {
        'quiet': True,
        'no_color': True,
        'extract_flat': True,
        'skip_download': True,
        'ignoreerrors': True,
        'ignore_no_formats_error': True,
        **config,
    }

    return yt_dlp.YoutubeDL(params=params).extract_info(url, download=False)


def mergeDict(source: dict, destination: dict) -> dict:
    """ Merge data from source into destination """
    destination_copy = copy.deepcopy(destination)

    for key, value in source.items():
        destination_key_value = destination_copy.get(key)
        if isinstance(value, dict) and isinstance(destination_key_value, dict):
            destination_copy[key] = mergeDict(
                source=value,
                destination=destination_copy.setdefault(key, {})
            )
        else:
            destination_copy[key] = value

    return destination_copy


def mergeConfig(config: dict, new_config: dict) -> dict:
    """ Merge user provided config into default config """

    ignored_keys: tuple = (
        'cookiefile',
        'paths',
        'outtmpl',
        'progress_hooks',
        'postprocessor_hooks',
    )

    for key in ignored_keys:
        if key in new_config:
            del new_config[key]

    return mergeDict(new_config, config)


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

                dicto = cookies[domain][subDomain][cookie]

                if 0 == int(dicto['expirationDate']):
                    dicto['expirationDate']: float = datetime.now(
                        timezone.utc).timestamp() + (86400 * 1000)

                hasCookies = True
                netscapeCookies += "\t".join([
                    dicto['domain'] if str(dicto['domain']).startswith(
                        '.') else '.' + dicto['domain'],
                    'TRUE',
                    dicto['path'],
                    'TRUE' if dicto['secure'] else 'FALSE',
                    str(int(dicto['expirationDate'])),
                    dicto['name'],
                    dicto['value']
                ])+"\n"

    return netscapeCookies if hasCookies else None


class ObjectSerializer(json.JSONEncoder):
    """
    This class is used to serialize objects to JSON.
    The only difference between this and the default JSONEncoder is that this one
    will call the __dict__ method of an object if it exists.
    """

    def default(self, obj):
        return obj.__dict__ if isinstance(obj, object) else json.JSONEncoder.default(self, obj)
