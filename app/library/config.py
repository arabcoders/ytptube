import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import coloredlogs
from dotenv import load_dotenv
from yt_dlp.version import __version__ as YTDLP_VERSION

from .Utils import load_file
from .version import APP_VERSION


class Config:
    config_path: str = "."
    download_path: str = "."
    temp_path: str = "/tmp"
    temp_keep: bool = False

    url_host: str = ""
    url_prefix: str = ""
    url_socketio: str = "{url_prefix}socket.io"

    output_template: str = "%(title)s.%(ext)s"
    output_template_chapter: str = "%(title)s - %(section_number)s %(section_title)s.%(ext)s"

    keep_archive: bool = True

    ytdl_debug: bool = False
    allow_manifestless: bool = False

    host: str = "0.0.0.0"
    port: int = 8081

    log_level: str = "info"
    max_workers: int = 1

    streamer_vcodec: str = "libx264"
    streamer_acodec: str = "aac"

    auth_username: str | None = None
    auth_password: str | None = None

    remove_files: bool = False

    access_log: bool = True

    debug: bool = False
    debugpy_port: int = 5678

    socket_timeout: int = 30
    extract_info_timeout: int = 70

    db_file: str = "{config_path}/ytptube.db"
    manual_archive: str = "{config_path}/archive.manual.log"
    ui_update_title: bool = True
    pip_packages: str = ""
    pip_ignore_updates: bool = False

    # immutable config vars.
    version: str = APP_VERSION
    __instance = None
    ytdl_options: dict = {}
    tasks: list = []
    new_version_available: bool = False
    ytdlp_version: str = YTDLP_VERSION
    started: int = 0
    ignore_ui: bool = False
    presets: list = [
        {"name": "default", "format": "default"},
    ]

    _manual_vars: tuple = (
        "temp_path",
        "config_path",
        "download_path",
    )

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

    _int_vars: tuple = (
        "port",
        "max_workers",
        "socket_timeout",
        "extract_info_timeout",
        "debugpy_port",
    )
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
    )

    _frontend_vars: tuple = (
        "download_path",
        "keep_archive",
        "output_template",
        "ytdlp_version",
        "version",
        "url_host",
        "started",
        "url_prefix",
        "remove_files",
        "ui_update_title",
        "max_workers",
    )

    @staticmethod
    def get_instance():
        """Static access method."""
        return Config() if not Config.__instance else Config.__instance

    def __init__(self):
        """Virtually private constructor."""
        if Config.__instance is not None:
            raise Exception("This class is a singleton. Use Config.get_instance() instead.")
        else:
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

        for k, v in self._getAttributes().items():
            if k.startswith("_") or k in self._manual_vars:
                continue

            # If the variable declared as immutable, set it to the default value.
            if k in self._immutable:
                setattr(self, k, v)
                continue

            lookUpKey: str = f"YTP_{k}".upper()
            setattr(self, k, os.environ[lookUpKey] if lookUpKey in os.environ else v)

        for k, v in self.__dict__.items():
            if k.startswith("_") or k in self._immutable or k in self._manual_vars:
                continue

            if isinstance(v, str) and "{" in v and "}" in v:
                for key in re.findall(r"\{.*?\}", v):
                    localKey: str = key[1:-1]
                    if localKey not in self.__dict__:
                        logging.error(f"Config variable '{k}' had non-existing config reference '{key}'.")
                        sys.exit(1)

                    v = v.replace(key, getattr(self, localKey))

                setattr(self, k, v)

            if k in self._boolean_vars:
                if str(v).lower() not in (True, False, "true", "false", "on", "off", "1", "0"):
                    raise ValueError(f"Config variable '{k}' is set to a non-boolean value '{v}'.")

                setattr(self, k, str(v).lower() in (True, "true", "on", "1"))

            if k in self._int_vars:
                setattr(self, k, int(v))

        if not self.url_prefix.endswith("/"):
            self.url_prefix += "/"

        numeric_level = getattr(logging, self.log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level '{self.log_level}' specified.")

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
        if os.path.exists(optsFile) and os.path.getsize(optsFile) > 4:
            LOG.info(f"Loading yt-dlp custom options from '{optsFile}'.")

            (opts, status, error) = load_file(optsFile, dict)
            if not status:
                LOG.error(f"Could not load yt-dlp custom options from '{optsFile}'. {error}")
                sys.exit(1)

            self.ytdl_options.update(opts)
        else:
            LOG.info(f"No yt-dlp custom options found at '{optsFile}'.")

        tasksFile = os.path.join(self.config_path, "tasks.json")
        if os.path.exists(tasksFile) and os.path.getsize(tasksFile) > 0:
            LOG.info(f"Loading tasks from '{tasksFile}'.")
            try:
                (tasks, status, error) = load_file(tasksFile, list)
                if not status:
                    LOG.error(f"Could not load tasks file from '{tasksFile}'. '{error}'.")
                    sys.exit(1)
                self.tasks.extend(tasks)
            except Exception:
                pass

        # Load default presets.
        with open(os.path.join(os.path.dirname(__file__), "presets.json"), "r") as f:
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

        self.started = time.time()

    def _getAttributes(self) -> dict:
        attrs: dict = {}
        vClass: str = self.__class__

        for attribute in vClass.__dict__.keys():
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

        return {k: getattr(self, k) for k in self._frontend_vars}
