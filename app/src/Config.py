import json
import logging
import os
import re
import sys

log = logging.getLogger('config')


class Config:
    state_path: str = '../../var/config'
    download_path: str = '../../var/downloads'
    temp_path: str = '../../var/tmp'

    db_file: str = '{state_path}/ytptube.db'

    url_host: str = ''
    url_prefix: str = ''
    url_socketio: str = '{url_prefix}socket.io'

    output_template: str = '%(title)s.%(ext)s'
    output_template_chapter: str = '%(title)s - %(section_number)s %(section_title)s.%(ext)s'

    ytdl_options: dict | str = {}
    ytdl_options_file: str = ''

    host: str = '0.0.0.0'
    port: int = 8081

    base_path: str = ''

    _boolean_vars: tuple = ()

    def __init__(self):
        baseDefualtPath: str = os.path.dirname(os.path.dirname(__file__))

        self.state_path = os.path.join(baseDefualtPath, 'var', 'config')
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
                        log.error(
                            f'Config variable "{k}" had non exisitng config reference "{key}"')
                        sys.exit(1)
                    v = v.replace(key, getattr(self, localKey))

                setattr(self, k, v)

            if k in self._boolean_vars:
                if v not in (True, False, 'True', 'false', 'true', 'false', 'on', 'off', '1', '0'):
                    log.error(
                        f'Config variable "{k}" is set to a non-boolean value "{v}".')
                    sys.exit(1)
                setattr(self, k, v in (True, 'true', 'True', 'on', '1'))

        if not self.url_prefix.endswith('/'):
            self.url_prefix += '/'

        if isinstance(self.ytdl_options, str):
            try:
                self.ytdl_options = json.loads(self.ytdl_options)
                assert isinstance(self.ytdl_options, dict)
            except (json.decoder.JSONDecodeError, AssertionError):
                log.error('ytdl_options is invalid')
                sys.exit(1)

        if self.ytdl_options_file:
            log.info(
                f'Loading yt-dlp custom options from "{self.ytdl_options_file}"')
            if not os.path.exists(self.ytdl_options_file):
                log.error(f'File "{self.ytdl_options_file}" not found')
                sys.exit(1)
            try:
                with open(self.ytdl_options_file) as json_data:
                    opts = json.load(json_data)
                assert isinstance(opts, dict)
            except (json.decoder.JSONDecodeError, AssertionError):
                log.error('ytdl_options_file contents is invalid')
                sys.exit(1)

            self.ytdl_options.update(opts)

    def getAttributes(self) -> dict:
        attrs: dict = {}
        vclass: str = self.__class__

        for attribute in vclass.__dict__.keys():
            if not attribute.startswith('_'):
                value = getattr(vclass, attribute)
                if not callable(value):
                    attrs[attribute] = value

        return attrs
