from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import pkgutil
import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskItem, TaskResult
from app.features.tasks.models import TaskModel
from app.features.ytdlp.utils import archive_read
from app.library.downloads.queue_manager import DownloadQueue
from app.library.Events import EventBus, Events
from app.library.ItemDTO import Item, ItemDTO
from app.library.Services import Services

if TYPE_CHECKING:
    from app.features.tasks.repository import TasksRepository
    from app.library.config import Config
    from app.library.Scheduler import Scheduler

LOG: logging.Logger = logging.getLogger("definitions.service")


class TaskHandle:
    def __init__(self, scheduler: Scheduler, tasks: TasksRepository, config: Config) -> None:
        self._handlers: list[type] = []
        "The available handlers."
        self._repo: TasksRepository = tasks
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
            func=lambda: asyncio.create_task(self._dispatcher(), name="task-handler-dispatcher"),
            id=f"{__class__.__name__}._dispatcher",
        )

    async def _dispatcher(self):
        s: dict[str, list[str]] = {"h": [], "d": [], "u": [], "f": []}

        handler_groups: dict[str, list[tuple[HandleTask, type]]] = {}

        tasks: list[TaskModel] = await self._repo.list()

        for task_model in tasks:
            task: HandleTask = HandleTask.model_validate(task_model)

            if not task.enabled or not task.handler_enabled:
                s["d"].append(task.name)
                continue

            if not task.get_ytdlp_opts().get_all().get("download_archive"):
                LOG.debug(f"Task '{task.name}' does not have an archive file configured.")
                s["f"].append(task.name)
                continue

            try:
                handler: type | None = await self._find_handler(task)
                if handler is None:
                    s["u"].append(task.name)
                    continue

                handler_name: str = handler.__name__
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
                    t: asyncio.Task[TaskResult | TaskFailure | None] = asyncio.create_task(
                        coro=self._dispatch(
                            task,
                            handler,
                            delay=0.0 if 0 == idx else random.uniform(1.0, self._config.task_handler_random_delay),
                        ),
                        name=f"taskHandler-{task.id}",
                    )
                    t.add_done_callback(lambda fut, t=task: self._handle_exception(fut, t))
                except Exception as e:
                    LOG.error(f"Failed to dispatch task '{task.name}'. '{e!s}'.")

        if len(tasks) > 0:
            LOG.info(
                f"Tasks handler summary: Handled: {len(s['h'])}, Unhandled: {len(s['u'])}, Disabled: {len(s['d'])}, Failed: {len(s['f'])}."
            )

    async def _dispatch(self, task: HandleTask, handler: type, delay: float) -> TaskResult | TaskFailure | None:
        """
        Dispatch a task after a random delay to avoid rate limiting.

        Args:
            task: The task to dispatch.
            handler: The handler to use.
            delay: The delay in seconds before dispatching.

        Returns:
            The dispatch result.

        """
        if delay > 0:
            LOG.debug(f"Delaying dispatch of task '{task.name}' by {delay:.1f} seconds.")
            await asyncio.sleep(delay)
        return await self.dispatch(task, handler=handler)

    def _handle_exception(self, fut: asyncio.Task, task: HandleTask) -> None:
        if fut.cancelled():
            return

        if exc := fut.exception():
            LOG.error(f"Exception while handling task '{task.name}': {exc}")

    async def _find_handler(self, task: HandleTask) -> type | None:
        for cls in self._handlers:
            try:
                if await Services.get_instance().handle_async(handler=cls.can_handle, task=task):
                    return cls
            except Exception as e:
                LOG.exception(e)
                continue

        return None

    async def dispatch(
        self,
        task: HandleTask,
        handler: type | None = None,
        **kwargs,  # noqa: ARG002
    ) -> TaskResult | TaskFailure | None:
        """
        Dispatch a task to the appropriate handler.

        Args:
            task: The task to dispatch.
            handler: Optional specific handler to use instead of finding one.
            **kwargs: Additional context to pass to the handler.

        Returns:
            The extraction outcome, or None if no handler matched.

        """
        if not handler:
            handler = await self._find_handler(task)
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
        """
        Inspect a URL to find a matching handler and optionally extract items.

        Args:
            url: The URL to inspect.
            preset: Optional preset name to use.
            handler_name: Optional specific handler name to use.
            static_only: If True, only check if a handler matches without extraction.

        Returns:
            TaskResult or TaskFailure with inspection results.

        """
        if not self._handlers:
            self._handlers = self._discover()

        task = HandleTask(
            id=None,
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
                matched = await services.handle_async(handler=handler_cls.can_handle, task=task)
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
            handler_cls = await self._find_handler(task)
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
                error=extraction.error or extraction.message,
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
        """Discover all available task handlers."""
        import app.features.tasks.definitions.handlers as handlers_pkg

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
        """Handle item error events to clean up queued items and track failures."""
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
