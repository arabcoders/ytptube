import asyncio
import inspect
import json
import logging
import pkgutil
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aiohttp import web

from .config import Config
from .DownloadQueue import DownloadQueue
from .encoder import Encoder
from .Events import EventBus, Events
from .ItemDTO import Item, ItemDTO
from .Scheduler import Scheduler
from .Services import Services
from .Singleton import Singleton
from .Utils import archive_add, archive_delete, archive_read, extract_info, init_class, validate_url
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
    enabled: bool = True

    def serialize(self) -> dict:
        return self.__dict__

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the task by key.

        Args:
            key (str): The key to get.
            default (Any): The default value if the key is not found.

        Returns:
            Any: The value of the key or the default value.

        """
        return self.serialize().get(key, default)

    def get_ytdlp_opts(self) -> YTDLPOpts:
        """
        Get the yt-dlp options for the task.

        Returns:
            YTDLPOpts: The yt-dlp options.

        """
        params: YTDLPOpts = YTDLPOpts.get_instance()

        if self.preset:
            params = params.preset(name=self.preset)

        if self.cli:
            params = params.add_cli(self.cli, from_user=True)

        if self.template:
            params = params.add({"outtmpl": {"default": self.template}}, from_user=False)

        return params

    def mark(self) -> tuple[bool, str]:
        """
        Mark the task's items as downloaded in the archive file.

        Returns:
            tuple[bool, str]: A tuple indicating success and a message.

        """
        ret = self._mark_logic()
        if isinstance(ret, tuple):
            return ret

        archive_file: Path = ret.get("file")
        items: set[str] = ret.get("items", set())

        if len(items) < 1 or not archive_add(archive_file, list(items)):
            return (True, "No new items to mark as downloaded.")

        return (True, f"Task '{self.name}' items marked as downloaded.")

    def unmark(self) -> tuple[bool, str]:
        """
        Unmark the task's items from the archive file.

        Returns:
            tuple[bool, str]: A tuple indicating success and a message.

        """
        ret: tuple[bool, str] | set[tuple[Path, set[str]]] = self._mark_logic()
        if isinstance(ret, tuple):
            return ret

        archive_file: Path = ret.get("file")
        items: set[str] = ret.get("items", set())

        if len(items) < 1 or not archive_delete(archive_file, list(items)):
            return (True, "No items to remove from archive file.")

        return (True, f"Removed '{self.name}' items from archive file.")

    def fetch_metadata(self, full: bool = False) -> tuple[dict[str, Any] | None, bool, str]:
        """
        Fetch metadata for the task's URL.

        Args:
            full (bool): Whether to fetch full metadata including all entries for playlists.

        Returns:
            tuple[dict[str, Any]|None, bool, str]: A tuple containing the metadata (or None on failure), a boolean
            indicating if the operation was successful, and a message.

        """
        if not self.url:
            return ({}, False, "No URL found in task parameters.")

        params = self.get_ytdlp_opts()
        if not full:
            params.add_cli("-I0", from_user=False)

        params = params.get_all()

        ie_info: dict | None = extract_info(
            params, self.url, no_archive=True, follow_redirect=False, sanitize_info=True
        )
        if not ie_info or not isinstance(ie_info, dict):
            return ({}, False, "Failed to extract information from URL.")

        return (ie_info, True, "")

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


def _split_inspect_metadata(metadata: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Split commonly consumed metadata keys from the rest.

    Args:
        metadata (dict[str, Any]|None): The metadata to split.

    Returns:
        tuple[dict[str, Any], dict[str, Any]]: The primary and extra metadata.

    """
    metadata = dict(metadata or {})
    primary: dict[str, Any] = {}

    for key in ("matched", "handler", "supported"):
        if key in metadata:
            primary[key] = metadata.pop(key)

    return primary, metadata


@dataclass(slots=True)
class TaskItem:
    url: str
    "The URL of the item."
    title: str | None = None
    "The title of the item."
    archive_id: str | None = None
    "The archive ID of the item."
    metadata: dict[str, Any] = field(default_factory=dict)
    "Additional metadata related to the item."


