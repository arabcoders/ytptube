import asyncio
import logging
from typing import Awaitable

from .Singleton import Singleton
from .EventsSubscriber import Events

LOG = logging.getLogger("Emitter")


class Emitter(metaclass=Singleton):
    """
    This class is used to emit events to the registered emitters.
    """

    emitters: list[(str, Awaitable)] = []
    """The emitters for the events."""

    _instance = None

    def __init__(self):
        Emitter._instance = self

    @staticmethod
    def get_instance():
        """
        Get the instance of the Emitter.

        Returns:
            Emitter: The instance of the Emitter
        """
        if not Emitter._instance:
            Emitter._instance = Emitter()
        return Emitter._instance

    def add_emitter(self, emitter: list[Awaitable] | Awaitable, local: bool = False) -> "Emitter":
        """
        Add an emitter to the list of emitters.

        Args:
            emitter (Awaitable|list[Awaitable]): The emitter function. The function must return a coroutine or None.
            local (bool): Mark the emitter as target for local events.

        Returns:
            Emitter: The instance of the Emitter
        """
        if not isinstance(emitter, list):
            emitter = [emitter]

        for e in emitter:
            self.emitters.append((local, e))

        return self

    async def added(self, dl: dict, local: bool = False, **kwargs):
        await self.emit(Events.ADDED, data=dl, local=local, **kwargs)

    async def updated(self, dl: dict, local: bool = False, **kwargs):
        await self.emit(Events.UPDATED, data=dl, local=local, **kwargs)

    async def completed(self, dl: dict, local: bool = False, **kwargs):
        await self.emit(Events.COMPLETED, data=dl, local=local, **kwargs)

    async def cancelled(self, dl: dict, local: bool = False, **kwargs):
        await self.emit(Events.CANCELLED, data=dl, local=local, **kwargs)

    async def cleared(self, dl: dict | None = None, local: bool = False, **kwargs):
        await self.emit(Events.CLEARED, data=dl, local=local, **kwargs)

    async def error(self, message: str, data: dict = {}, local: bool = False, **kwargs):
        msg = {"type": "error", "message": message, "data": {}}
        if data:
            msg.update({"data": data})
        await self.emit(Events.ERROR, data=msg, local=local, **kwargs)

    async def info(self, message: str, data: dict = {}, local: bool = False, **kwargs):
        msg = {"type": "info", "message": message, "data": {}}
        if data:
            msg.update({"data": data})
        await self.emit(Events.LOG_INFO, data=msg, local=local, **kwargs)

    async def success(self, message: str, data: dict = {}, local: bool = False, **kwargs):
        msg = {"type": "success", "message": message, "data": {}}
        if data:
            msg.update({"data": data})
        await self.emit(Events.LOG_SUCCESS, data=msg, local=local, **kwargs)

    async def emit(self, event: str, data, local: bool = False, **kwargs):
        """
        Emit an event.

        Args:
            event (str): The event to emit.
            data (dict): The data to send with the event.
            local (bool): If the event should be sent to the local emitters only.
            kwargs: Additional arguments to pass to the emitters.

        Returns:
            None
        """
        tasks = []

        for emitter in self.emitters:
            try:
                isLocal, callback = emitter
                if local and not isLocal:
                    continue

                _ret = callback(event, data, **kwargs)
                if _ret:
                    if isinstance(_ret, list):
                        tasks.extend(_ret)
                    else:
                        tasks.append(_ret)
            except Exception as e:
                LOG.error(f"Emitter '{callback}' failed with error '{e}'.")

        if len(tasks) < 1:
            return

        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=60)
        except asyncio.CancelledError:
            LOG.error(f"Cancelled sending event '{event}'.")
        except asyncio.TimeoutError:
            LOG.error(f"Timed out sending event '{event}'.")
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Failed to send event '{event}'. '{str(e)}'.")
