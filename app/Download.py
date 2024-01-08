import asyncio
import json
import logging
import multiprocessing
import os
import queue
import re
import shutil
import yt_dlp
from Utils import Notifier, get_format, get_opts, jsonCookie, mergeConfig
from ItemDTO import ItemDTO
from Config import Config

log = logging.getLogger('download')


class Download:
    id: str = None
    manager = None
    download_dir: str = None
    temp_dir: str = None
    output_template: str = None
    output_template_chapter: str = None
    format: str = None
    ytdl_opts: dict = None
    info: ItemDTO = None
    default_ytdl_opts: dict = None
    debug: bool = False
    tempPath: str = None
    notifier: Notifier = None
    canceled: bool = False

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
    tempKeep: bool = False

    def __init__(
        self,
        info: ItemDTO,
        download_dir: str,
        temp_dir: str,
        output_template_chapter: str,
        default_ytdl_opts: dict,
        debug: bool = False
    ):
        self.download_dir = download_dir
        self.temp_dir = temp_dir
        self.output_template_chapter = output_template_chapter
        self.output_template = info.output_template
        self.format = get_format(info.format, info.quality)
        self.ytdl_opts = get_opts(
            info.format, info.quality, info.ytdlp_config if info.ytdlp_config else {})
        self.info = info
        self.id = info._id
        self.default_ytdl_opts = default_ytdl_opts
        self.debug = debug

        self.canceled = False
        self.tmpfilename = None
        self.status_queue = None
        self.proc = None
        self.loop = None
        self.notifier = None
        config = Config.get_instance()
        self.max_workers = int(config.max_workers)
        self.tempKeep = bool(config.temp_keep)

    def _download(self):
        try:
            def put_status(st):
                dicto = {k: v for k, v in st.items() if k in self._ytdlp_fields}
                self.status_queue.put({'id': self.id, **dicto})

            def put_status_postprocessor(d):
                if d['postprocessor'] == 'MoveFiles' and d['status'] == 'finished':
                    if '__finaldir' in d['info_dict']:
                        filename = os.path.join(
                            d['info_dict']['__finaldir'],
                            os.path.basename(d['info_dict']['filepath'])
                        )
                    else:
                        filename = d['info_dict']['filepath']

                    self.status_queue.put({
                        'id': self.id,
                        'status': 'finished',
                        'filename': filename
                    })

            params: dict = {
                'no_color': True,
                'format': self.format,
                'paths': {
                    'home': self.download_dir,
                    'temp': self.tempPath,
                },
                'outtmpl': {
                    'default': self.output_template,
                    'chapter': self.output_template_chapter
                },
                'socket_timeout': 60,
                'break_per_url': True,
                'ignoreerrors': False,
                'progress_hooks': [put_status],
                'postprocessor_hooks': [put_status_postprocessor],
                **mergeConfig(self.default_ytdl_opts, self.ytdl_opts),
            }

            params['ignoreerrors'] = False

            if self.debug:
                params['verbose'] = True

            if self.info.ytdlp_cookies:
                try:
                    data = jsonCookie(json.loads(self.info.ytdlp_cookies))
                    if not data:
                        log.warning(
                            f'The cookie string that was provided for {self.info.title} is empty or not in expected spec.')
                    with open(os.path.join(self.tempPath, f'cookie_{self.info._id}.txt'), 'w') as f:
                        f.write(data)

                    params['cookiefile'] = f.name
                except ValueError as e:
                    log.error(
                        f'Invalid cookies: was provided for {self.info.title} - {str(e)}')

            log.info(
                f'Downloading id="{self.info.id}" title="{self.info.title}".')

            ret = yt_dlp.YoutubeDL(params=params).download([self.info.url])

            self.status_queue.put({
                'id': self.id,
                'status': 'finished' if ret == 0 else 'error'
            })
        except Exception as exc:
            self.status_queue.put({
                'id': self.id,
                'status': 'error',
                'msg': str(exc),
                'error': str(exc)
            })

    async def start(self, notifier: Notifier):
        if self.manager is None:
            self.manager = multiprocessing.Manager()

        self.status_queue = self.manager.Queue()
        self.loop = asyncio.get_running_loop()
        self.notifier = notifier

        # Create temp dir for each download.
        self.tempPath = os.path.join(self.temp_dir, self.info._id)
        if not os.path.exists(self.tempPath):
            os.makedirs(self.tempPath, exist_ok=True)

        self.proc = multiprocessing.Process(target=self._download)
        self.proc.start()
        self.info.status = 'preparing'
        await self.notifier.updated(self.info)
        asyncio.create_task(self.progress_update())
        return await self.loop.run_in_executor(None, self.proc.join)

    def started(self) -> bool:
        return self.proc is not None

    def cancel(self):
        self.kill()
        self.canceled = True

    def close(self):
        if self.started():
            self.proc.close()

        self.delete_temp()

    def running(self) -> bool:
        return self.started() and self.proc.is_alive()

    def is_canceled(self) -> bool:
        return self.canceled

    def kill(self):
        if self.running():
            log.info(f'Killing download process: {self.proc.ident}')
            self.proc.kill()

    def delete_temp(self):
        if self.tempKeep is True or not self.tempPath:
            return

        if not os.path.exists(self.tempPath):
            return

        if self.tempPath == self.temp_dir:
            log.warning(
                f'Attempted to delete video temp directory: {self.tempPath}, but it is the same as main temp directory.')
            return

        log.info(f'Deleting Temp directory: {self.tempPath}')
        shutil.rmtree(self.tempPath, ignore_errors=True)

    async def progress_update(self):
        """
        Update status of download task and notify the client.
        """
        while True:
            status = await self.loop.run_in_executor(None, self.status_queue.get)
            if status.get('id') != self.id or len(status) < 2:
                return

            if self.debug:
                log.debug(f'Status Update: {self.info._id=} {status=}')

            if isinstance(status, str):
                await self.notifier.updated(self.info)
                return

            self.tmpfilename = status.get('tmpfilename')

            if 'filename' in status:
                self.info.filename = os.path.relpath(
                    status.get('filename'), self.download_dir)

                # Set correct file extension for thumbnails
                if self.info.format == 'thumbnail':
                    self.info.filename = re.sub(
                        r'\.webm$', '.jpg', self.info.filename)

            self.info.status = status.get('status', self.info.status)
            self.info.msg = status.get('msg')

            if self.info.status == 'error' and 'error' in status:
                self.info.error = status.get('error')
                await self.notifier.error(self.info, self.info.error)

            if 'downloaded_bytes' in status:
                total = status.get('total_bytes') or status.get(
                    'total_bytes_estimate')
                if total:
                    perc = status['downloaded_bytes'] / total * 100
                    self.info.percent = perc
                    self.info.total_bytes = total

            self.info.speed = status.get('speed')
            self.info.eta = status.get('eta')

            if self.info.status == 'finished' and 'filename' in status and self.info.format != 'thumbnail':
                self.info.file_size = os.path.getsize(status.get('filename'))

            await self.notifier.updated(self.info)
