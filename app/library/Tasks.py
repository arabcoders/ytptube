import asyncio
import inspect
import json
import logging
import pkgutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aiohttp import web

from .config import Config
from .DownloadQueue import DownloadQueue
from .encoder import Encoder
from .Events import EventBus, Events
from .ItemDTO import Item
from .Scheduler import Scheduler
from .Services import Services
from .Singleton import Singleton
from .Utils import archive_add, archive_delete, extract_info, init_class, validate_url
from .YTDLPOpts import YTDLPOpts

LOG: logging.Logger = logging.getLogger("tasks")


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
    auto_start: bool = True
    handler_enabled: bool = True

    def serialize(self) -> dict:
        return self.__dict__

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.serialize().get(key, default)

    def get_ytdlp_opts(self) -> YTDLPOpts:
        params: YTDLPOpts = YTDLPOpts.get_instance()

        if self.preset:
            params = params.preset(name=self.preset)

        if self.cli:
            params = params.add_cli(self.cli, from_user=True)

        return params

    def mark(self) -> tuple[bool, str]:
        ret = self._mark_logic()
        if isinstance(ret, tuple):
            return ret

        archive_file: Path = ret.get("file")
        items: set[str] = ret.get("items", set())

        if len(items) < 1 or not archive_add(archive_file, list(items)):
            return (True, "No new items to mark as downloaded.")

        return (True, f"Task '{self.name}' items marked as downloaded.")

    def unmark(self) -> tuple[bool, str]:
        ret: tuple[bool, str] | set[tuple[Path, set[str]]] = self._mark_logic()
        if isinstance(ret, tuple):
            return ret

        archive_file: Path = ret.get("file")
        items: set[str] = ret.get("items", set())

        if len(items) < 1 or not archive_delete(archive_file, list(items)):
            return (True, "No items to remove from archive file.")

        return (True, f"Removed '{self.name}' items from archive file.")

    def _mark_logic(self) -> tuple[bool, str] | set[tuple[Path, set[str]]]:
        if not self.url:
            return (False, "No URL found in task parameters.")

        params: dict = self.get_ytdlp_opts().get_all()
        if not (archive_file := params.get("download_archive")):
            return (False, "No archive file found.")

        archive_file: Path = Path(archive_file)

        ie_info: dict | None = extract_info(params, self.url, no_archive=True, follow_redirect=True)
        if not ie_info or not isinstance(ie_info, dict):
            return (False, "Failed to extract information from URL.")

        if "playlist" != ie_info.get("_type"):
            return (False, "Expected a playlist type from extract_info.")

        items: set[str] = set()

        def _process(item: dict):
            for entry in item.get("entries", []):
                if not isinstance(entry, dict):
                    continue

                if "playlist" == entry.get("_type"):
                    _process(entry)
                    continue

                if entry.get("_type") not in ("video", "url"):
                    continue

                if not entry.get("id") or not entry.get("ie_key"):
                    continue

                archive_id: str = f"{entry.get('ie_key', '').lower()} {entry.get('id')}"

                items.add(archive_id)

        _process(ie_info)

        return {"file": archive_file, "items": items}


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
        scheduler: Scheduler | None = None,
    ):
        Tasks._instance = self

        config = config or Config.get_instance()

        self._debug: bool = config.debug
        self._default_preset: str = config.default_preset
        self._file: Path = Path(file) if file else Path(config.config_path).joinpath("tasks.json")
        self._encoder: Encoder = encoder or Encoder()
        self._loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()
        self._scheduler: Scheduler = scheduler or Scheduler.get_instance()
        self._notify: EventBus = EventBus.get_instance()
        self._task_handler = HandleTask(self._scheduler, self, config)
        self._downloadQueue = DownloadQueue.get_instance()

        if self._file.exists() and "600" != self._file.stat().st_mode:
            try:
                self._file.chmod(0o600)
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
        self.clear(shutdown=True)
        self._task_handler.on_shutdown(_)

    def attach(self, _: web.Application):
        """
        Attach the tasks to the aiohttp application.

        Args:
            _ (web.Application): The aiohttp application.

        """
        self.load()

        async def event_handler(data, _):
            if data and data.data:
                self.save(data.data)

        self._notify.subscribe(Events.TASKS_ADD, event_handler, f"{__class__.__name__}.add")
        self._task_handler.load()

    def get_all(self) -> list[Task]:
        """Return the tasks."""
        return self._tasks

    def get(self, task_id: str) -> Task | None:
        """
        Get a task by its ID.

        Args:
            task_id (str): The ID of the task.

        Returns:
            Task | None: The task if found, otherwise None.

        """
        return next((task for task in self._tasks if task.id == task_id), None)

    def load(self) -> "Tasks":
        """
        Load the tasks.

        Returns:
            Tasks: The current instance.

        """
        has_tasks: bool = len(self._tasks) > 0
        self.clear()

        if not self._file.exists() or self._file.stat().st_size < 1:
            return self

        try:
            LOG.info(f"{'Reloading' if has_tasks else 'Loading'} '{self._file}'.")
            tasks = json.loads(self._file.read_text())
        except Exception as e:
            LOG.error(f"Error loading '{self._file}'. '{e!s}'.")
            return self

        if not tasks or len(tasks) < 1:
            return self

        for i, task in enumerate(tasks):
            try:
                Tasks.validate(task)
                task: Task = init_class(Task, task)
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
                    schedule_time: str = cs.explain()
                except Exception:
                    schedule_time = task.timer

                if not has_tasks:
                    LOG.info(f"Task '{task.name}' queued to be executed '{schedule_time}'.")
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to queue '{i}: {task.name}'. '{e!s}'.")

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
            if not self._scheduler.has(task.id):
                continue

            try:
                LOG.debug(f"Stopping '{task.name}'.")
                self._scheduler.remove(task.id)
            except Exception as e:
                if not shutdown:
                    LOG.exception(e)
                    LOG.error(f"Failed to stop '{task.name}'. '{e!s}'.")

        self._tasks.clear()

        return self

    @staticmethod
    def validate(task: Task | dict) -> bool:
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

        task["name"] = task["name"].strip()

        if not task.get("url"):
            msg = "No URL found."
            raise ValueError(msg)

        task["url"] = task["url"].strip()
        try:
            validate_url(task["url"], allow_internal=True)
        except ValueError as e:
            msg = f"Invalid URL format. '{e!s}'."
            raise ValueError(msg) from e

        if task.get("timer"):
            try:
                from cronsim import CronSim

                CronSim(task.get("timer"), datetime.now(UTC))
                task["timer"] = str(task["timer"]).strip()
            except Exception as e:
                msg = f"Invalid timer format. '{e!s}'."
                raise ValueError(msg) from e

        if task.get("cli"):
            try:
                from .Utils import arg_converter

                arg_converter(args=task.get("cli"))
                task["cli"] = str(task["cli"]).strip()
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
                self.validate(task)

                if not isinstance(task, Task):
                    task: Task = init_class(Task, task)
                    tasks[i] = task
            except ValueError as e:
                LOG.error(f"Failed to validate item '{i}: {task.name}'. '{e}'.")
                continue
            except Exception as e:
                LOG.error(f"Failed to save task '{i}'. '{e!s}'.")
                continue

        try:
            self._file.write_text(json.dumps([i.serialize() for i in tasks], indent=4))
            LOG.info(f"Updated '{self._file}'.")
        except Exception as e:
            LOG.error(f"Error saving '{self._file}'. '{e!s}'.")

        return self

    async def _runner(self, task: Task) -> None:
        """
        Run the task.

        Args:
            task (Task): The task to run.

        Returns:
            None

        """
        timeNow: str = datetime.now(UTC).isoformat()
        try:
            started: float = time.time()
            if not task.url:
                LOG.error(f"Failed to dispatch '{task.name}'. No URL found.")
                return

            preset: str = str(task.preset or self._default_preset)
            folder: str = task.folder if task.folder else ""
            template: str = task.template if task.template else ""
            cli: str = task.cli if task.cli else ""

            status = await self._downloadQueue.add(
                item=Item.format(
                    {
                        "url": task.url,
                        "preset": preset,
                        "folder": folder,
                        "template": template,
                        "cli": cli,
                        "auto_start": task.auto_start,
                    }
                )
            )

            timeNow = datetime.now(UTC).isoformat()
            ended: float = time.time()
            LOG.info(f"Task '{task.name}' completed at '{timeNow}' took '{ended - started:.2f}' seconds.")

            _tasks = [
                self._notify.emit(
                    Events.TASK_DISPATCHED,
                    data={**status, "preset": task.preset} if status else {"preset": task.preset},
                    title=f"Task '{task.name}' dispatched",
                    message=f"Task '{task.name}' dispatched at '{timeNow}'.",
                ),
                self._notify.emit(
                    Events.LOG_SUCCESS,
                    data={"preset": task.preset, "lowPriority": True},
                    title="Task completed",
                    message=f"Task '{task.name}' completed in '{ended - started:.2f}'.",
                ),
            ]

            await asyncio.gather(*_tasks)
        except Exception as e:
            LOG.error(f"Failed to execute '{task.name}' at '{timeNow}'. '{e!s}'.")
            self._notify.emit(
                Events.LOG_ERROR,
                data={"preset": task.preset},
                title="Task failed",
                message=f"Failed to execute '{task.name}'. '{e!s}'",
            )


