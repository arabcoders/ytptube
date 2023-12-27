
import asyncio
import json
import logging
import multiprocessing
import os
import re
import shutil
import yt_dlp
from src.Utils import get_format, get_opts, jsonCookie, mergeConfig
from src.DTO.ItemDTO import ItemDTO

log = logging.getLogger('download')


class Download:
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
        self.default_ytdl_opts = default_ytdl_opts
        self.debug = debug

        self.canceled = False
        self.tmpfilename = None
        self.status_queue = None
        self.proc = None
        self.loop = None
        self.notifier = None

    def _download(self):
        try:
            def put_status(st):
                self.status_queue.put(
                    {k: v for k, v in st.items() if k in self._ytdlp_fields})

            def put_status_postprocessor(d):
                if d['postprocessor'] == 'MoveFiles' and d['status'] == 'finished':
                    if '__finaldir' in d['info_dict']:
                        filename = os.path.join(
                            d['info_dict']['__finaldir'],
                            os.path.basename(d['info_dict']['filepath'])
                        )
                    else:
                        filename = d['info_dict']['filepath']
                    self.status_queue.put(
                        {
                            'status': 'finished',
                            'filename': filename
                        }
                    )

            # Create temp dir for each download.
            self.tempPath = os.path.join(self.temp_dir, self.info._id)
            if not os.path.exists(self.tempPath):
                os.makedirs(self.tempPath, exist_ok=True)

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
                'socket_timeout': 30,
                'progress_hooks': [put_status],
                'postprocessor_hooks': [put_status_postprocessor],
                **mergeConfig(self.default_ytdl_opts, self.ytdl_opts),
            }

            if self.debug:
                params['verbose'] = True

            if self.info.ytdlp_cookies:
                try:
                    data = jsonCookie(json.loads(self.info.ytdlp_cookies))
                    if not data:
                        logging.warning(
                            f'The cookie string that was provided for {self.info.title} is empty or not in expected spec.')
                    with open(os.path.join(self.tempPath, f'cookie_{self.info._id}.txt'), 'w') as f:
                        f.write(data)

                    params['cookiefile'] = f.name
                except ValueError as e:
                    logging.error(
                        f'Invalid cookies: was provided for {self.info.title} - {str(e)}')

            logging.info(
                f'Downloading {self.info._id=} {self.info.title=}... {params=}')
            ret = yt_dlp.YoutubeDL(params=params).download([self.info.url])

            self.status_queue.put(
                {'status': 'finished' if ret == 0 else 'error'}
            )
        except yt_dlp.utils.YoutubeDLError as exc:
            self.status_queue.put({'status': 'error', 'msg': str(exc)})

        if self.tempPath and self.info._id and os.path.exists(self.tempPath):
            logging.debug(f'Deleting Temp directory: {self.tempPath}')
            shutil.rmtree(self.tempPath, ignore_errors=True)

    async def start(self, notifier):
        if self.manager is None:
            self.manager = multiprocessing.Manager()

        self.status_queue = self.manager.Queue()
        self.proc = multiprocessing.Process(target=self._download)
        self.proc.start()
        self.loop = asyncio.get_running_loop()
        self.notifier = notifier
        self.info.status = 'preparing'
        await self.notifier.updated(self.info)
        asyncio.create_task(self.update_status())
        return await self.loop.run_in_executor(None, self.proc.join)

    def cancel(self):
        if self.running():
            self.proc.kill()
        self.canceled = True

    def close(self):
        if self.started():
            self.proc.close()
            self.status_queue.put(None)

    def running(self):
        try:
            return self.proc is not None and self.proc.is_alive()
        except ValueError:
            return False

    def started(self):
        return self.proc is not None

    async def update_status(self):
        while True:
            status = await self.loop.run_in_executor(None, self.status_queue.get)
            if status is None:
                return

            self.tmpfilename = status.get('tmpfilename')

            if 'filename' in status:
                self.info.filename = os.path.relpath(
                    status.get('filename'), self.download_dir)

                # Set correct file extension for thumbnails
                if self.info.format == 'thumbnail':
                    self.info.filename = re.sub(
                        r'\.webm$', '.jpg', self.info.filename)

            self.info.status = status['status']
            self.info.msg = status.get('msg')

            if 'downloaded_bytes' in status:
                total = status.get('total_bytes') or status.get(
                    'total_bytes_estimate')
                if total:
                    self.info.percent = status['downloaded_bytes'] / \
                        total * 100

            self.info.speed = status.get('speed')
            self.info.eta = status.get('eta')

            await self.notifier.updated(self.info)
