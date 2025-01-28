import json
import logging
import multiprocessing
import os
import re
import sys
import time
from multiprocessing.managers import SyncManager
from pathlib import Path

import coloredlogs
from dotenv import load_dotenv
from yt_dlp.version import __version__ as YTDLP_VERSION

from .Utils import IGNORED_KEYS, load_file, mergeDict
from .version import APP_VERSION


class Config:
    config_path: str = "."
    """The path to the configuration directory."""

    download_path: str = "."
    """The path to the download directory."""

    temp_path: str = "/tmp"
    """The path to the temporary directory."""

    temp_keep: bool = False
    """Keep temporary files after the download is complete."""

    url_socketio: str = "/socket.io"
    """The URL to use for the socket.io server."""

    output_template: str = "%(title)s.%(ext)s"
    """The output template to use for the downloaded files."""

    output_template_chapter: str = "%(title)s - %(section_number)s %(section_title)s.%(ext)s"
    """The output template to use for the downloaded files with chapters."""

    keep_archive: bool = True
    """Keep the download archive file."""

    ytdl_debug: bool = False
    """Enable yt-dlp debugging."""

    allow_manifestless: bool = False
    """Allow downloading videos without manifest."""

    host: str = "0.0.0.0"
    """The host to bind the server to."""

    port: int = 8081
    """The port to bind the server to."""

    log_level: str = "info"
    """The log level to use for the application."""

    max_workers: int = 1
    """The maximum number of workers to use for downloading."""

    streamer_vcodec: str = "libx264"
    """The video codec to use for streaming."""
    streamer_acodec: str = "aac"
    """The audio codec to use for streaming."""

    auth_username: str | None = None
    """The username to use for basic authentication."""

    auth_password: str | None = None
    """The password to use for basic authentication."""

    remove_files: bool = False
    """Remove downloaded files when removing the record."""

    access_log: bool = True
    """Enable access logging."""

    debug: bool = False
    """Enable debugging."""

    debugpy_port: int = 5678
    """The port to use for the debugpy server."""

    socket_timeout: int = 30
    """The socket timeout to use for yt-dlp."""

    extract_info_timeout: int = 70
    """The timeout to use for extracting video information."""

    db_file: str = "{config_path}/ytptube.db"
    """The path to the database file."""

    manual_archive: str = "{config_path}/archive.manual.log"
    """The path to the manual archive file."""

    ui_update_title: bool = True
    """Update the title of the browser tab with the current status."""

    pip_packages: str = ""
    """The pip packages to install."""

    pip_ignore_updates: bool = False
    """Ignore pip package updates."""

    # immutable config vars.
    version: str = APP_VERSION
    "The version of the application."

    __instance = None
    "The instance of the class."

    ytdl_options: dict = {}
    "The options to use for yt-dlp."

    new_version_available: bool = False
    "A new version of the application is available."

    ytdlp_version: str = YTDLP_VERSION
    "The version of yt-dlp."

    started: int = 0
    "The time the application was started."

    ignore_ui: bool = False
    "Ignore the UI and run the application in the background."

    basic_mode: bool = False
    "Run the frontend in basic mode."

    presets: list = [
        {"name": "default", "format": "default"},
    ]
    "The presets to use for downloading."

    default_preset: str = "default"
    "The default preset to use when no preset is specified."

    _manual_vars: tuple = (
        "temp_path",
        "config_path",
        "download_path",
    )
    "The variables that are set manually."

    _immutable: tuple = (
        "version",
        "__instance",
        "ytdl_options",
        "tasks",
        "new_version_available",
        "ytdlp_version",
        "started",
        "presets",
    )
    "The variables that are immutable."

    _int_vars: tuple = (
        "port",
        "max_workers",
        "socket_timeout",
        "extract_info_timeout",
        "debugpy_port",
    )
    "The variables that are integers."

    _boolean_vars: tuple = (
        "keep_archive",
        "ytdl_debug",
        "debug",
        "temp_keep",
        "allow_manifestless",
        "access_log",
        "remove_files",
        "ignore_ui",
        "ui_update_title",
        "pip_ignore_updates",
        "basic_mode",
    )
    "The variables that are booleans."

    _frontend_vars: tuple = (
        "download_path",
        "keep_archive",
        "output_template",
        "ytdlp_version",
        "version",
        "started",
        "remove_files",
        "ui_update_title",
        "max_workers",
        "basic_mode",
        "default_preset",
    )
    "The variables that are relevant to the frontend."

    _manager: SyncManager | None = None
    "The manager instance."

    @staticmethod
    def get_instance():
        """Static access method."""
        return Config() if not Config.__instance else Config.__instance

    @staticmethod
    def get_manager() -> SyncManager:
        if not Config._manager:
            Config._manager = multiprocessing.Manager()

        return Config._manager

    def __init__(self):
        """Virtually private constructor."""
        if Config.__instance is not None:
            msg = "This class is a singleton. Use Config.get_instance() instead."
            raise Exception(msg)

        Config.__instance = self

        baseDefaultPath: str = str(Path(__file__).parent.parent.parent.absolute())

        self.temp_path = os.environ.get("YTP_TEMP_PATH", None) or os.path.join(baseDefaultPath, "var", "tmp")
        self.config_path = os.environ.get("YTP_CONFIG_PATH", None) or os.path.join(baseDefaultPath, "var", "config")
        self.download_path = os.environ.get("YTP_DOWNLOAD_PATH", None) or os.path.join(
            baseDefaultPath, "var", "downloads"
        )

        envFile: str = os.path.join(self.config_path, ".env")

        if os.path.exists(envFile):
            logging.info(f"Loading environment variables from '{envFile}'.")
            load_dotenv(envFile)

        for k, v in self._get_attributes().items():
            if k.startswith("_") or k in self._manual_vars:
                continue

            # If the variable declared as immutable, set it to the default value.
            if k in self._immutable:
                setattr(self, k, v)
                continue

            lookUpKey: str = f"YTP_{k}".upper()
            setattr(self, k, os.environ.get(lookUpKey, v))

        for k, v in self.__dict__.items():
            if k.startswith("_") or k in self._immutable or k in self._manual_vars:
                continue

            if isinstance(v, str) and "{" in v and "}" in v:
                for key in re.findall(r"\{.*?\}", v):
                    localKey: str = key[1:-1]
                    if localKey not in self.__dict__:
                        logging.error(f"Config variable '{k}' had non-existing config reference '{key}'.")
                        sys.exit(1)

                    v = v.replace(key, getattr(self, localKey))  # noqa: PLW2901

                setattr(self, k, v)

            if k in self._boolean_vars:
                if str(v).lower() not in (True, False, "true", "false", "on", "off", "1", "0"):
                    msg = f"Config variable '{k}' is set to a non-boolean value '{v}'."
                    raise ValueError(msg)

                setattr(self, k, str(v).lower() in (True, "true", "on", "1"))

            if k in self._int_vars:
                setattr(self, k, int(v))

        numeric_level = getattr(logging, self.log_level.upper(), None)
        if not isinstance(numeric_level, int):
            msg = f"Invalid log level '{self.log_level}' specified."
            raise TypeError(msg)

        coloredlogs.install(
            level=numeric_level, fmt="%(asctime)s [%(name)s] [%(levelname)-5.5s] %(message)s", datefmt="%H:%M:%S"
        )

        LOG = logging.getLogger("config")

        if self.debug:
            try:
                import debugpy

                debugpy.listen(("0.0.0.0", self.debugpy_port), in_process_debug_adapter=True)
                LOG.info(f"starting debugpy server on '0.0.0.0:{self.debugpy_port}'.")
            except ImportError:
                LOG.error("debugpy package not found, please install it with 'pip install debugpy'.")
            except Exception as e:
                LOG.error(f"Error starting debugpy server at '0.0.0.0:{self.debugpy_port}'. {e}")

        optsFile: str = os.path.join(self.config_path, "ytdlp.json")
        if os.path.exists(optsFile) and os.path.getsize(optsFile) > 5:
            LOG.info(f"Loading yt-dlp custom options from '{optsFile}'.")

            (opts, status, error) = load_file(optsFile, dict)
            if not status:
                LOG.error(f"Could not load yt-dlp custom options from '{optsFile}'. {error}")
                sys.exit(1)
            if isinstance(opts, dict):
                for key in IGNORED_KEYS:
                    if key in opts:
                        LOG.error(f"Key '{key}' is not allowed to be loaded via 'ytdlp.json' file.")
                        del opts[key]

                self.ytdl_options = mergeDict(self.ytdl_options, opts)
            else:
                LOG.error(f"Invalid yt-dlp custom options file '{optsFile}'.")
        else:
            LOG.info(f"No yt-dlp custom options found at '{optsFile}'.")

        # Load default presets.
        with open(os.path.join(os.path.dirname(__file__), "presets.json")) as f:
            self.presets.extend(json.load(f))

        # Load user defined presets.
        presetsFile = os.path.join(self.config_path, "presets.json")
        if os.path.exists(presetsFile) and os.path.getsize(presetsFile) > 0:
            LOG.info(f"Loading user presets from '{presetsFile}'.")
            try:
                (presets, status, error) = load_file(presetsFile, list)
                if not status:
                    LOG.error(f"Could not load presets file from '{presetsFile}'. '{error}'.")
                    sys.exit(1)

                if not isinstance(presets, list):
                    LOG.error(f"Invalid presets file '{presetsFile}'. It's expected to be a list of objects.")
                    sys.exit(1)

                for preset in presets:
                    if "name" not in preset:
                        LOG.error(f"Missing 'name' key in preset '{preset}'.")
                        continue

                    if "format" not in preset:
                        LOG.error(f"Missing 'format' key in preset '{preset}'.")
                        continue

                    if "args" in preset and not isinstance(preset["args"], dict):
                        LOG.error(f"Invalid 'args' key in preset '{preset}' it's expected to be dict.")
                        continue

                    if "postprocessors" in preset and not isinstance(preset["postprocessors"], list):
                        LOG.error(f"Invalid 'postprocessors' key in preset '{preset}' it's expected to be list.")
                        continue

                    self.presets.append(preset)
            except Exception:
                pass

        self.ytdl_options["socket_timeout"] = self.socket_timeout

        if self.keep_archive:
            LOG.info("keep archive option is enabled.")
            self.ytdl_options["download_archive"] = os.path.join(self.config_path, "archive.log")

        if self.temp_keep:
            LOG.info("Keep temp files option is enabled.")

        if self.auth_password and self.auth_username:
            LOG.warning(f"Basic authentication enabled with username '{self.auth_username}'.")

        if self.basic_mode:
            LOG.info("The frontend is running in basic mode.")

        self.started = time.time()

    def _get_attributes(self) -> dict:
        attrs: dict = {}
        vClass: str = self.__class__

        for attribute in vClass.__dict__:
            if attribute.startswith("_"):
                continue

            value = getattr(vClass, attribute)
            if not callable(value):
                attrs[attribute] = value

        return attrs

    def frontend(self) -> dict:
        """
        Returns configuration variables relevant to the frontend.

        Returns:
            dict: A dictionary with the frontend configuration

        """
        data = {k: getattr(self, k) for k in self._frontend_vars}
        hasCookies = self.ytdl_options.get("cookiefile", None)
        data["has_cookies"] = hasCookies is not None and os.path.exists(hasCookies)

        return data
