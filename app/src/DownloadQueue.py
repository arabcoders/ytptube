import asyncio
from email.utils import formatdate
import logging
import os
import yt_dlp
from sqlite3 import Connection
from src.Config import Config
from src.Notifier import Notifier
from src.Download import Download
from src.DTO.ItemDTO import ItemDTO
from src.DataStore import DataStore
from src.Utils import ObjectSerializer, calcDownloadPath, ExtractInfo, mergeConfig
from datetime import datetime, timezone

log = logging.getLogger('DownloadQueue')


class DownloadQueue:
    config: Config = None
    notifier: Notifier = None
    connection: Connection = None
    serializer: ObjectSerializer = None
    queue: DataStore = None
    done: DataStore = None
    event: asyncio.Event = None

    def __init__(self, config: Config, notifier: Notifier, connection: Connection, serializer: ObjectSerializer):
        self.config = config
        self.notifier = notifier
        self.connection = connection
        self.serializer = serializer
        self.done = DataStore(type='done', config=self.config)
        self.queue = DataStore(type='queue', config=self.config)
        self.done.load()
        self.queue.load()

    async def initialize(self):
        self.event = asyncio.Event()
        asyncio.create_task(self.__download())

    async def __add_entry(
        self,
        entry: dict,
        quality: str,
        format: str,
        folder: str,
        ytdlp_config: dict = {},
        ytdlp_cookies: str = '',
        output_template: str = '',
        already=None
    ):
        if not entry:
            return {'status': 'error', 'msg': 'Invalid/empty data was given.'}

        error: str = None

        if 'live_status' in entry and 'release_timestamp' in entry and entry.get('live_status') == 'is_upcoming':
            dt_ts = datetime.fromtimestamp(
                entry.get('release_timestamp'), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S %z')
            error = f"Live stream is scheduled to start at {dt_ts}"
        else:
            error = entry['msg'] if 'msg' in entry else None

        etype = entry.get('_type') or 'video'
        if etype == 'playlist':
            entries = entry['entries']
            log.info(f'playlist detected with {len(entries)} entries')
            playlist_index_digits = len(str(len(entries)))
            results = []
            for index, etr in enumerate(entries, start=1):
                etr['playlist'] = entry['id']
                etr['playlist_index'] = '{{0:0{0:d}d}}'.format(
                    playlist_index_digits).format(index)
                for property in ('id', 'title', 'uploader', 'uploader_id'):
                    if property in entry:
                        etr[f'playlist_{property}'] = entry[property]

                results.append(
                    await self.__add_entry(
                        entry=etr,
                        quality=quality,
                        format=format,
                        folder=folder,
                        ytdlp_config=ytdlp_config,
                        ytdlp_cookies=ytdlp_cookies,
                        output_template=output_template,
                        already=already
                    )
                )

            if any(res['status'] == 'error' for res in results):
                return {'status': 'error', 'msg': ', '.join(res['msg'] for res in results if res['status'] == 'error' and 'msg' in res)}

            return {'status': 'ok'}
        elif etype == 'video' or etype.startswith('url') and 'id' in entry and 'title' in entry:
            if not self.queue.exists(entry['id']):
                dl = ItemDTO(
                    id=entry['id'],
                    title=entry['title'],
                    url=entry.get('webpage_url') or entry['url'],
                    quality=quality,
                    format=format,
                    folder=folder,
                    ytdlp_cookies=ytdlp_cookies,
                    ytdlp_config=ytdlp_config,
                    output_template=output_template if output_template else self.config.output_template,
                    error=error,
                    is_live=entry['is_live'] if 'is_live' in entry else None,
                )

                logging.info(f'adding {dl.json()}')

                try:
                    dldirectory = calcDownloadPath(
                        basePath=self.config.download_path,
                        folder=folder
                    )
                except Exception as e:
                    return {'status': 'error', 'msg': str(e)}

                output_chapter = self.config.output_template_chapter

                for property, value in entry.items():
                    if property.startswith("playlist"):
                        dl.output_template = dl.output_template.replace(
                            f"%({property})s", str(value))

                self.queue.put(
                    Download(
                        info=dl,
                        download_dir=dldirectory,
                        temp_dir=self.config.temp_path,
                        output_template_chapter=output_chapter,
                        default_ytdl_opts=self.config.ytdl_options,
                        debug=bool(self.config.ytdl_debug)
                    )
                )

                self.event.set()
                await self.notifier.added(dl)

            return {
                'status': 'ok'
            }
        elif etype.startswith('url'):
            return await self.add(
                entry=entry['url'],
                quality=quality,
                format=format,
                folder=folder,
                already=already
            )

        return {
            'status': 'error',
            'msg': f'Unsupported resource "{etype}"'
        }

    async def add(
        self,
        url: str,
        quality: str,
        format: str,
        folder: str,
        ytdlp_config: dict = {},
        ytdlp_cookies: str = '',
        output_template: str = '',
        already=None
    ):
        ytdlp_config = ytdlp_config if ytdlp_config else {}

        log.info(
            f'adding {url}: {quality=} {format=} {folder=} {output_template=} {ytdlp_cookies=} {ytdlp_config=}')

        already = set() if already is None else already
        if url in already:
            log.info('recursion detected, skipping')
            return {'status': 'ok'}
        else:
            already.add(url)
        try:
            entry = await asyncio.get_running_loop().run_in_executor(
                None,
                ExtractInfo,
                mergeConfig(self.config.ytdl_options, ytdlp_config),
                url,
                bool(self.config.ytdl_debug)
            )
            if not entry:
                return {
                    'status': 'error',
                    'msg': 'No metadata, most likely video has been downloaded before.' if self.config.keep_archive else 'Unable to extract info check logs.'
                }
            logging.debug(f'entry: extract info says: {entry}')
        except yt_dlp.utils.YoutubeDLError as exc:
            return {'status': 'error', 'msg': str(exc)}

        return await self.__add_entry(
            entry=entry,
            quality=quality,
            format=format,
            folder=folder,
            ytdlp_config=ytdlp_config,
            ytdlp_cookies=ytdlp_cookies,
            output_template=output_template,
            already=already,
        )

    async def cancel(self, ids):
        for id in ids:
            if not self.queue.exists(id):
                log.warn(f'requested cancel for non-existent download {id}')
                continue
            if self.queue.get(id).started():
                self.queue.get(id).cancel()
            else:
                self.queue.delete(id)
                await self.notifier.canceled(id)

        return {'status': 'ok'}

    async def clear(self, ids):
        for id in ids:
            if not self.done.exists(id):
                log.warn(f'requested delete for non-existent download {id}')
                continue
            self.done.delete(id)
            await self.notifier.cleared(id)

        return {'status': 'ok'}

    def get(self) -> dict[str, list[dict[str, ItemDTO]]]:
        items = {'queue': {}, 'done': {}}

        for k, v in self.queue.items():
            items['queue'][k] = v.info

        for k, v in self.done.items():
            items['done'][k] = v.info

        return items

    async def __download(self):
        while True:
            while self.queue.empty():
                log.info('waiting for item to download.')
                await self.event.wait()
                self.event.clear()

            id, entry = self.queue.next()
            log.info(f'downloading {id=} - {entry.info.title}')

            await entry.start(self.notifier)

            if entry.info.status != 'finished':
                if entry.tmpfilename and os.path.isfile(entry.tmpfilename):
                    try:
                        os.remove(entry.tmpfilename)
                    except:
                        pass

                entry.info.status = 'error'

            entry.close()

            if self.queue.exists(id):
                self.queue.delete(id)
                if entry.canceled:
                    await self.notifier.canceled(id)
                else:
                    self.done.put(entry)
                    await self.notifier.completed(entry.info)