@dataclass(slots=True)
class TaskResult:
    items: list[TaskItem] = field(default_factory=list)
    "The list of items."
    metadata: dict[str, Any] = field(default_factory=dict)
    "Additional metadata related to the result."

    def serialize(self) -> dict[str, Any]:
        """
        Serialize the task result.

        Returns:
            dict[str, Any]: The serialized task result.

        """
        primary, extra = _split_inspect_metadata(self.metadata)
        payload: dict[str, Any] = {**primary, "items": [asdict(item) for item in self.items]}

        if extra:
            payload["metadata"] = extra

        return payload


@dataclass(slots=True)
class TaskFailure:
    message: str
    "A human-readable message describing the failure."
    error: str | None = None
    "An optional error code or string."
    metadata: dict[str, Any] = field(default_factory=dict)
    "Additional metadata related to the failure."

    def serialize(self) -> dict[str, Any]:
        """
        Serialize the task failure.

        Returns:
            dict[str, Any]: The serialized task failure.

        """
        primary, extra = _split_inspect_metadata(self.metadata)
        payload: dict[str, Any] = dict(primary)

        if self.error:
            payload["error"] = self.error

        if self.message and (not self.error or self.message != self.error):
            payload["message"] = self.message

        if extra:
            payload["metadata"] = extra

        return payload


class Tasks(metaclass=Singleton):
    """
    This class is used to manage the tasks.
    """

    def __init__(
        self,
        file: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        config: Config | None = None,
        encoder: Encoder | None = None,
        scheduler: Scheduler | None = None,
    ):
        self._tasks: list[Task] = []
        "The tasks."
        config = config or Config.get_instance()

        self._debug: bool = config.debug
        "Debug mode."
        self._default_preset: str = config.default_preset
        "The default preset."
        self._file: Path = Path(file) if file else Path(config.config_path).joinpath("tasks.json")
        "The tasks file."
        self._encoder: Encoder = encoder or Encoder()
        "The JSON encoder."
        self._loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()
        "The event loop."
        self._scheduler: Scheduler = scheduler or Scheduler.get_instance()
        "The scheduler."
        self._notify: EventBus = EventBus.get_instance()
        "The event bus."
        self._task_handler = HandleTask(self._scheduler, self, config)
        "The task handler."
        self._downloadQueue = DownloadQueue.get_instance()
        "The download queue."

        if self._file.exists() and "600" != self._file.stat().st_mode:
            try:
                self._file.chmod(0o600)
            except Exception:
                pass

    @staticmethod
    def get_instance(
        file: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        config: Config | None = None,
        encoder: Encoder | None = None,
        scheduler: Scheduler | None = None,
    ) -> "Tasks":
        """
        Get the instance of the class.

        Returns:
            Tasks: The instance of the class.

        """
        return Tasks(file=file, loop=loop, config=config, encoder=encoder, scheduler=scheduler)

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
        Services.get_instance().add("tasks", self)

        async def event_handler(data, _):
            if data and data.data:
                self.save(data.data)

        self._notify.subscribe(Events.TASKS_ADD, event_handler, f"{__class__.__name__}.add")
        self._task_handler.load()

    def get_all(self) -> list[Task]:
        """Return the tasks."""
        return self._tasks

    def get_handler(self) -> "HandleTask":
        """Expose the handle task helper."""
        return self._task_handler

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

        needs_update: bool = False
        for i, task in enumerate(tasks):
            try:
                Tasks.validate(task)
                if "enabled" not in task:
                    task["enabled"] = True
                    needs_update = True

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

        if needs_update:
            self.save(self._tasks)

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
                raise ValueError(msg)

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
            if not self.get(task.id):
                LOG.info(f"Task '{task.name}' no longer exists.")
                if self._scheduler.has(task.id):
                    self._scheduler.remove(task.id)
                return

            started: float = time.time()

            if not task.enabled:
                LOG.debug(f"Task '{task.name}' is disabled. Skipping execution.")
                return

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
                        "extras": {
                            "source_name": task.name,
                            "source_id": task.id,
                            "source_handler": __class__.__name__,
                        },
                    }
                )
            )

            timeNow = datetime.now(UTC).isoformat()
            ended: float = time.time()
            LOG.info(f"Task '{task.name}' completed at '{timeNow}' took '{ended - started:.2f}' seconds.")
            self._notify.emit(
                Events.TASK_DISPATCHED,
                data={**status, "preset": task.preset} if status else {"preset": task.preset},
                title=f"Task '{task.name}' dispatched",
                message=f"Task '{task.name}' dispatched at '{timeNow}'.",
            )
            self._notify.emit(
                Events.LOG_SUCCESS,
                data={"preset": task.preset, "lowPriority": True},
                title="Task completed",
                message=f"Task '{task.name}' completed in '{ended - started:.2f}'.",
            )
        except Exception as e:
            LOG.error(f"Failed to execute '{task.name}' at '{timeNow}'. '{e!s}'.")
            self._notify.emit(
                Events.LOG_ERROR,
                data={"preset": task.preset},
                title="Task failed",
                message=f"Failed to execute '{task.name}'. '{e!s}'",
            )


