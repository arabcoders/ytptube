import asyncio
import logging

from aiocron import Cron
from aiohttp import web

from .Events import EventBus, Events
from .Singleton import Singleton

LOG = logging.getLogger("scheduler")


class Scheduler(metaclass=Singleton):
    """
    This class is used to manage the schedule.
    """

    _jobs: dict[str, Cron] = {}
    """The scheduled jobs."""

    _instance = None
    """The instance of the class."""

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        Scheduler._instance = self

        self._loop = loop or asyncio.get_event_loop()

        EventBus.get_instance().subscribe(
            Events.SCHEDULE_ADD,
            lambda data, _, **kwargs: self.add(**data.data),  # noqa: ARG005
            f"{__class__.__name__}.add",
        )

    @staticmethod
    def get_instance() -> "Scheduler":
        """
        Get the instance of the class.

        Returns:
            Scheduler: The instance of the class

        """
        if not Scheduler._instance:
            Scheduler._instance = Scheduler()
        return Scheduler._instance

    async def on_shutdown(self, _: web.Application):
        """
        Do any jobs before shutdown.

        Args:
            _: The aiohttp application.

        """
        LOG.debug("Shutting down the scheduler.")

        for job in self._jobs:
            try:
                self._jobs[job].stop()
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to stop job '{job}'. Error message '{e!s}'.")

        self._jobs = {}

        LOG.debug("Scheduler has been shut down.")

    def attach(self, app: web.Application):
        app.on_shutdown.append(self.on_shutdown)

    def get_all(self) -> dict[str, Cron]:
        """Return the jobs."""
        return self._jobs

    def get(self, id: str) -> Cron | None:
        """Return the job by id."""
        return self._jobs.get(id)

    def add(
        self, timer: str, func: callable, args: tuple = (), kwargs: dict | None = None, id: str | None = None
    ) -> str:
        """
        Add a job to the schedule.

        Args:
            timer (str): The timer for the job.
            func (callable): The function to call.
            args (tuple): The arguments to pass to the function.
            kwargs (dict): The keyword arguments to pass to the function.
            id (str): The id of the job.

        Returns:
            str: The id of the job

        """
        if id and id in self._jobs:
            self.remove(id)

        job = Cron(spec=timer, func=func, args=args, kwargs=kwargs, uuid=id, start=True, loop=self._loop)

        job_id = str(job.uuid)

        self._jobs[job_id] = job

        LOG.debug(f"Added '{job_id}' to the scheduler.")

        return job_id

    def remove(self, id: str | list[str]) -> bool:
        """
        Remove a job from the schedule.

        Args:
            id (str|list[str]): The id of the job to remove.

        Returns:
            bool: True if the job was removed, False otherwise

        """
        if isinstance(id, list):
            for i in id:
                self.remove(i)
            return True

        if id in self._jobs:
            try:
                self._jobs[id].stop()
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to stop job '{id}'. Error message '{e!s}'.")
                return False

            del self._jobs[id]
            LOG.debug(f"Removed job '{id}' from the schedule.")
            return True

        return False
