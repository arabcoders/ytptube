import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from aiohttp import web

from .config import Config
from .encoder import Encoder
from .Events import EventBus, Events, error, info, success
from .Scheduler import Scheduler
from .Singleton import Singleton
from .Utils import clean_item

LOG = logging.getLogger("tasks")


@dataclass(kw_only=True)
class Task:
    id: str
    name: str
    url: str
    folder: str = ""
    preset: str = ""
    timer: str = ""
    template: str = ""
    cli: str = ""

    def serialize(self) -> dict:
        return self.__dict__

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.serialize().get(key, default)


class Tasks(metaclass=Singleton):
    """
    This class is used to manage the tasks.
    """

    _tasks: list[Task] = []
    """The tasks."""

    _instance = None
    """The instance of the Tasks."""

    def __init__(
        self,
        file: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        config: Config | None = None,
        encoder: Encoder | None = None,
        client: httpx.AsyncClient | None = None,
        scheduler: Scheduler | None = None,
    ):
        Tasks._instance = self

        config = config or Config.get_instance()

        self._debug = config.debug
        self._default_preset = config.default_preset
        self._file = file or os.path.join(config.config_path, "tasks.json")
        self._client = client or httpx.AsyncClient()
        self._encoder = encoder or Encoder()
        self._loop = loop or asyncio.get_event_loop()
        self._scheduler = scheduler or Scheduler.get_instance()
        self._notify = EventBus.get_instance()

        if os.path.exists(self._file) and "600" != oct(os.stat(self._file).st_mode)[-3:]:
            try:
                os.chmod(self._file, 0o600)
            except Exception:
                pass

    @staticmethod
    def get_instance() -> "Tasks":
        """
        Get the instance of the class.

        Returns:
            Tasks: The instance of the class.

        """
        if not Tasks._instance:
            Tasks._instance = Tasks()

        return Tasks._instance

    async def on_shutdown(self, _: web.Application):
        pass

    def attach(self, _: web.Application):
        """
        Attach the tasks to the aiohttp application.

        Args:
            _ (web.Application): The aiohttp application.

        """
        self.load()
        self._notify.subscribe(
            Events.TASKS_ADD,
            lambda data, _, **kwargs: self.save(**data.data),  # noqa: ARG005
            f"{__class__.__name__}.add",
        )

    def get_all(self) -> list[Task]:
        """Return the tasks."""
        return self._tasks

    def load(self) -> "Tasks":
        """
        Load the tasks.

        Returns:
            Tasks: The current instance.

        """
        self.clear()

        if not os.path.exists(self._file) or os.path.getsize(self._file) < 10:
            return self

        LOG.info(f"Loading tasks from '{self._file}'.")
        try:
            with open(self._file) as f:
                tasks = json.load(f)
        except Exception as e:
            LOG.error(f"Failed to parse tasks from '{self._file}'. '{e!s}'.")
            return self

        if not tasks or len(tasks) < 1:
            LOG.info(f"No tasks were defined in '{self._file}'.")
            return self

        need_save = False
        for i, task in enumerate(tasks):
            try:
                task, task_status = clean_item(task, keys=("cookies", "config"))
                self.validate(task)
                task = Task(**task)
                if task_status:
                    need_save = True
            except Exception as e:
                LOG.error(f"Failed to parse task at list position '{i}'. '{e!s}'.")
                continue

            self._tasks.append(task)

            if not task.timer:
                continue

            try:
                self._scheduler.add(timer=task.timer, func=self._runner, args=(task,), id=task.id)

                try:
                    from cronsim import CronSim

                    cs = CronSim(task.timer, datetime.now(UTC))
                    schedule_time = cs.explain()
                except Exception:
                    schedule_time = task.timer

                LOG.info(f"Task '{i}: {task.name}' queued to be executed '{schedule_time}'.")
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to queue task '{i}: {task.name}'. '{e!s}'.")

        if need_save:
            LOG.info("Updating tasks file to remove old keys.")
            self.save(self.get_all())

        return self

    def clear(self, shutdown: bool = False) -> "Tasks":
        """
        Clear all tasks.

        Returns:
            Tasks: The current instance.

        """
        if len(self._tasks) < 1:
            return self

        for task in self._tasks:
            try:
                LOG.info(f"Stopping task '{task.id}: {task.name}'.")
                self._scheduler.remove(task.id)
            except Exception as e:
                if not shutdown:
                    LOG.exception(e)
                    LOG.error(f"Failed to stop task '{task.id}: {task.name}'. '{e!s}'.")

        self._tasks.clear()

        return self

    def validate(self, task: Task | dict) -> bool:
        """
        Validate the task.

        Args:
            task (Task|dict): The task to validate.

        Returns:
            bool: True if the task is valid, False otherwise.

        """
        if not isinstance(task, dict):
            if not isinstance(task, Task):
                msg = "Invalid task type."
                raise ValueError(msg)  # noqa: TRY004

            task = task.serialize()

        if not task.get("name"):
            msg = "No name found."
            raise ValueError(msg)

        if not task.get("url"):
            msg = "No URL found."
            raise ValueError(msg)

        if task.get("timer"):
            try:
                from cronsim import CronSim

                CronSim(task.get("timer"), datetime.now(UTC))
            except Exception as e:
                msg = f"Invalid timer format. '{e!s}'."
                raise ValueError(msg) from e

        if task.get("cli"):
            try:
                from .Utils import arg_converter

                arg_converter(args=task.get("cli"))
            except Exception as e:
                msg = f"Invalid command options for yt-dlp. '{e!s}'."
                raise ValueError(msg) from e

        return True

    def save(self, tasks: list[Task | dict]) -> "Tasks":
        """
        Save the tasks.

        Args:
            tasks (list[Task]): The tasks to save.

        Returns:
            Tasks: The current instance.

        """
        for i, task in enumerate(tasks):
            try:
                if not isinstance(task, Task):
                    task = Task(**task)
                    tasks[i] = task
            except Exception as e:
                LOG.error(f"Failed to save task '{i}' unable to parse task. '{e!s}'.")
                continue

            try:
                self.validate(task)
            except ValueError as e:
                LOG.error(f"Failed to add task '{i}: {task.name}'. '{e}'.")
                continue

        try:
            with open(self._file, "w") as f:
                json.dump(obj=[task.serialize() for task in tasks], fp=f, indent=4)

            LOG.info(f"Tasks saved to '{self._file}'.")
        except Exception as e:
            LOG.error(f"Failed to save tasks to '{self._file}'. '{e!s}'.")

        return self

    async def _runner(self, task: Task):
        """
        Run the task.

        Args:
            task (Task): The task to run.

        Returns:
            None

        """
        try:
            timeNow = datetime.now(UTC).isoformat()
            started = time.time()
            if not task.url:
                LOG.error(f"Failed to dispatch task '{task.id}: {task.name}'. No URL found.")
                return

            preset: str = str(task.preset or self._default_preset)
            folder: str = task.folder if task.folder else ""
            template: str = task.template if task.template else ""
            cli: str = task.cli if task.cli else ""

            LOG.info(f"Task '{task.id}: {task.name}' dispatched at '{timeNow}'.")

            tasks = []
            tasks.append(
                self._notify.emit(Events.LOG_INFO, data=info(f"Task '{task.name}' dispatched at '{timeNow}'."))
            )
            tasks.append(
                self._notify.emit(
                    Events.ADD_URL,
                    data={
                        "url": task.url,
                        "preset": preset,
                        "folder": folder,
                        "template": template,
                        "cli": cli,
                    },
                    id=task.id,
                ),
            )

            await asyncio.wait_for(asyncio.gather(*tasks), timeout=None)

            timeNow = datetime.now(UTC).isoformat()

            ended = time.time()
            LOG.info(f"Task '{task.id}: {task.name}' completed at '{timeNow}' took '{ended - started:.2f}' seconds.")

            await self._notify.emit(
                Events.LOG_SUCCESS,
                data=success(f"Task '{task.name}' completed in '{ended - started:.2f}' seconds."),
            )
        except Exception as e:
            timeNow = datetime.now(UTC).isoformat()
            LOG.error(f"Task '{task.id}: {task.name}' has failed to execute at '{timeNow}'. '{e!s}'.")
            await self._notify.emit(
                Events.ERROR, data=error(f"Task '{task.name}' failed to execute at '{timeNow}'. '{e!s}'.")
            )
