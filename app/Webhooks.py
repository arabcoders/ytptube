import asyncio
import json
import logging
import os
from ItemDTO import ItemDTO
from aiohttp import client

log = logging.getLogger('Webhooks')


class Webhooks:
    targets: list[dict] = {}

    def __init__(self, file: str):
        if os.path.exists(file):
            try:
                if os.path.getsize(file) < 2:
                    raise Exception(f'file is empty.')

                log.info(f'Loading webhooks from {file}')
                with open(file, 'r') as f:
                    self.targets = json.load(f)
            except Exception as e:
                log.error(f'Error loading webhooks from {file}: {e}')
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
        req: dict = target.get('request')
        try:
            log.info(f"Sending {event=} {item.id=} to [{target.get('name')}]")
            async with client.ClientSession() as session:
                headers = req.get('headers', {}) if 'headers' in req else {}
                async with session.request(method=req.get('method', 'POST'), url=req.get('url'), json=item.__dict__, headers=headers) as response:
                    return {
                        'url': req.get('url'),
                        'status': response.status,
                        'text': await response.text()
                    }
        except Exception as e:
            return {
                'url': req.get('url'),
                'status': 500,
                'text': str(e)
            }
