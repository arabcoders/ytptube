import json
import logging
import os
import re
import sys
import coloredlogs
from version import APP_VERSION
from dotenv import load_dotenv
from yt_dlp.version import __version__ as YTDLP_VERSION


class Config:
    __instance = None
    config_path: str = '.'
    download_path: str = '.'
    temp_path: str = '{download_path}'
    temp_keep: bool = False
    db_file: str = '{config_path}/ytptube.db'

    url_host: str = ''
    url_prefix: str = ''
    url_socketio: str = '{url_prefix}socket.io'

    output_template: str = '%(title)s.%(ext)s'
    output_template_chapter: str = '%(title)s - %(section_number)s %(section_title)s.%(ext)s'

    ytdl_options: dict | str = {}
    ytdl_debug: bool = False

    host: str = '0.0.0.0'
    port: int = 8081

    keep_archive: bool = True

    base_path: str = ''

    log_level: str = 'info'

    allow_manifestless: bool = False

    max_workers: int = 1

    version: str = APP_VERSION

    debug: bool = False

    new_version_available: bool = False

    extract_info_timeout: int = 70

    socket_timeout: int = 30

    ytdlp_version: str = YTDLP_VERSION

    _int_vars: tuple = ('port', 'max_workers', 'socket_timeout', 'extract_info_timeout',)
    _immutable: tuple = ('version', '__instance', 'ytdl_options', 'new_version_available', 'ytdlp_version',)
    _boolean_vars: tuple = ('keep_archive', 'ytdl_debug', 'debug', 'temp_keep', 'allow_manifestless',)

    @staticmethod
    def get_instance():
        """ Static access method. """
        return Config() if not Config.__instance else Config.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if Config.__instance is not None:
            raise Exception("This class is a singleton!. Use Config.getInstance() instead.")
        else:
            Config.__instance = self

        baseDefaultPath: str = os.path.dirname(__file__)

        self.temp_path = os.environ.get('YTP_TEMP_PATH', None) or os.path.join(baseDefaultPath, 'var', 'tmp')
        self.config_path = os.environ.get('YTP_CONFIG_PATH', None) or os.path.join(baseDefaultPath, 'var', 'config')
        self.download_path = os.environ.get(
            'YTP_DOWNLOAD_PATH', None) or os.path.join(
            baseDefaultPath, 'var', 'downloads')

        envFile: str = os.path.join(self.config_path, '.env')

        if os.path.exists(envFile):
            logging.info(f'Loading environment variables from [{envFile}].')
            load_dotenv(envFile)

        for k, v in self._getAttributes().items():
            if k.startswith('_'):
                continue

            # If the variable declared as immutable, set it to the default value.
            if k in self._immutable:
                setattr(self, k, v)
                continue

            lookUpKey: str = f'YTP_{k}'.upper()
            setattr(self, k, os.environ[lookUpKey] if lookUpKey in os.environ else v)

        for k, v in self.__dict__.items():
            if k.startswith('_') or k in self._immutable:
                continue

            if isinstance(v, str) and '{' in v and '}' in v:
                for key in re.findall(r'\{.*?\}', v):
                    localKey: str = key[1:-1]
                    if localKey not in self.__dict__:
                        logging.error(f'Config variable "{k}" had non existing config reference "{key}"')
                        sys.exit(1)

                    v = v.replace(key, getattr(self, localKey))

                setattr(self, k, v)

            if k in self._boolean_vars:
                if str(v).lower() not in (True, False, 'true', 'false', 'on', 'off', '1', '0'):
                    raise ValueError(f'Config variable "{k}" is set to a non-boolean value "{v}".')

                setattr(self, k, str(v).lower() in (True, 'true', 'on', '1'))

            if k in self._int_vars:
                setattr(self, k, int(v))

        if not self.url_prefix.endswith('/'):
            self.url_prefix += '/'

        numeric_level = getattr(logging, self.log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {self.log_level}")

        coloredlogs.install(
            level=numeric_level,
            fmt="%(asctime)s [%(name)s] [%(levelname)-5.5s] %(message)s",
            datefmt='%H:%M:%S'
        )

        LOG = logging.getLogger('config')

        if self.debug:
            try:
                import debugpy
                debugpy.listen(("0.0.0.0", 5678))
                LOG.info("starting debugpy server on [0.0.0.0:5678]")
            except ImportError:
                LOG.error("debugpy not found, please install it with 'pip install debugpy'")

        optsFile: str = os.path.join(self.config_path, 'ytdlp.json')
        if os.path.exists(optsFile) and os.path.getsize(optsFile) > 0:
            LOG.info(f'Loading yt-dlp custom options from "{optsFile}"')

            try:
                with open(optsFile) as json_data:
                    opts = json.load(json_data)
                assert isinstance(opts, dict)
                self.ytdl_options.update(opts)
            except (json.decoder.JSONDecodeError, AssertionError) as e:
                LOG.error(f'JSON error in "{optsFile}": {e}')
                sys.exit(1)
        else:
            LOG.info(f'No custom yt-dlp options found in "{self.config_path}"')

        self.ytdl_options['socket_timeout'] = self.socket_timeout

        if self.keep_archive:
            LOG.info(f'keep archive: {self.keep_archive}')
            self.ytdl_options['download_archive'] = os.path.join(
                self.config_path, 'archive.log')

        LOG.info(f'Keep temp: {self.temp_keep}')

    def _getAttributes(self) -> dict:
        attrs: dict = {}
        vClass: str = self.__class__

        for attribute in vClass.__dict__.keys():
            if attribute.startswith('_'):
                continue

            value = getattr(vClass, attribute)
            if not callable(value):
                attrs[attribute] = value

        return attrs