class HandleTask:
    _tasks: Tasks
    _handlers: list[type]
    _scheduler: Scheduler
    _config: Config
    _task_name: str

    def __init__(self, scheduler: Scheduler, tasks: Tasks, config: Config) -> None:
        self._tasks = tasks
        self._scheduler = scheduler
        self._config = config
        self._task_name: str = f"{__class__.__name__}._dispatcher"

    def load(self) -> None:
        self._handlers: list[type] = self._discover()

        timer: str = self._config.tasks_handler_timer
        try:
            from cronsim import CronSim

            CronSim(timer, datetime.now(UTC))
        except Exception as e:
            timer = "15 */1 * * *"
            LOG.error(f"Invalid timer format. '{e!s}'. Defaulting to '{timer}'.")

        self._scheduler.add(
            timer=timer,
            func=self._dispatcher,
            id=f"{__class__.__name__}._dispatcher",
        )

    def on_shutdown(self, _: web.Application) -> None:
        """
        Handle shutdown event.

        Args:
            _: web.Application: The aiohttp application.

        """
        if self._scheduler.has(self._task_name):
            self._scheduler.remove(self._task_name)

    def _dispatcher(self):
        for task in self._tasks.get_all():
            if not task.handler_enabled:
                continue

            if not task.get_ytdlp_opts().get_all().get("download_archive"):
                LOG.debug(f"Task '{task.name}' does not have an archive file configured.")
                continue

            try:
                handler = self._find_handler(task)
                if handler is None:
                    continue

                coro = self.dispatch(task, handler=handler)
                t = asyncio.create_task(coro, name=f"task-{task.id}")
                t.add_done_callback(lambda fut, t=task: self._handle_exception(fut, t))
            except Exception as e:
                LOG.error(f"Failed to handle task '{task.name}'. '{e!s}'.")

    def _handle_exception(self, fut: asyncio.Task, task: Task) -> None:
        if fut.cancelled():
            return

        if exc := fut.exception():
            LOG.error(f"Exception while handling task '{task.name}': {exc}")

    def _find_handler(self, task: Task) -> type | None:
        for cls in self._handlers:
            try:
                if Services.get_instance().handle_sync(handler=cls.can_handle, task=task):
                    return cls
            except Exception as e:
                LOG.exception(e)
                continue

        return None

    async def dispatch(self, task: Task, handler: type | None = None, **kwargs) -> Any | None:
        """
        Dispatch a task to the appropriate handler.

        Args:
            task (Task): The task to dispatch.
            handler (type|None): Optional specific handler to use instead of finding one.
            **kwargs: Additional context to pass to the handler.

        Returns:
            Any|None: The result of the handler's execution, or None if no handler found.

        """
        if not handler:
            handler = self._find_handler(task)
            if handler is None:
                return None

        try:
            return await Services.get_instance().handle_async(handler=handler.handle, task=task, **kwargs)
        except Exception as e:
            LOG.exception(e)
            raise

    def _discover(self) -> list[type]:
        import importlib

        import app.library.task_handlers as handlers_pkg

        handlers: list[type] = []

        for _, module_name, _ in pkgutil.iter_modules(handlers_pkg.__path__):
            if module_name.startswith("_"):
                continue

            module = importlib.import_module(f"{handlers_pkg.__name__}.{module_name}")
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ != module.__name__:
                    continue

                if callable(getattr(cls, "can_handle", None)) and callable(getattr(cls, "handle", None)):
                    handlers.append(cls)

        return handlers
