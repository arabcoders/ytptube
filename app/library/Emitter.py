import asyncio
import logging

LOG = logging.getLogger("Emitter")


class Emitter:
    """
    This class is used to emit events to the registered emitters.
    """

    emitters: list[callable] = []  # type: ignore

    def add_emitter(self, emitter: callable):  # type: ignore
        """
        Add an emitter to the list of emitters.

        Args:
            emitter (function): The emitter function. The function must return a coroutine or None.
        """
        self.emitters.append(emitter)

    async def added(self, dl: dict, **kwargs):
        await self.emit("added", dl, **kwargs)

    async def updated(self, dl: dict, **kwargs):
        await self.emit("updated", dl, **kwargs)

    async def completed(self, dl: dict, **kwargs):
        await self.emit("completed", dl, **kwargs)

    async def canceled(self, id: str, dl: dict | None = None, **kwargs):
        await self.emit("canceled", id, **kwargs)

    async def cleared(self, id: str, dl: dict | None = None, **kwargs):
        await self.emit("cleared", id, **kwargs)

    async def error(self, message: str, data: dict = {}, **kwargs):
        msg = {"status": "error", "message": message, "data": {}}
        if data:
            msg.update({"data": data})
        await self.emit("error", msg, **kwargs)

    async def warning(self, message: str, **kwargs):
        await self.emit("error", message, **kwargs)

    async def info(self, message: str, data: dict = {}, **kwargs):
        msg = {"type": "info", "message": message, "data": {}}
        if data:
            msg.update({"data": data})
        await self.emit("log_info", msg, **kwargs)

    async def success(self, message: str, data: dict = {}, **kwargs):
        msg = {"type": "success", "message": message, "data": {}}
        if data:
            msg.update({"data": data})
        await self.emit("log_success", msg, **kwargs)

    async def emit(self, event: str, data, **kwargs):
        tasks = []

        for emitter in self.emitters:
            try:
                _ret = emitter(event, data, **kwargs)
                if _ret:
                    if isinstance(_ret, list):
                        tasks.extend(_ret)
                    else:
                        tasks.append(_ret)
            except Exception as e:
                LOG.error(f"Emitter '{emitter}' failed with error '{e}'.")

        if len(tasks) < 1:
            return

        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=60)
        except asyncio.TimeoutError:
            LOG.error(f"Timed out sending event '{event}'.")
