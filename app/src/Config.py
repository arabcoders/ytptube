import json
import logging
import os
import re
import sys
import coloredlogs


class Config:
    config_path: str = '.'
    download_path: str = '.'
    temp_path: str = '{download_path}'

    db_file: str = '{config_path}/ytptube.db'

    url_host: str = ''
    url_prefix: str = ''
    url_socketio: str = '{url_prefix}socket.io'

    output_template: str = '%(title)s.%(ext)s'
    output_template_chapter: str = '%(title)s - %(section_number)s %(section_title)s.%(ext)s'

    ytdl_options: dict | str = {}
    ytdl_options_file: str = ''
    ytdl_debug: bool = False

    host: str = '0.0.0.0'
    port: int = 8081

    keep_archive: bool = False

    base_path: str = ''

    logging_level: str = 'info'

    _boolean_vars: tuple = ('keep_archive', 'ytdl_debug')

    def __init__(self):
        baseDefualtPath: str = os.path.dirname(os.path.dirname(__file__))

        self.config_path = os.path.join(baseDefualtPath, 'var', 'config')
        self.download_path = os.path.join(baseDefualtPath, 'var', 'downloads')
        self.temp_path = os.path.join(baseDefualtPath, 'var', 'tmp')

        for k, v in self.getAttributes().items():
            if k.startswith('_'):
                continue

            lookUpKey: str = f'YTP_{k}'.upper()
            setattr(
                self, k,
                os.environ[lookUpKey] if lookUpKey in os.environ else v
            )

        for k, v in self.__dict__.items():
            if k.startswith('_'):
                continue

            if isinstance(v, str) and '{' in v and '}' in v:
                for key in re.findall(r'\{.*?\}', v):
                    localKey: str = key[1:-1]
                    if localKey not in self.__dict__:
                        logging.error(
                            f'Config variable "{k}" had non exisitng config reference "{key}"')
                        sys.exit(1)
                    v = v.replace(key, getattr(self, localKey))

                setattr(self, k, v)

            if k in self._boolean_vars:
                if str(v).lower() not in (True, False, 'true', 'false', 'on', 'off', '1', '0'):
                    raise ValueError(
                        f'Config variable "{k}" is set to a non-boolean value "{v}".')

                setattr(self, k, str(v).lower() in (True, 'true', 'on', '1'))

        if not self.url_prefix.endswith('/'):
            self.url_prefix += '/'

        numeric_level = getattr(
            logging, self.logging_level.upper(), None)

        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {self.logging_level}")

        logging.basicConfig(
            force=True,
            level=numeric_level,
            format="%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s] %(message)s"
        )

        coloredlogs.install()

        if isinstance(self.ytdl_options, str):
            try:
                self.ytdl_options = json.loads(self.ytdl_options)
                assert isinstance(self.ytdl_options, dict)
            except (json.decoder.JSONDecodeError, AssertionError) as e:
                logging.error(f'JSON error in "YTP_YTDL_OPTIONS": {e}')
                sys.exit(1)

        if self.ytdl_options_file:
            logging.info(
                f'Loading yt-dlp custom options from "{self.ytdl_options_file}"')
            if not os.path.exists(self.ytdl_options_file):
                logging.error(
                    f'"YTP_YTDL_OPTIONS_FILE" ENV points to non-existent file: "{self.ytdl_options_file}"')
            else:
                try:
                    with open(self.ytdl_options_file) as json_data:
                        opts = json.load(json_data)
                    assert isinstance(opts, dict)
                    self.ytdl_options.update(opts)
                except (json.decoder.JSONDecodeError, AssertionError) as e:
                    logging.error(
                        f'JSON error in "{self.ytdl_options_file}": {e}')
                    sys.exit(1)

        if self.keep_archive:
            logging.info(f'keep archive: {self.keep_archive}')
            self.ytdl_options['download_archive'] = os.path.join(
                self.config_path, 'archive.log')

    def getAttributes(self) -> dict:
        attrs: dict = {}
        vclass: str = self.__class__

        for attribute in vclass.__dict__.keys():
            if attribute.startswith('_'):
                continue

            value = getattr(vclass, attribute)
            if not callable(value):
                attrs[attribute] = value

        return attrs
