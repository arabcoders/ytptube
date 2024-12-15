
import asyncio
import logging

LOG = logging.getLogger('Emitter')


class Emitter:
    """
    This class is used to emit events to the registered emitters.
    """
    emitters: list[callable] = []

    def add_emitter(self, emitter: callable):
        """
            Add an emitter to the list of emitters.

            Args:
                emitter (function): The emitter function. The function must return a coroutine or None.
        """
        self.emitters.append(emitter)

    async def added(self, dl: dict, **kwargs):
        await self.emit('added', dl, **kwargs)

    async def updated(self, dl: dict, **kwargs):
        await self.emit('updated', dl, **kwargs)

    async def completed(self, dl: dict, **kwargs):
        await self.emit('completed', dl, **kwargs)

    async def canceled(self, id: str, dl: dict = None, **kwargs):
        await self.emit('canceled', id, **kwargs)

    async def cleared(self, id: str, dl: dict = None, **kwargs):
        await self.emit('cleared', id, **kwargs)

    async def error(self, dl: dict, message: str, **kwargs):
        await self.emit('error', (dl, message), **kwargs)

    async def warning(self, message: str, **kwargs):
        await self.emit('error', message, **kwargs)

    async def emit(self, event: str, data, **kwargs):
        tasks = []

        for emitter in self.emitters:
            _ret = emitter(event, data, **kwargs)
            if _ret:
                if isinstance(_ret, list):
                    tasks.extend(_ret)
                else:
                    tasks.append(_ret)

        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=60)
        except asyncio.TimeoutError:
            LOG.error(f"Timed out sending event {event}.")
