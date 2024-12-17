import asyncio
import json
import logging
import multiprocessing
import os
import re
import shutil
import yt_dlp
import hashlib
from .AsyncPool import Terminator
from .Utils import get_opts, jsonCookie, mergeConfig
from .ItemDTO import ItemDTO
from .config import Config
from .Emitter import Emitter
from multiprocessing.managers import SyncManager
LOG = logging.getLogger('download')


class Download:
    """
    Download task.
    """
    id: str = None
    manager = None
    download_dir: str = None
    temp_dir: str = None
    output_template: str = None
    output_template_chapter: str = None
    ytdl_opts: dict = None
    info: ItemDTO = None
    default_ytdl_opts: dict = None
    debug: bool = False
    tempPath: str = None
    emitter: Emitter = None
    manager: SyncManager = None
    canceled: bool = False
    is_live: bool = False
    info_dict: dict = None
    "yt-dlp metadata dict."
    update_task = None

    bad_live_options: list = [
        "concurrent_fragment_downloads",
        "fragment_retries",
        "skip_unavailable_fragments",
    ]
    "Bad yt-dlp options which are known to cause issues with live stream and post manifestless mode."

    _ytdlp_fields: tuple = (
        'tmpfilename',
        'filename',
        'status',
        'msg',
        'total_bytes',
        'total_bytes_estimate',
        'downloaded_bytes',
        'speed',
        'eta',
    )
    "Fields to be extracted from yt-dlp progress hook."

    tempKeep: bool = False
    "Keep temp folder after download."

    def __init__(self, info: ItemDTO, info_dict: dict = None, debug: bool = False):
        config = Config.get_instance()

        self.download_dir = info.download_dir
        self.temp_dir = info.temp_dir
        self.output_template_chapter = info.output_template_chapter
        self.output_template = info.output_template
        self.preset = info.preset
        self.ytdl_opts = get_opts(self.preset, info.ytdlp_config if info.ytdlp_config else {})
        self.info = info
        self.id = info._id
        self.default_ytdl_opts = config.ytdl_options
        self.debug = debug
        self.canceled = False
        self.tmpfilename = None
        self.status_queue = None
        self.proc = None
        self.emitter = None
        self.max_workers = int(config.max_workers)
        self.tempKeep = bool(config.temp_keep)
        self.is_live = bool(info.is_live) or info.live_in is not None
        self.is_manifestless = 'is_manifestless' in self.info.options and self.info.options['is_manifestless'] is True
        self.info_dict = info_dict

    def _progress_hook(self, data: dict):
        dataDict = {k: v for k, v in data.items() if k in self._ytdlp_fields}
        self.status_queue.put({'id': self.id, **dataDict})

    def _postprocessor_hook(self, data: dict):
        if data.get('postprocessor') != 'MoveFiles' or data.get('status') != 'finished':
            return

        if '__finaldir' in data['info_dict']:
            filename = os.path.join(data['info_dict']['__finaldir'], os.path.basename(data['info_dict']['filepath']))
        else:
            filename = data['info_dict']['filepath']

        self.status_queue.put({
            'id': self.id,
            'status': 'finished',
            'filename': filename
        })

    def _download(self):
        try:
            params: dict = {
                'color': 'no_color',
                'paths': {
                    'home': self.download_dir,
                    'temp': self.tempPath,
                },
                'outtmpl': {
                    'default': self.output_template,
                    'chapter': self.output_template_chapter
                },
                'noprogress': True,
                'break_on_existing': True,
                'progress_hooks': [self._progress_hook],
                'postprocessor_hooks': [self._postprocessor_hook],
                **mergeConfig(self.default_ytdl_opts, self.ytdl_opts),
            }

            if 'format' not in params and self.default_ytdl_opts.get('format', None):
                params['format'] = self.default_ytdl_opts['format']

            params['ignoreerrors'] = False

            if self.debug:
                params['verbose'] = True
                params['noprogress'] = False

            if self.info.ytdlp_cookies:
                try:
                    data = jsonCookie(json.loads(self.info.ytdlp_cookies))
                    if not data:
                        LOG.warning(
                            f'The cookie string that was provided for {self.info.title} is empty or not in expected spec.')
                    with open(os.path.join(self.tempPath, f'cookie_{self.info._id}.txt'), 'w') as f:
                        f.write(data)

                    params['cookiefile'] = f.name
                except ValueError as e:
                    LOG.error(
                        f'Invalid cookies: was provided for {self.info.title} - {str(e)}')

            if self.is_live or self.is_manifestless:
                hasDeletedOptions = False
                deletedOpts: list = []
                for opt in self.bad_live_options:
                    if opt in params:
                        params.pop(opt, None)
                        hasDeletedOptions = True
                        deletedOpts.append(opt)

                if hasDeletedOptions:
                    LOG.warning(
                        f"Live stream detected for '{self.info.title}', The following opts '{deletedOpts=}' have been deleted which are known to cause issues with live stream and post stream manifestless mode.")

            LOG.info(
                f'Downloading pid: {os.getpid()} id="{self.info.id}" title="{self.info.title}" preset="{self.preset}".')

            cls = yt_dlp.YoutubeDL(params=params)

            if isinstance(self.info_dict, dict) and len(self.info_dict) > 1:
                LOG.debug(f'Downloading using pre-info.')
                cls.process_ie_result(self.info_dict, download=True)
                ret = cls._download_retcode
            else:
                LOG.debug(f'Downloading using url: {self.info.url}')
                ret = cls.download([self.info.url])

            self.status_queue.put({'id': self.id, 'status': 'finished' if ret == 0 else 'error'})
        except Exception as exc:
            self.status_queue.put({
                'id': self.id,
                'status': 'error',
                'msg': str(exc),
                'error': str(exc)
            })

        LOG.info(f'Finished {os.getpid()=} id="{self.info.id}" title="{self.info.title}".')

    async def start(self, emitter: Emitter):
        self.manager = multiprocessing.Manager()
        self.emitter = emitter
        self.status_queue = self.manager.Queue()

        # Create temp dir for each download.
        self.tempPath = os.path.join(
            self.temp_dir,
            hashlib.shake_256(f"D-{self.info.id}".encode('utf-8')).hexdigest(5)
        )

        if not os.path.exists(self.tempPath):
            os.makedirs(self.tempPath, exist_ok=True)

        self.proc = multiprocessing.Process(name=f"download-{self.id}", target=self._download)
        self.proc.start()
        self.info.status = 'preparing'

        asyncio.create_task(self.emitter.updated(dl=self.info), name=f"emitter-{self.id}")
        asyncio.create_task(self.progress_update(), name=f"update-{self.id}")

        return await asyncio.get_running_loop().run_in_executor(None, self.proc.join)

    def started(self) -> bool:
        return self.proc is not None

    def cancel(self) -> bool:
        if not self.started():
            return False

        self.canceled = True

        return True

    async def close(self) -> bool:
        """
        Close download process.
        This method MUST be called to clear resources.
        """
        if not self.started():
            return False

        procId = self.proc.ident
        try:
            LOG.info(f"Closing download process: '{procId}'.")
            try:
                if 'update_task' in self.__dict__ and self.update_task.done() is False:
                    self.update_task.cancel()
            except Exception as e:
                LOG.error(f"Failed to close status queue: '{procId}'. {e}")
                pass

            self.kill()

            loop = asyncio.get_running_loop()
            tasks = []

            if self.proc.is_alive():
                tasks.append(loop.run_in_executor(None, self.proc.join))

            if self.manager:
                tasks.append(loop.run_in_executor(None, self.manager.shutdown))

            if len(tasks) > 0:
                await asyncio.gather(*tasks)

            if self.proc:
                self.proc.close()
                self.proc = None

            self.delete_temp()

            LOG.debug(f"Closed download process: '{procId}'.")

            return True
        except Exception as e:
            LOG.error(f"Failed to close process: '{procId}'. {e}")

        return False

    def running(self) -> bool:
        try:
            return self.proc is not None and self.proc.is_alive()
        except ValueError:
            return False

    def is_canceled(self) -> bool:
        return self.canceled

    def kill(self) -> bool:
        if not self.running():
            return False

        try:
            LOG.info(f"Killing download process: '{self.proc.ident}'.")
            self.proc.kill()
            return True
        except Exception as e:
            LOG.error(f"Failed to kill process: '{self.proc.ident}'. {e}")

        return False

    def delete_temp(self):
        if self.tempKeep is True or not self.tempPath:
            return

        if self.info.status != 'finished' and self.is_live:
            LOG.warning(
                f'Keeping live temp folder [{self.tempPath}], as the reported status is not finished [{self.info.status}].')
            return

        if not os.path.exists(self.tempPath):
            return

        if self.tempPath == self.temp_dir:
            LOG.warning(
                f'Attempted to delete video temp folder: {self.tempPath}, but it is the same as main temp folder.')
            return

        LOG.info(f'Deleting Temp folder: {self.tempPath}')
        shutil.rmtree(self.tempPath, ignore_errors=True)

    async def progress_update(self):
        """
        Update status of download task and notify the client.
        """
        while True:
            try:
                self.update_task = asyncio.get_running_loop().run_in_executor(None, self.status_queue.get)
            except asyncio.CancelledError:
                LOG.debug(f'Closing progress update for: {self.info._id=}.')
                return

            status = await self.update_task

            if status is None or status.__class__ is Terminator:
                LOG.debug(f'Closing progress update for: {self.info._id=}.')
                return

            if status.get('id') != self.id or len(status) < 2:
                continue

            if self.debug:
                LOG.debug(f'Status Update: {self.info._id=} {status=}')

            if isinstance(status, str):
                asyncio.create_task(self.emitter.updated(dl=self.info), name=f"emitter-u-{self.id}")
                continue

            self.tmpfilename = status.get('tmpfilename')

            if 'filename' in status:
                self.info.filename = os.path.relpath(status.get('filename'), self.download_dir)

                if os.path.exists(status.get('filename')):
                    self.info.file_size = os.path.getsize(status.get('filename'))

            self.info.status = status.get('status', self.info.status)
            self.info.msg = status.get('msg')

            if self.info.status == 'error' and 'error' in status:
                self.info.error = status.get('error')
                asyncio.create_task(
                    self.emitter.error(dl=self.info, message=self.info.error),
                    name=f"emitter-e-{self.id}")

            if 'downloaded_bytes' in status:
                total = status.get('total_bytes') or status.get('total_bytes_estimate')
                if total:
                    self.info.percent = status['downloaded_bytes'] / total * 100
                    self.info.total_bytes = total

            self.info.speed = status.get('speed')
            self.info.eta = status.get('eta')

            if self.info.status == 'finished' and 'filename' in status:
                try:
                    self.info.file_size = os.path.getsize(status.get('filename'))
                except FileNotFoundError:
                    LOG.warning(f'File not found: {status.get("filename")}')
                    self.info.file_size = None
                    pass

            asyncio.create_task(self.emitter.updated(dl=self.info), name=f"emitter-u-{self.id}")
