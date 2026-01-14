import logging
import multiprocessing
import os
import re
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from multiprocessing.managers import SyncManager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import coloredlogs
from dotenv import load_dotenv

from .Singleton import Singleton
from .Utils import FileLogFormatter
from .version import APP_BRANCH, APP_BUILD_DATE, APP_COMMIT_SHA, APP_VERSION

if TYPE_CHECKING:
    from subprocess import CompletedProcess

SUPPORTED_CODECS: tuple[str] = ("h264_qsv", "h264_nvenc", "h264_amf", "h264_videotoolbox", "h264_vaapi", "libx264")
"Supported encoder names in order of preference."


class Config(metaclass=Singleton):
    app_env: str = "production"
    """The application environment, can be 'production' or 'development'."""

    app_path: str = "../../"
    """The app path of the application."""

    config_path: str = "."
    """The path to the configuration directory."""

    download_path: str = "."
    """The path to the download directory."""

    download_path_depth: int = 2
    """How many subdirectories to show in auto complete."""

    download_info_expires: int = 10800
    """How long (in seconds) the download info is valid before it needs to be re-extracted."""

    temp_path: str = "/tmp"
    """The path to the temporary directory."""

    simple_mode: bool = False
    """Enable simple mode."""

    temp_keep: bool = False
    """Keep temporary files after the download is complete."""

    temp_disabled: bool = False
    """Disable the temporary files feature."""

    allow_internal_urls: bool = False
    """Allow requests to internal URLs."""

    output_template: str = "%(title)s.%(ext)s"
    """The output template to use for the downloaded files."""

    output_template_chapter: str = "%(title)s - %(section_number)s %(section_title)s.%(ext)s"
    """The output template to use for the downloaded files with chapters."""

    keep_archive: bool = True
    """Keep the download archive file."""

    host: str = "0.0.0.0"
    """The host to bind the server to."""

    port: int = 8081
    """The port to bind the server to."""

    log_level: str = "info"
    """The log level to use for the application."""

    log_level_file: str = "info"
    """The log level to use for the file logging."""

    base_path: str = "/"
    """The base path to use for the application."""

    max_workers: int = 20
    """The maximum number of workers to use for downloading."""

    max_workers_per_extractor: int = 2
    """The maximum number of concurrent downloads per extractor."""

    streamer_vcodec: str = ""
    """The video codec to use for streaming. If empty, auto-detect."""

    streamer_acodec: str = "aac"
    """The audio codec to use for streaming."""

    vaapi_device: str = "/dev/dri/renderD128"
    """VAAPI device path used for VAAPI encoder when available."""

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

    extract_info_timeout: int = 70
    """The timeout to use for extracting video information."""

    extract_info_concurrency: int = 4
    """The number of concurrent extract_info calls allowed."""

    db_file: str = "{config_path}{os_sep}ytptube.db"
    """The path to the database file."""

    archive_file: str = "{config_path}{os_sep}archive.log"
    """The path to the download archive file."""

    apprise_config: str = "{config_path}{os_sep}apprise.yml"
    """The path to the Apprise configuration file."""

    ui_update_title: bool = True
    """Update the title of the browser tab with the current status."""

    pip_packages: str = ""
    """The pip packages to install."""

    pip_ignore_updates: bool = False
    """Ignore pip package updates."""

    app_version: str = APP_VERSION
    "The version of the application, same as `version`."

    app_commit_sha: str = APP_COMMIT_SHA
    "The commit SHA of the application."

    app_build_date: str = APP_BUILD_DATE
    "The build date of the application."

    app_branch: str = APP_BRANCH
    "The branch of the application."

    started: int = 0
    "The time the application was started."

    ignore_ui: bool = False
    "Ignore the UI and run the application in the background."

    default_preset: str = "default"
    "The default preset to use when no preset is specified."

    instance_title: str | None = None
    "The title of the instance."

    file_logging: bool = True
    "Enable file logging."

    secret_key: str
    "The secret key to use for the application."

    tasks_handler_timer: str = "15 */1 * * *"
    """The cron expression for the tasks timer."""

    console_enabled: bool = False
    "Enable direct access to yt-dlp console."

    browser_control_enabled: bool = False
    "Enable file browser control access."

    ytdlp_auto_update: bool = True
    """Enable in-place auto update of yt-dlp package."""

    ytdlp_version: str | None = None
    """The version of yt-dlp to use, if not set, the latest version will be used."""

    ytdlp_debug: bool = False
    """Enable yt-dlp debugging."""

    flaresolverr_url: str = ""
    """FlareSolverr endpoint URL."""

    flaresolverr_max_timeout: int = 120
    """Max FlareSolverr challenge timeout in seconds."""

    flaresolverr_client_timeout: int = 120
    """HTTP client timeout (seconds) when calling FlareSolverr."""

    flaresolverr_cache_ttl: int = 600
    """The cache TTL (in seconds) for FlareSolverr solutions."""

    is_native: bool = False
    "Is the application running in natively."

    prevent_live_premiere: bool = False
    """Prevent downloading of the initial premiere live broadcast."""

    live_premiere_buffer: int = 5
    """The buffer time in minutes to add to video duration to wait before starting premiere download."""

    playlist_items_concurrency: int = 4
    """The number of concurrent playlist items to be processed at same time."""

    auto_clear_history_days: int = 0
    """Number of days after which completed download history is automatically cleared. 0 to disable."""

    default_pagination: int = 50
    """The default number of items per page for pagination."""

    task_handler_random_delay: float = 60.0
    """The maximum random delay in seconds before starting a task handler."""

    ignore_archived_items: bool = False
    """Dont report archived items in the download history."""

    pictures_backends: list[str] = [
        "https://unsplash.it/1920/1080?random",
        "https://picsum.photos/1920/1080",
        "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=en-US",
    ]
    "The list of picture backends to use for the background."

    static_ui_path: str = ""
    "The path to the static UI files."

    check_for_updates: bool = True
    "Check for application updates."

    new_version: str = ""
    "The new version available."

    _manual_vars: tuple = (
        "temp_path",
        "config_path",
        "download_path",
        "app_path",
    )
    "The variables that are set manually."

    _immutable: tuple = (
        "ytdl_options",
        "started",
        "is_native",
        "app_version",
        "app_commit_sha",
        "app_build_date",
        "app_branch",
        "new_version",
    )
    "The variables that are immutable."

    _int_vars: tuple = (
        "port",
        "max_workers",
        "max_workers_per_extractor",
        "extract_info_timeout",
        "debugpy_port",
        "playlist_items_concurrency",
        "download_path_depth",
        "download_info_expires",
        "auto_clear_history_days",
        "default_pagination",
        "flaresolverr_max_timeout",
        "flaresolverr_client_timeout",
        "flaresolverr_cache_ttl",
    )
    "The variables that are integers."

    _boolean_vars: tuple = (
        "keep_archive",
        "ytdlp_debug",
        "debug",
        "temp_keep",
        "access_log",
        "remove_files",
        "ignore_ui",
        "ui_update_title",
        "pip_ignore_updates",
        "file_logging",
        "console_enabled",
        "browser_control_enabled",
        "ytdlp_auto_update",
        "prevent_premiere_live",
        "temp_disabled",
        "allow_internal_urls",
        "simple_mode",
        "ignore_archived_items",
        "check_for_updates",
    )
    "The variables that are booleans."

    _float_vars: tuple = ("task_handler_random_delay",)
    "The variables that are floats."

    _frontend_vars: tuple = (
        "download_path",
        "keep_archive",
        "output_template",
        "started",
        "remove_files",
        "ui_update_title",
        "max_workers",
        "max_workers_per_extractor",
        "default_preset",
        "instance_title",
        "console_enabled",
        "simple_mode",
        "browser_control_enabled",
        "file_logging",
        "base_path",
        "is_native",
        "app_env",
        "tasks_handler_timer",
        "app_version",
        "app_commit_sha",
        "app_build_date",
        "app_branch",
        "default_pagination",
        "check_for_updates",
        "new_version",
    )
    "The variables that are relevant to the frontend."

    _manager: SyncManager | None = None
    "The manager instance."

    os_sep: str = os.path.sep
    "The system path separator."

    @staticmethod
    def get_instance(is_native: bool = False) -> "Config":
        cls = Config(is_native)
        cls.is_native = is_native or cls.is_native
        return cls

    @staticmethod
    def get_manager() -> SyncManager:
        if not Config._manager:
            Config._manager = multiprocessing.Manager()

        return Config._manager

    def __init__(self, is_native: bool = False):
        baseDefaultPath: str = str(Path(__file__).parent.parent.parent.absolute())

        self.config_path = os.environ.get("YTP_CONFIG_PATH", None) or str(Path(baseDefaultPath) / "var" / "config")
        envFile: str = Path(self.config_path) / ".env"

        if envFile.exists():
            logging.info(f"Loading environment variables from '{envFile}'.")
            load_dotenv(envFile)

        self.is_native = is_native
        self.temp_path = os.environ.get("YTP_TEMP_PATH", None) or str(Path(baseDefaultPath) / "var" / "tmp")
        self.download_path = os.environ.get("YTP_DOWNLOAD_PATH", None) or str(
            Path(baseDefaultPath) / "var" / "downloads"
        )
        self.app_path = Path(__file__).parent.parent.absolute()

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

                    v: str = v.replace(key, str(getattr(self, localKey)))

                setattr(self, k, v)

            if k in self._boolean_vars:
                if str(v).lower() not in (True, False, "true", "false", "on", "off", "1", "0"):
                    msg = f"Config variable '{k}' is set to a non-boolean value '{v}'."
                    raise ValueError(msg)

                setattr(self, k, str(v).lower() in (True, "true", "on", "1"))

            if k in self._int_vars:
                setattr(self, k, int(v))

            if k in self._float_vars:
                setattr(self, k, float(v))

        if isinstance(self.pictures_backends, str) and self.pictures_backends:
            self.pictures_backends = self.pictures_backends.split(",")

        if not self.base_path.endswith("/"):
            self.base_path += "/"

        numeric_level: int | None = getattr(logging, self.log_level.upper(), None)
        if not isinstance(numeric_level, int):
            msg = f"Invalid log level '{self.log_level}' specified."
            raise TypeError(msg)

        coloredlogs.install(
            level=numeric_level,
            fmt="%(asctime)s [%(name)s] [%(levelname)-5.5s] %(message)s",
            datefmt="%H:%M:%S",
            encoding="utf-8",
        )

        LOG: logging.Logger = logging.getLogger("config")

        if self.debug:
            try:
                import debugpy

                debugpy.listen(("0.0.0.0", self.debugpy_port), in_process_debug_adapter=True)
                LOG.info(f"starting debugpy server on '0.0.0.0:{self.debugpy_port}'.")
            except ImportError:
                LOG.error("debugpy package not found, install it with 'uv sync'.")
            except Exception as e:
                LOG.error(f"Error starting debugpy server at '0.0.0.0:{self.debugpy_port}'. {e}")

        if (Path(self.config_path) / "ytdlp.cli").exists():
            LOG.error("Support for ./ytdlp.cli file is removed, migrate to presets and remove the file.")

        if self.temp_keep:
            LOG.warning("Keep temp files option is enabled.")

        if self.auth_password and self.auth_username:
            LOG.info(f"Authentication enabled with username '{self.auth_username}'.")

        if self.file_logging:
            log_level_file: int | None = getattr(logging, self.log_level_file.upper(), None)
            if not isinstance(log_level_file, int):
                msg = f"Invalid file log level '{self.log_level_file}' specified."
                raise TypeError(msg)

            loggingPath: Path = Path(self.config_path) / "logs"
            if not loggingPath.exists():
                loggingPath.mkdir(parents=True, exist_ok=True)

            handler = TimedRotatingFileHandler(
                filename=loggingPath / "app.log",
                when="midnight",
                backupCount=3,
                encoding="utf-8",
            )

            handler.setLevel(log_level_file)
            formatter = FileLogFormatter("%(asctime)s [%(levelname)s.%(name)s]: %(message)s")
            handler.setFormatter(formatter)
            logging.getLogger().addHandler(handler)

        key_file: str = Path(self.config_path) / "secret.key"

        if key_file.exists() and key_file.stat().st_size > 2:
            with open(key_file, "rb") as f:
                self.secret_key = f.read().strip()
        else:
            self.secret_key = os.urandom(32)
            with open(key_file, "wb") as f:
                f.write(self.secret_key)

        self.started = time.time()

        _log_levels = (
            ("httpx", logging.WARNING),
            ("urllib3.connectionpool", logging.WARNING),
            ("apprise", logging.WARNING),
            ("httpcore", logging.INFO),
            ("aiosqlite", logging.INFO),
        )
        for _tool, _level in _log_levels:
            logging.getLogger(_tool).setLevel(_level)

        if self.app_env not in ("production", "development"):
            msg: str = f"Invalid app environment '{self.app_env}' specified. Must be 'production' or 'development'."
            raise ValueError(msg)

        if self.streamer_vcodec and self.streamer_vcodec not in SUPPORTED_CODECS:
            supported = ", ".join(SUPPORTED_CODECS)
            msg: str = f"Invalid video codec '{self.streamer_vcodec}' specified. Supported: '{supported}'."
            raise ValueError(msg)

        if "dev-master" == self.app_version:
            self._version_via_git()

    def set_app_path(self, path: Path | str) -> "Config":
        """
        Set the root path of the application.

        Args:
            path (str): The root path to set.

        Returns:
            Config: The Config instance.

        """
        Config.app_path = str(path)

        return self

    def _get_attributes(self) -> dict:
        attrs: dict = {}
        vClass: str = self.__class__

        for attribute in vClass.__dict__:
            if attribute.startswith("_"):
                continue

            value: Any = getattr(vClass, attribute)
            if not callable(value):
                attrs[attribute] = value

        return attrs

    def is_dev(self) -> bool:
        """
        Check if the application is running in development mode.

        Returns:
            bool: True if the application is in development mode, False otherwise.

        """
        return "development" == self.app_env

    def is_prod(self) -> bool:
        """
        Check if the application is running in production mode.

        Returns:
            bool: True if the application is in production mode, False otherwise.

        """
        return "production" == self.app_env

    def frontend(self) -> dict:
        """
        Returns configuration variables relevant to the frontend.

        Returns:
            dict: A dictionary with the frontend configuration

        """
        data: dict[str, Any] = {k: getattr(self, k) for k in self._frontend_vars}

        data["ytdlp_version"] = Config._ytdlp_version()
        return data

    def get_replacers(self) -> dict[str, str]:
        """
        Get the variables that can be used in Command options for yt-dlp.

        Returns:
            dict[str, str]: The replacer variables.

        """
        keys: tuple[str] = ("os_sep", "download_path", "temp_path", "config_path", "archive_file")
        return {k: getattr(self, k) for k in keys}

    @staticmethod
    def _ytdlp_version() -> str:
        try:
            from yt_dlp.version import __version__ as YTDLP_VERSION

            return YTDLP_VERSION
        except ImportError:
            return "0.0.0"

    def _version_via_git(self):
        """
        Updates the version of the application using git tags.
        This is used to set the version to the latest git tag.
        """
        git_path: str = Path(__file__).parent / ".." / ".." / ".git"
        if not git_path.exists():
            return

        try:
            import subprocess

            branch_result: CompletedProcess[str] = subprocess.run(
                ["git", "-c", f"safe.directory={git_path.parent!s}", "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
                cwd=os.path.dirname(git_path),
                capture_output=True,
                text=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            if 0 != branch_result.returncode:
                logging.error(f"Git rev-parse failed: {branch_result.stderr.strip()}")
                return

            branch_name: str = branch_result.stdout.strip()
            if not branch_name:
                logging.warning("Git branch name is empty.")
                return

            commit_result: CompletedProcess[str] = subprocess.run(
                ["git", "-c", f"safe.directory={git_path.parent!s}", "log", "-1", "--format=%ct_%H"],  # noqa: S607
                cwd=os.path.dirname(git_path),
                capture_output=True,
                text=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            if 0 != commit_result.returncode:
                logging.error(f"Git log failed: {commit_result.stderr.strip()}")
                return

            commit_info: str = commit_result.stdout.strip()
            if not commit_info:
                logging.warning("Git commit info is empty.")
                return

            commit_date, commit_sha = commit_info.split("_", 1)
            commit_date: str = time.strftime("%Y%m%d", time.localtime(int(commit_date)))

            self.app_version = f"{branch_name}-{commit_date}-{commit_sha[:8]}"
            self.app_branch = branch_name
            self.app_commit_sha = commit_sha
            self.app_build_date = commit_date
            version_data = {
                "version": self.app_version,
                "branch": self.app_branch,
                "commit": self.app_commit_sha,
                "build_date": self.app_build_date,
            }
            logging.info(f"Application version info set to '{version_data}'")
        except Exception as e:
            logging.error(f"Error while getting git version: {e!s}")
