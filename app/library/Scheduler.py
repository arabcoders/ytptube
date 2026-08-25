import asyncio
from collections.abc import Callable
from typing import Any

from aiocron import Cron
from aiohttp import web

from app.library.logging import get_logger

from .Events import EventBus, Events
from .Singleton import Singleton

LOG = get_logger()


class Scheduler(metaclass=Singleton):
    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        self._jobs: dict[str, Cron] = {}

        self._loop: asyncio.AbstractEventLoop | None = loop

    @staticmethod
    def get_instance(loop: asyncio.AbstractEventLoop | None = None) -> "Scheduler":
        return Scheduler(loop=loop)

    async def on_shutdown(self, _: web.Application):
        LOG.debug("Shutting down the scheduler.")

        for job in self._jobs:
            try:
                self._jobs[job].stop()
                LOG.debug("Stopped job '%s'.", job, extra={"job_id": job})
            except Exception as e:
                LOG.exception(
                    "Failed to stop scheduler job '%s'.",
                    job,
                    extra={"job_id": job, "exception_type": type(e).__name__},
                )

        self._jobs = {}

        LOG.debug("Scheduler has been shut down.")

    def attach(self, app: web.Application):
        app.on_shutdown.append(self.on_shutdown)

        async def event_handler(data, _):
            if data and data.data:
                self.add(**data.data)

        EventBus.get_instance().subscribe(Events.SCHEDULE_ADD, event_handler, f"{type(self).__name__}.add")

    def get_all(self) -> dict[str, Cron]:
        return self._jobs

    def get(self, id: str) -> Cron | None:
        return self._jobs.get(id)

    def has(self, id: str) -> bool:
        return id in self._jobs

    def add(
        self, timer: str, func: Callable[..., Any], args: tuple = (), kwargs: dict | None = None, id: str | None = None
    ) -> str:
        if id and id in self._jobs:
            self.remove(id)

        if not self._loop:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)

        job = Cron(spec=timer, func=func, args=args, kwargs=kwargs, uuid=id, start=True, loop=self._loop)

        job_id = str(job.uuid)

        self._jobs[job_id] = job

        LOG.debug("Added job '%s' to run on '%s'.", job_id, timer, extra={"job_id": job_id, "timer": timer})

        return job_id

    def remove(self, id: str | list[str]) -> bool:
        if isinstance(id, list):
            for i in id:
                self.remove(i)
            return True

        if id in self._jobs:
            try:
                self._jobs[id].stop()
            except Exception as e:
                LOG.exception(
                    "Failed to stop scheduler job '%s'.",
                    id,
                    extra={"job_id": id, "exception_type": type(e).__name__},
                )
                return False

            del self._jobs[id]
            LOG.debug("Removed job '%s' from the scheduler.", id, extra={"job_id": id})
            return True

        return False
