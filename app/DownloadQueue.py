import asyncio
from email.utils import formatdate
import logging
import os
import time
import yt_dlp
from sqlite3 import Connection
from Config import Config
from Download import Download
from ItemDTO import ItemDTO
from DataStore import DataStore
from Utils import Notifier, ObjectSerializer, calcDownloadPath, ExtractInfo, isDownloaded, mergeConfig
from AsyncPool import AsyncPool
from concurrent.futures import ThreadPoolExecutor

LOG = logging.getLogger('DownloadQueue')
TYPE_DONE: str = 'done'
TYPE_QUEUE: str = 'queue'


class DownloadQueue:
    config: Config = None
    notifier: Notifier = None
    serializer: ObjectSerializer = None
    queue: DataStore = None
    done: DataStore = None
    event: asyncio.Event = None

    def __init__(self, notifier: Notifier, connection: Connection, serializer: ObjectSerializer):
        self.config = Config.get_instance()
        self.notifier = notifier
        self.serializer = serializer
        self.done = DataStore(type=TYPE_DONE, connection=connection)
        self.queue = DataStore(type=TYPE_QUEUE, connection=connection)
        self.done.load()
        self.queue.load()

    async def initialize(self):
        self.event = asyncio.Event()
        LOG.info(f'Using {self.config.max_workers} workers for downloading.')

        asyncio.create_task(
            self.__download_pool() if self.config.max_workers > 1 else self.__download()
        )

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

        options: dict = {}

        error: str = None
        live_in: str = None

        eventType = entry.get('_type') or 'video'
        if eventType == 'playlist':
            entries = entry['entries']
            playlist_index_digits = len(str(len(entries)))
            results = []
            for index, etr in enumerate(entries, start=1):
                etr['playlist'] = entry.get('id')
                etr['playlist_index'] = '{{0:0{0:d}d}}'.format(playlist_index_digits).format(index)
                for property in ('id', 'title', 'uploader', 'uploader_id'):
                    if property in entry:
                        etr[f'playlist_{property}'] = entry.get(property)

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
        elif (eventType == 'video' or eventType.startswith('url')) and 'id' in entry and 'title' in entry:
            # check if the video is live stream.
            if 'live_status' in entry and entry.get('live_status') == 'is_upcoming':
                if 'release_timestamp' in entry and entry.get('release_timestamp'):
                    live_in = formatdate(entry.get('release_timestamp'))
                else:
                    error = 'Live stream not yet started. And no date is set.'
            else:
                error = entry.get('msg', None)

            LOG.debug(f"entry: {entry.get('id', None)} - {entry.get('webpage_url', None)} - {entry.get('url', None)}")

            if self.done.exists(key=entry['id'], url=entry.get('webpage_url') or entry.get('url')):
                item = self.done.get(key=entry['id'], url=entry.get('webpage_url') or entry['url'])

                LOG.debug(f'Item [{item.info.title}] already downloaded. Removing from history.')

                await self.clear([item.info._id])

            try:
                item = self.queue.get(key=entry.get('id'), url=entry.get('webpage_url') or entry.get('url'))
                if item is not None:
                    err_message = f'Item [{item.info.id}: {item.info.title}] already in download queue.'
                    LOG.info(err_message)
                    return {'status': 'error', 'msg': err_message}
            except KeyError:
                pass

            is_manifestless = entry.get('is_manifestless', False)
            options.update({'is_manifestless': is_manifestless})

            dl = ItemDTO(
                id=entry.get('id'),
                title=entry.get('title'),
                url=entry.get('webpage_url') or entry.get('url'),
                quality=quality,
                format=format,
                folder=folder,
                ytdlp_cookies=ytdlp_cookies,
                ytdlp_config=ytdlp_config,
                output_template=output_template if output_template else self.config.output_template,
                datetime=formatdate(time.time()),
                error=error,
                is_live=entry.get('is_live', None) or entry.get('live_status', None) in ['is_live', 'is_upcoming'] or live_in,
                live_in=live_in,
                options=options
            )

            try:
                download_dir = calcDownloadPath(basePath=self.config.download_path, folder=folder)
            except Exception as e:
                LOG.exception(e)
                return {'status': 'error', 'msg': str(e)}

            output_chapter = self.config.output_template_chapter

            for property, value in entry.items():
                if property.startswith("playlist"):
                    dl.output_template = dl.output_template.replace(f"%({property})s", str(value))

            dlInfo: Download = Download(
                info=dl,
                download_dir=download_dir,
                temp_dir=self.config.temp_path,
                output_template_chapter=output_chapter,
                default_ytdl_opts=self.config.ytdl_options,
                debug=bool(self.config.ytdl_debug)
            )

            if dlInfo.info.live_in:
                dlInfo.info.status = 'not_live'
                itemDownload = self.done.put(dlInfo)
                NotifyEvent = 'completed'
            elif self.config.allow_manifestless is False and is_manifestless is True:
                dlInfo.info.status = 'error'
                dlInfo.info.error = 'Video is in Post-Live Manifestless mode.'
                itemDownload = self.done.put(dlInfo)
                NotifyEvent = 'completed'
            else:
                NotifyEvent = 'added'
                itemDownload = self.queue.put(dlInfo)
                self.event.set()

            await self.notifier.emit(NotifyEvent, itemDownload.info)

            return {
                'status': 'ok'
            }
        elif eventType.startswith('url'):
            return await self.add(
                entry=entry.get('url'),
                quality=quality,
                format=format,
                folder=folder,
                ytdlp_config=ytdlp_config,
                ytdlp_cookies=ytdlp_cookies,
                output_template=output_template,
                already=already
            )

        return {
            'status': 'error',
            'msg': f'Unsupported resource "{eventType}"'
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

        LOG.info(f'Adding {url=} {quality=} {format=} {folder=} {output_template=} {ytdlp_cookies=} {ytdlp_config=}')

        already = set() if already is None else already

        if url in already:
            LOG.info('recursion detected, skipping.')
            return {'status': 'ok'}

        already.add(url)

        try:
            downloaded, id_dict = self.isDownloaded(url)
            if downloaded is True:
                message = f"[ { id_dict.get('id') } ]: has been downloaded already."
                LOG.info(message)
                return {'status': 'error', 'msg': message}

            started = time.perf_counter()
            LOG.debug(f'extract_info: checking {url=}')

            with ThreadPoolExecutor(1) as executor:
                entry = await asyncio.wait_for(
                    fut=asyncio.get_running_loop().run_in_executor(
                        executor,
                        ExtractInfo,
                        mergeConfig(self.config.ytdl_options, ytdlp_config),
                        url,
                        bool(self.config.ytdl_debug)
                    ),
                    timeout=self.config.extract_info_timeout)

            if not entry:
                return {'status': 'error', 'msg': 'Unable to extract info check logs.'}

            LOG.debug(f'extract_info: for [{url=}] is done in {time.perf_counter() - started}. Length: {len(entry)}')
        except yt_dlp.utils.ExistingVideoReached as exc:
            LOG.error(f'Video has been downloaded already and recorded in archive.log file. {str(exc)}')
            return {'status': 'error', 'msg': 'Video has been downloaded already and recorded in archive.log file.'}
        except yt_dlp.utils.YoutubeDLError as exc:
            LOG.error(f'YoutubeDLError: Unable to extract info. {str(exc)}')
            return {'status': 'error', 'msg': str(exc)}
        except asyncio.exceptions.TimeoutError as exc:
            LOG.error(f'TimeoutError: Unable to extract info. {str(exc)}')
            return {'status': 'error', 'msg': f'TimeoutError: {self.config.extract_info_timeout}s reached Unable to extract info.'}

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
            try:
                item = self.queue.get(key=id)
            except KeyError as e:
                LOG.warning(f'Requested cancel for non-existent download {id=}. {str(e)}')
                continue

            itemMessage = f"{id=} {item.info.id=} {item.info.title=}"

            if item.started() is True:
                LOG.debug(f'Canceling {itemMessage}')
                item.cancel()
                LOG.info(f'Cancelled {itemMessage}')

            else:
                item.close()
                LOG.debug(f'Deleting from queue {itemMessage}')
                self.queue.delete(id)
                await self.notifier.canceled(id)
                self.done.put(item)
                await self.notifier.completed(item)
                LOG.info(f'Deleted from queue {itemMessage}')

        return {'status': 'ok'}

    async def clear(self, ids):
        for id in ids:
            try:
                item = self.done.get(key=id)
            except KeyError as e:
                LOG.warning(f'Requested delete for non-existent download {id=}. {str(e)}')
                continue

            itemMessage = f"{id=} {item.info.id=} {item.info.title=}"
            LOG.debug(f'Deleting completed download {itemMessage}')
            self.done.delete(id)
            await self.notifier.cleared(id)
            LOG.info(f'Deleted completed download {itemMessage}')

        return {'status': 'ok'}

    def get(self) -> dict[str, list[dict[str, ItemDTO]]]:
        items = {'queue': {}, 'done': {}}

        for k, v in self.queue.saved_items():
            items['queue'][k] = v

        for k, v in self.done.saved_items():
            items['done'][k] = v

        for k, v in self.queue.items():
            if not k in items['queue']:
                items['queue'][k] = v.info

        for k, v in self.done.items():
            if not k in items['done']:
                items['done'][k] = v.info

        return items

    async def __download_pool(self):
        async with AsyncPool(
            loop=asyncio.get_running_loop(),
            num_workers=self.config.max_workers,
            worker_co=self.__downloadFile,
            name='download_pool',
            logger=logging.getLogger('WorkerPool'),
        ) as executor:
            lastLog = time.time()

            while True:
                while True:
                    if executor.has_open_workers() is True:
                        break
                    if time.time() - lastLog > 120:
                        lastLog = time.time()
                        LOG.info(f'Waiting for worker to be free.')
                    await asyncio.sleep(1)

                while not self.queue.hasDownloads():
                    LOG.info(f"Waiting for item to download. '{executor.get_available_workers()}' free workers.")
                    await self.event.wait()
                    self.event.clear()
                    LOG.debug(f"Cleared wait event.")

                entry = self.queue.getNextDownload()
                await asyncio.sleep(0.2)

                if entry is None:
                    continue

                LOG.debug(f"Pushing {entry=} to executor.")

                if entry.started() is False and entry.is_canceled() is False:
                    await executor.push(id=entry.info._id, entry=entry)
                    LOG.debug(f"Pushed {entry=} to executor.")
                    await asyncio.sleep(1)

    async def __download(self):
        while True:
            while self.queue.empty():
                LOG.info('Waiting for item to download.')
                await self.event.wait()
                self.event.clear()

            id, entry = self.queue.next()
            await self.__downloadFile(id, entry)

    async def __downloadFile(self, id: str, entry: Download):
        LOG.info(f'Queuing {id=} - {entry.info.title=} - {entry.info.url=} - {entry.info.folder=}.')

        await entry.start(self.notifier)

        if entry.info.status != 'finished':
            if entry.tmpfilename and os.path.isfile(entry.tmpfilename):
                try:
                    os.remove(entry.tmpfilename)
                except:
                    pass

            entry.info.status = 'error'

        entry.close()

        if self.queue.exists(key=id):

            self.queue.delete(key=id)

            if entry.is_canceled() is True:
                await self.notifier.canceled(id)
                entry.info.status = 'canceled'
                entry.info.error = 'Canceled by user.'

            self.done.put(value=entry)
            await self.notifier.completed(entry.info)

        self.event.set()

    def isDownloaded(self, url: str) -> tuple[bool, dict[str | None, str | None, str | None]]:
        if not url or not self.config.keep_archive:
            return False, None

        return isDownloaded(self.config.ytdl_options.get('download_archive', None), url)