class HandleTask:
    def __init__(self, scheduler: Scheduler, tasks: Tasks, config: Config) -> None:
        self._handlers: list[type] = []
        "The available handlers."
        self._tasks: Tasks = tasks
        "The tasks manager."
        self._scheduler: Scheduler = scheduler
        "The scheduler."
        self._config: Config = config
        "The configuration."
        self._task_name: str = f"{__class__.__name__}._dispatcher"
        "The task name for the scheduler."
        self._queued: dict[str, set[str]] = {}
        "Queued archive IDs per handler."
        self._failure_count: dict[str, dict[str, int]] = {}
        "Failure counts per handler and archive ID."

        EventBus.get_instance().subscribe(
            Events.ITEM_ERROR,
            self._handle_item_error,
            f"{__class__.__name__}.item_error",
        )

    def load(self) -> None:
        """
        Load the available handlers and schedule the dispatcher.
        """
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
        s: dict[list[str]] = {"h": [], "d": [], "u": [], "f": []}

        handler_groups: dict[str, list[tuple[Task, type]]] = {}

        for task in self._tasks.get_all():
            if not task.enabled or not task.handler_enabled:
                s["d"].append(task.name)
                continue

            if not task.get_ytdlp_opts().get_all().get("download_archive"):
                LOG.debug(f"Task '{task.name}' does not have an archive file configured.")
                s["f"].append(task.name)
                continue

            try:
                handler = self._find_handler(task)
                if handler is None:
                    s["u"].append(task.name)
                    continue

                handler_name = handler.__name__
                if handler_name not in handler_groups:
                    handler_groups[handler_name] = []
                handler_groups[handler_name].append((task, handler))
                s["h"].append(task.name)
            except Exception as e:
                LOG.error(f"Failed to handle task '{task.name}'. '{e!s}'.")
                s["f"].append(task.name)

        for tasks_with_handlers in handler_groups.values():
            for idx, (task, handler) in enumerate(tasks_with_handlers):
                try:
                    t = asyncio.create_task(
                        coro=self._dispatch(
                            task,
                            handler,
                            delay=0.0 if 0 == idx else random.uniform(1.0, self._config.task_handler_random_delay),
                        ),
                        name=f"task-{task.id}",
                    )
                    t.add_done_callback(lambda fut, t=task: self._handle_exception(fut, t))
                except Exception as e:
                    LOG.error(f"Failed to dispatch task '{task.name}'. '{e!s}'.")

        if len(self._tasks.get_all()) > 0:
            LOG.info(
                f"Tasks handler summary: Handled: {len(s['h'])}, Unhandled: {len(s['u'])}, Disabled: {len(s['d'])}, Failed: {len(s['f'])}."
            )

    async def _dispatch(self, task: Task, handler: type, delay: float) -> TaskResult | TaskFailure | None:
        """
        Dispatch a task after a random delay to avoid rate limiting.

        Args:
            task (Task): The task to dispatch.
            handler (type): The handler to use.
            delay (float): The delay in seconds before dispatching.

        Returns:
            TaskResult|TaskFailure|None: The dispatch result.

        """
        if delay > 0:
            LOG.debug(f"Delaying dispatch of task '{task.name}' by {delay:.1f} seconds.")
            await asyncio.sleep(delay)
        return await self.dispatch(task, handler=handler)

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

    async def dispatch(self, task: Task, handler: type | None = None, **kwargs) -> TaskResult | TaskFailure | None:  # noqa: ARG002
        """
        Dispatch a task to the appropriate handler.

        Args:
            task (Task): The task to dispatch.
            handler (type|None): Optional specific handler to use instead of finding one.
            **kwargs: Additional context to pass to the handler.

        Returns:
            TaskResult|TaskFailure|None: The extraction outcome, or None if no handler matched.

        """
        if not handler:
            handler = self._find_handler(task)
            if handler is None:
                return None

        services: Services = Services.get_instance()

        try:
            extraction: TaskResult | TaskFailure = await services.handle_async(
                handler=handler.extract, task=task, config=self._config
            )
        except NotImplementedError:
            LOG.error(f"Handler '{handler.__name__}' does not implement extract().")
            return TaskFailure(message="Handler does not support extraction.")
        except Exception as exc:
            LOG.exception(exc)
            raise

        if isinstance(extraction, TaskFailure):
            LOG.error(f"Handler '{handler.__name__}' failed to extract items: {extraction.message}")
            return extraction

        if not isinstance(extraction, TaskResult):
            LOG.error(
                f"Handler '{handler.__name__}' returned unexpected result type '{type(extraction).__name__}'.",
            )
            return TaskFailure(
                message="Handler returned invalid result type.", metadata={"type": type(extraction).__name__}
            )

        raw_items: list[TaskItem] = extraction.items or []
        metadata: dict[str, Any] = extraction.metadata or {}

        handler_name: str = handler.__name__
        queued: set[str] = self._queued.setdefault(handler_name, set())
        failures: dict[str, int] = self._failure_count.setdefault(handler_name, {})

        params: dict = task.get_ytdlp_opts().get_all()
        archive_file: str | None = params.get("download_archive")

        download_queue: DownloadQueue = services.get("queue") or DownloadQueue.get_instance()
        notify: EventBus = services.get("notify") or EventBus.get_instance()

        archive_ids: list[str] = [
            item.archive_id for item in raw_items if isinstance(item, TaskItem) and item.archive_id
        ]
        downloaded: list[str] = archive_read(archive_file, archive_ids) if archive_file else []

        filtered: list[TaskItem] = []

        for item in raw_items:
            if not isinstance(item, TaskItem):
                LOG.warning("Handler '{handler.__name__}' produced non-TaskItem entry: {item!r}")
                continue

            url: str = item.url
            if not url:
                continue

            archive_id: str | None = item.archive_id
            if not archive_id:
                LOG.warning(f"'{task.name}': Item with URL '{url}' is missing an archive ID. Skipping.")
                continue

            if archive_id in queued:
                continue

            queued.add(archive_id)

            if archive_file and archive_id in downloaded:
                continue

            if await download_queue.queue.exists(url=url):
                continue

            try:
                done = await download_queue.done.get(url=url)
                if "error" != done.info.status:
                    continue
            except KeyError:
                pass

            if archive_id not in failures:
                failures[archive_id] = 0

            filtered.append(item)

        if not filtered:
            if raw_items:
                LOG.debug(
                    f"Handler '{handler.__name__}' produced '{len(raw_items)}' for '{task.name}' items, none queued after filtering."
                )
            return TaskResult(items=[], metadata=metadata)

        LOG.info(
            f"Handler '{handler.__name__}' Found '{len(filtered)}' new items for '{task.name}' (raw={len(raw_items)})."
        )

        base_item = Item.format(
            {
                "url": task.url,
                "preset": task.preset or self._config.default_preset,
                "folder": task.folder or "",
                "template": task.template or "",
                "cli": task.cli or "",
                "auto_start": task.auto_start,
                "extras": {"source_name": task.name, "source_id": task.id, "source_handler": handler.__name__},
            }
        )

        for item in filtered:
            metadata_entry: dict[str, Any] = item.metadata if isinstance(item.metadata, dict) else {}
            extras: dict[str, Any] = base_item.extras.copy()
            if metadata_entry:
                extras["metadata"] = metadata_entry

            notify.emit(
                Events.ADD_URL,
                data=base_item.new_with(url=item.url, extras=extras).serialize(),
            )

        return TaskResult(items=filtered, metadata=metadata)

    async def inspect(
        self,
        url: str,
        preset: str | None = None,
        handler_name: str | None = None,
        static_only: bool = False,
    ) -> TaskResult | TaskFailure:
        if not self._handlers:
            self._handlers = self._discover()

        task = Task(
            id=str(uuid.uuid4()),
            name="Inspector",
            url=url,
            preset=preset or self._config.default_preset,
            auto_start=False,
        )

        services = Services.get_instance()

        handler_cls: type | None
        if handler_name:
            handler_cls = next((cls for cls in self._handlers if cls.__name__.lower() == handler_name.lower()), None)
            if handler_cls is None:
                message: str = f"Handler '{handler_name}' not found."
                return TaskFailure(
                    message=message,
                    error=message,
                    metadata={"matched": False, "handler": handler_name},
                )

            try:
                matched = services.handle_sync(handler=handler_cls.can_handle, task=task)
            except Exception as exc:  # pragma: no cover - defensive
                LOG.exception(exc)
                message = str(exc)
                return TaskFailure(
                    message=message,
                    error=message,
                    metadata={"matched": False, "handler": handler_cls.__name__},
                )

            if not matched:
                return TaskFailure(
                    message="Handler cannot process the supplied URL.",
                    metadata={"matched": False, "handler": handler_cls.__name__},
                )
        else:
            handler_cls = self._find_handler(task)
            if handler_cls is None:
                message = "No handler matched the supplied URL."
                return TaskFailure(
                    message=message,
                    error=message,
                    metadata={"matched": False, "handler": None},
                )

        base_metadata: dict[str, Any] = {"matched": True, "handler": handler_cls.__name__}

        if static_only:
            return TaskResult(items=[], metadata=base_metadata)

        try:
            extraction: TaskResult | TaskFailure = await services.handle_async(
                handler=handler_cls.extract, task=task, config=self._config
            )
        except NotImplementedError:
            return TaskFailure(
                message="Handler does not support manual inspection.",
                metadata={**base_metadata, "supported": False},
            )
        except Exception as exc:
            LOG.exception(exc)
            message = str(exc)
            return TaskFailure(
                message=message,
                error=message,
                metadata={**base_metadata, "supported": True},
            )

        if isinstance(extraction, TaskFailure):
            combined_failure_metadata: dict[str, Any] = {**base_metadata, "supported": True}
            if extraction.metadata:
                combined_failure_metadata.update(extraction.metadata)

            return TaskFailure(
                message=extraction.message,
                error=extraction.error if extraction.error else extraction.message,
                metadata=combined_failure_metadata,
            )

        if not isinstance(extraction, TaskResult):
            LOG.error(
                f"Handler '{handler_cls.__name__}' returned unexpected result type '{type(extraction).__name__}' during inspection.",
            )
            extraction = TaskResult()

        combined_metadata: dict[str, Any] = {**base_metadata, "supported": True}
        if extraction.metadata:
            combined_metadata.update(extraction.metadata)

        return TaskResult(items=list(extraction.items), metadata=combined_metadata)

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

                if callable(getattr(cls, "can_handle", None)) and callable(getattr(cls, "extract", None)):
                    handlers.append(cls)

        return handlers

    async def _handle_item_error(self, event, _name, **_kwargs):
        item: ItemDTO | None = getattr(event, "data", None)
        if not isinstance(item, ItemDTO):
            return

        extras: dict[Any, Any] = getattr(item, "extras", {}) or {}
        handler_name: Any | None = extras.get("source_handler")
        if not handler_name:
            return

        archive_id: str | None = item.archive_id
        if not archive_id:
            return

        queued: set[str] | None = self._queued.get(handler_name)
        if queued:
            queued.discard(archive_id)

        failures: dict[str, int] = self._failure_count.setdefault(handler_name, {})
        failures[archive_id] = failures.get(archive_id, 0) + 1
