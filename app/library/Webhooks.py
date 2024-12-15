import asyncio
import logging
import os
from .ItemDTO import ItemDTO
import httpx
from .version import APP_VERSION

LOG = logging.getLogger('Webhooks')

class Webhooks:
    targets: list[dict] = []
    allowed_events: tuple = ('added', 'completed', 'error', 'not_live',)

    def __init__(self, file: str):
        if os.path.exists(file):
            self.load(file)

    def load(self, file: str):
        try:
            if os.path.getsize(file) < 2:
                raise Exception(f'file is empty.')

            LOG.info(f'Loading webhooks from {file}')
            from .Utils import load_file
            (target, status, error) = load_file(file, list)
            if not status:
                raise Exception(f'{error}')

            self.targets = target
        except Exception as e:
            LOG.error(f'Error loading webhooks from {file}: {e}')
            pass

    async def send(self, event: str, item: ItemDTO) -> list[dict]:
        if len(self.targets) == 0:
            return []

        if not isinstance(item, ItemDTO):
            return []

        tasks = []

        for target in self.targets:
            allowed_events = target.get('on') if 'on' in target else []
            if len(allowed_events) > 0 and event not in allowed_events:
                continue

            tasks.append(self.__send(event, target, item))

        return await asyncio.gather(*tasks)

    async def __send(self, event: str, target: dict, item: ItemDTO) -> dict:
        from .config import Config
        req: dict = target.get('request')
        try:
            LOG.info(f"Sending {event=} {item.id=} to [{target.get('name')}]")
            async with httpx.AsyncClient() as client:
                request_type = req.get('type', 'json')

                reqBody = {
                    'method': req.get('method', 'POST'),
                    'url': req.get('url'),
                    'headers': {
                        'User-Agent': f"YTPTube/{APP_VERSION}"
                    },
                }

                if req.get('headers', None):
                    reqBody['headers'].update(req.get('headers'))

                match(request_type):
                    case 'json':
                        reqBody['json'] = item.__dict__
                        reqBody['headers']['Content-Type'] = 'application/json'
                    case _:
                        reqBody['data'] = item.__dict__
                        reqBody['headers']['Content-Type'] = 'application/x-www-form-urlencoded'

                response = await client.request(**reqBody)

                respData = {
                    'url': req.get('url'),
                    'status': response.status_code,
                    'text': response.text
                }

                msg = f"[{target.get('name')}] Response to [{event=} {item.id=}] [status: {response.status_code}]."
                if Config.get_instance().debug and respData.get('text'):
                    msg += f" [Body: {respData.get('text','??')}]"

                LOG.info(msg)

                return respData
        except Exception as e:
            return {
                'url': req.get('url'),
                'status': 500,
                'text': str(e)
            }

    def emit(self, event, data, **kwargs):
        if len(self.targets) < 1 or event not in self.allowed_events:
            return False

        return self.send(event, data)
