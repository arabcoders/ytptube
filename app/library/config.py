import logging
import multiprocessing
import os
import re
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from multiprocessing.managers import SyncManager
from pathlib import Path

import coloredlogs
from dotenv import load_dotenv

from .Utils import FileLogFormatter, arg_converter
from .version import APP_BRANCH, APP_BUILD_DATE, APP_COMMIT_SHA, APP_VERSION


class Config:
    app_env: str = "production"
    """The application environment, can be 'production' or 'development'."""

    config_path: str = "."
    """The path to the configuration directory."""

    download_path: str = "."
    """The path to the download directory."""

    temp_path: str = "/tmp"
    """The path to the temporary directory."""

    temp_keep: bool = False
    """Keep temporary files after the download is complete."""

    output_template: str = "%(title)s.%(ext)s"
    """The output template to use for the downloaded files."""

    output_template_chapter: str = "%(title)s - %(section_number)s %(section_title)s.%(ext)s"
    """The output template to use for the downloaded files with chapters."""

    keep_archive: bool = True
    """Keep the download archive file."""

    ytdl_debug: bool = False
    """Enable yt-dlp debugging."""

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

    archive_file: str = "{config_path}/archive.log"
    """The path to the download archive file."""

    manual_archive: str = "{config_path}/archive.manual.log"
    """The path to the manual archive file."""

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

    __instance = None
    "The instance of the class."

    started: int = 0
    "The time the application was started."

    ignore_ui: bool = False
    "Ignore the UI and run the application in the background."

    basic_mode: bool = False
    "Run the frontend in basic mode."

    default_preset: str = "default"
    "The default preset to use when no preset is specified."

    instance_title: str | None = None
    "The title of the instance."

    file_logging: bool = True
    "Enable file logging."

    sentry_dsn: str | None = None
    "The Sentry DSN to use for error reporting."

    secret_key: str
    "The secret key to use for the application."

    tasks_handler_timer: str = "15 */1 * * *"
    """The cron expression for the tasks timer."""

    console_enabled: bool = False
    "Enable direct access to yt-dlp console."

    browser_enabled: bool = False
    "Enable file browser access."

    browser_control_enabled: bool = False
    "Enable file browser control access."

    ytdlp_auto_update: bool = True
    """Enable in-place auto update of yt-dlp package."""

    ytdlp_cli: str = ""
    """The command line options to use for yt-dlp."""

    _ytdlp_cli_mutable: str = ""
    """The command line options to use for yt-dlp."""

    is_native: bool = False
    "Is the application running in webview."

    prevent_live_premiere: bool = False
    """Prevent downloading of the initial premiere live broadcast."""

    playlist_items_concurrency: int = 1
    """The number of concurrent playlist items to be processed at same time."""

    pictures_backends: list[str] = [
        "https://unsplash.it/1920/1080?random",
        "https://picsum.photos/1920/1080",
        "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=en-US",
    ]
    "The list of picture backends to use for the background."

    _manual_vars: tuple = (
        "temp_path",
        "config_path",
        "download_path",
    )
    "The variables that are set manually."

    _immutable: tuple = (
        "__instance",
        "ytdl_options",
        "started",
        "ytdlp_cli",
        "_ytdlp_cli_mutable",
        "is_native",
        "app_version",
        "app_commit_sha",
        "app_build_date",
        "app_branch",
    )
    "The variables that are immutable."

    _int_vars: tuple = (
        "port",
        "max_workers",
        "socket_timeout",
        "extract_info_timeout",
        "debugpy_port",
        "playlist_items_concurrency",
    )
    "The variables that are integers."

    _boolean_vars: tuple = (
        "keep_archive",
        "ytdl_debug",
        "debug",
        "temp_keep",
        "access_log",
        "remove_files",
        "ignore_ui",
        "ui_update_title",
        "pip_ignore_updates",
        "basic_mode",
        "file_logging",
        "console_enabled",
        "browser_enabled",
        "browser_control_enabled",
        "ytdlp_auto_update",
        "prevent_premiere_live",
    )
    "The variables that are booleans."

    _frontend_vars: tuple = (
        "download_path",
        "keep_archive",
        "output_template",
        "started",
        "remove_files",
        "ui_update_title",
        "max_workers",
        "basic_mode",
        "default_preset",
        "instance_title",
        "sentry_dsn",
        "console_enabled",
        "browser_enabled",
        "browser_control_enabled",
        "ytdlp_cli",
        "file_logging",
        "base_path",
        "is_native",
        "app_env",
        "tasks_handler_timer",
        "app_version",
        "app_commit_sha",
        "app_build_date",
        "app_branch",
    )
    "The variables that are relevant to the frontend."

    _manager: SyncManager | None = None
    "The manager instance."

    @staticmethod
    def get_instance(is_native: bool = False) -> "Config":
        """Static access method."""
        return Config(is_native) if not Config.__instance else Config.__instance

    @staticmethod
    def get_manager() -> SyncManager:
        if not Config._manager:
            Config._manager = multiprocessing.Manager()

        return Config._manager

    def __init__(self, is_native: bool = False):
        """Virtually private constructor."""
        if Config.__instance is not None:
            msg = "This class is a singleton. Use Config.get_instance() instead."
            raise Exception(msg)

        Config.__instance = self

        baseDefaultPath: str = str(Path(__file__).parent.parent.parent.absolute())

        self.is_native = is_native
        self.temp_path = os.environ.get("YTP_TEMP_PATH", None) or str(Path(baseDefaultPath) / "var" / "tmp")
        self.config_path = os.environ.get("YTP_CONFIG_PATH", None) or str(Path(baseDefaultPath) / "var" / "config")
        self.download_path = os.environ.get("YTP_DOWNLOAD_PATH", None) or str(
            Path(baseDefaultPath) / "var" / "downloads"
        )

        envFile: str = Path(self.config_path) / ".env"

        if envFile.exists():
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

                    v = v.replace(key, getattr(self, localKey))

                setattr(self, k, v)

            if k in self._boolean_vars:
                if str(v).lower() not in (True, False, "true", "false", "on", "off", "1", "0"):
                    msg = f"Config variable '{k}' is set to a non-boolean value '{v}'."
                    raise ValueError(msg)

                setattr(self, k, str(v).lower() in (True, "true", "on", "1"))

            if k in self._int_vars:
                setattr(self, k, int(v))

        if isinstance(self.pictures_backends, str) and self.pictures_backends:
            self.pictures_backends = self.pictures_backends.split(",")

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

        ytdl_options = {}
        opts_file: Path = Path(self.config_path) / "ytdlp.cli"
        if opts_file.exists() and opts_file.stat().st_size > 2:
            LOG.info(f"Loading yt-dlp custom options from '{opts_file}'.")
            with open(opts_file) as f:
                self.ytdlp_cli = f.read().strip()
                if self.ytdlp_cli:
                    self._ytdlp_cli_mutable = self.ytdlp_cli
                    try:
                        removed_options = []
                        ytdl_options = arg_converter(args=self.ytdlp_cli, level=True, removed_options=removed_options)

                        try:
                            LOG.debug("Parsed yt-dlp cli options '%s'.", ytdl_options)
                        except Exception:
                            pass

                        if len(removed_options) > 0:
                            LOG.warning(
                                "Removed the following options: '%s' from '%s'", ", ".join(removed_options), opts_file
                            )
                    except Exception as e:
                        msg = f"Failed to parse yt-dlp cli options from '{opts_file}'. '{e!s}'."
                        raise ValueError(msg) from e
                else:
                    LOG.warning(f"Empty yt-dlp custom options file '{opts_file}'.")
        else:
            LOG.info(f"No yt-dlp custom options found at '{opts_file}'.")

        self._ytdlp_cli_mutable += f"\n--socket-timeout {self.socket_timeout}"

        if self.keep_archive:
            archive_file: Path = Path(self.archive_file)
            if not archive_file.exists():
                LOG.info(f"Creating archive file '{archive_file}'.")
                archive_file.touch(exist_ok=True)

            LOG.info(f"keep archive option is enabled. Using archive file '{archive_file}'.")
            self._ytdlp_cli_mutable += f"\n--download-archive {archive_file.as_posix()!s}"

        if self.temp_keep:
            LOG.info("Keep temp files option is enabled.")

        if self.auth_password and self.auth_username:
            LOG.warning(f"Basic authentication enabled with username '{self.auth_username}'.")

        if self.basic_mode:
            LOG.info("The frontend is running in basic mode.")

        if self.file_logging:
            log_level_file = getattr(logging, self.log_level_file.upper(), None)
            if not isinstance(log_level_file, int):
                msg = f"Invalid file log level '{self.log_level_file}' specified."
                raise TypeError(msg)

            loggingPath = Path(self.config_path) / "logs"
            if not loggingPath.exists():
                loggingPath.mkdir(parents=True, exist_ok=True)

            handler = TimedRotatingFileHandler(
                filename=loggingPath / "app.log",
                when="midnight",
                backupCount=3,
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

        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.INFO)

        # check env
        if self.app_env not in ("production", "development"):
            msg: str = (
                f"Invalid application environment '{self.app_env}' specified. Must be 'production' or 'development'."
            )
            raise ValueError(msg)

        if "dev-master" == self.app_version:
            self._version_via_git()

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

    def get_ytdlp_args(self) -> dict:
        try:
            return arg_converter(args=self._ytdlp_cli_mutable, level=True)
        except Exception as e:
            msg = f"Invalid ytdlp.cli options for yt-dlp. '{e!s}'."
            raise ValueError(msg) from e

    def frontend(self) -> dict:
        """
        Returns configuration variables relevant to the frontend.

        Returns:
            dict: A dictionary with the frontend configuration

        """
        data = {k: getattr(self, k) for k in self._frontend_vars}

        ytdlp_args = self.get_ytdlp_args()

        if not data.get("keep_archive", False) and ytdlp_args.get("download_archive", None):
            data["keep_archive"] = True

        data["ytdlp_version"] = Config.ytdlp_version()
        return data

    @staticmethod
    def ytdlp_version():
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

            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
                cwd=os.path.dirname(git_path),
                capture_output=True,
                text=True,
                check=False,
            )

            if 0 != branch_result.returncode:
                logging.error(f"Git rev-parse failed: {branch_result.stderr.strip()}")
                return

            branch_name: str = branch_result.stdout.strip()
            if not branch_name:
                logging.warning("Git branch name is empty.")
                return

            commit_result = subprocess.run(
                ["git", "log", "-1", "--format=%ct_%H"],  # noqa: S607
                cwd=os.path.dirname(git_path),
                capture_output=True,
                text=True,
                check=False,
            )

            if 0 != commit_result.returncode:
                logging.error(f"Git log failed: {commit_result.stderr.strip()}")
                return

            commit_info: str = commit_result.stdout.strip()
            if not commit_info:
                logging.warning("Git commit info is empty.")
                return

            commit_date, commit_sha = commit_info.split("_", 1)
            commit_date = time.strftime("%Y%m%d", time.localtime(int(commit_date)))

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
