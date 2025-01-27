import asyncio
import datetime
import json
import logging
import os
import time
from typing import Any, List

import httpx
from aiocron import Cron, crontab
from dataclasses import dataclass, field

from .config import Config
from .Emitter import Emitter
from .encoder import Encoder
from .EventsSubscriber import Event, Events, EventsSubscriber
from .Singleton import Singleton

LOG = logging.getLogger("notifications")


@dataclass(kw_only=True)
class Task:
    id: str
    name: str
    url: str
    folder: str = ""
    preset: str = ""
    timer: str = ""
    template: str = ""
    cookies: str = ""
    config: dict[str, str] = field(default_factory=dict)

    def serialize(self) -> dict:
        return self.__dict__

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.serialize().get(key, default)


@dataclass(kw_only=True)
class Job:
    id: str
    name: str
    task: Task
    job: Cron


class Tasks(metaclass=Singleton):
    """
    This class is used to manage the tasks.
    """

    _jobs: List[Job] = []
    """The jobs for the tasks."""

    _instance = None
    """The instance of the Tasks."""

    def __init__(
        self,
        file: str | None = None,
        emitter: Emitter | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        config: Config | None = None,
        encoder: Encoder | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        Tasks._instance = self

        config = config or Config.get_instance()

        self._debug = config.debug
        self._default_preset = config.default_preset
        self._file: str = file or os.path.join(config.config_path, "tasks.json")
        self._client: httpx.AsyncClient = client or httpx.AsyncClient()
        self._encoder: Encoder = encoder or Encoder()
        self._loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()
        self._emitter: Emitter = emitter or Emitter.get_instance()

        if os.path.exists(self._file):
            try:
                if "600" != oct(os.stat(self._file).st_mode)[-3:]:
                    os.chmod(self._file, 0o600)
            except Exception:
                pass

            if os.path.getsize(self._file) > 10:
                self.load()

        def handle_event(_, e: Event):
            self.save(**e.data)

        EventsSubscriber.get_instance().subscribe(Events.TASKS_ADD, f"{__class__}.save", handle_event)

    @staticmethod
    def get_instance() -> "Tasks":
        """
        Get the instance of the Tasks.

        Returns:
            Tasks: The instance of the Tasks
        """

        if not Tasks._instance:
            Tasks._instance = Tasks()
        return Tasks._instance

    def getTasks(self) -> List[Task]:
        """Return the tasks."""
        return [job.task for job in self._jobs]

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
            with open(self._file, "r") as f:
                tasks = json.load(f)
        except Exception as e:
            LOG.error(f"Failed to parse tasks from '{self._file}'. '{e}'.")
            return self

        if not tasks or len(tasks) < 1:
            LOG.info(f"No tasks were defined in '{self._file}'.")
            return self

        for i, task in enumerate(tasks):
            try:
                task = Task(**task)
            except Exception as e:
                LOG.error(f"Failed to parse task at list position '{i}'. '{str(e)}'.")
                continue

            try:
                self._jobs.append(
                    Job(
                        id=task.id,
                        name=task.name,
                        task=task,
                        job=crontab(spec=task.timer, func=self._runner, args=(task,), start=True, loop=self._loop),
                    )
                )
                LOG.info(f"Task '{i}: {task.name}' queued to be executed every '{task.timer}'.")
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to queue task '{i}: {task['name']}'. '{str(e)}'.")

        return self

    def clear(self) -> "Tasks":
        """
        Clear all tasks.

        Returns:
            Tasks: The current instance.
        """
        if len(self._jobs) < 1:
            return self

        for task in self._jobs:
            try:
                LOG.info(f"Stopping job '{task.id}: {task.name}'.")
                task.job.stop()
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to stop job '{task.id}: {task.name}'. '{str(e)}'.")

        self._jobs.clear()

        return self

    def validate(self, task: Task | dict) -> bool:
        """
        Validate the task.

        Args:
            tasks (Task|dict): The task to validate.

        Returns:
            bool: True if the task is valid, False otherwise.
        """

        if not isinstance(task, dict):
            if not isinstance(task, Task):
                raise ValueError("Invalid task type.")

            task = task.serialize()

        if not task.get("name"):
            raise ValueError("No name found.")

        if not task.get("timer"):
            raise ValueError("No timer found.")

        if not task.get("url"):
            raise ValueError("No URL found.")

        if not isinstance(task.get("cookies"), str):
            raise ValueError("Invalid cookies type.")

        if not isinstance(task.get("config"), dict):
            raise ValueError("Invalid config type.")

        if not isinstance(task.get("template"), str):
            raise ValueError("Invalid template type.")

        return True

    def save(self, tasks: List[Task | dict]) -> "Tasks":
        """
        Save the tasks.

        Args:
            tasks (List[Task]): The tasks to save.

        Returns:
            Tasks: The current instance.
        """

        for i, task in enumerate(tasks):
            try:
                if not isinstance(task, Task):
                    task = Task(**task)
                    tasks[i] = task
            except Exception as e:
                LOG.error(f"Failed to save task '{i}' unable to parse task. '{str(e)}'.")
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
            LOG.error(f"Failed to save tasks to '{self._file}'. '{str(e)}'.")

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
            timeNow = datetime.datetime().isoformat()
            started = time.time()
            if not task.url:
                LOG.error(f"Failed to dispatch task '{task.id}: {task.name}'. No URL found.")
                return

            preset: str = str(task.preset or self._default_preset)
            folder: str = task.folder if task.folder else ""
            ytdlp_cookies: str = str(task.cookies) if task.cookies else ""
            output_template: str = task.template if task.template else ""

            ytdlp_config = task.config if task.config else {}
            if isinstance(ytdlp_config, str) and ytdlp_config:
                try:
                    ytdlp_config = json.loads(ytdlp_config)
                except Exception as e:
                    LOG.error(f"Failed to parse json yt-dlp config for '{task.name}'. {str(e)}")
                    return

            await self.emitter.info(f"Task '{task.name}' dispatched at '{timeNow}'.")
            LOG.info(f"Task '{task.id}: {task.name}' dispatched at '{timeNow}'.")

            await self._emitter.emit(
                event=Events.ADD_URL,
                data=Event(
                    id=task.id,
                    data={
                        "url": task.url,
                        "preset": preset,
                        "folder": folder,
                        "ytdlp_cookies": ytdlp_cookies,
                        "ytdlp_config": ytdlp_config,
                        "output_template": output_template,
                    },
                ),
                local=True,
            )

            timeNow = datetime.datetime().isoformat()

            ended = time.time()
            LOG.info(f"Task '{task.id}: {task.name}' completed at '{timeNow}' took '{ended - started:.2f}' seconds.")

            await self.emitter.success(f"Task '{task.name}' completed in '{ended - started:.2f}' seconds.")
        except Exception as e:
            timeNow = datetime.datetime().isoformat()
            LOG.error(f"Task '{task.id}: {task.name}' has failed to execute at '{timeNow}'. '{str(e)}'.")
            await self.emitter.error(f"Task '{task.name}' failed to execute at '{timeNow}'. '{str(e)}'.")
