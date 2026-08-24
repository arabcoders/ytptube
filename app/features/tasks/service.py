from __future__ import annotations

from typing import TYPE_CHECKING

from app.features.core.schemas import CEAction, CEFeature, ConfigEvent
from app.features.tasks.models import TaskModel
from app.features.tasks.utils import cron_time
from app.library.Events import Event, EventBus, Events
from app.library.logging import get_logger
from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from aiohttp import web

LOG = get_logger()


class Tasks(metaclass=Singleton):
    def __init__(self):
        from app.features.tasks.deps import get_tasks_repo

        self._repo = get_tasks_repo()
        self._loaded: bool = False
        self._handlers_service = None
        self._scheduler = Scheduler.get_instance()

    @staticmethod
    def get_instance() -> Tasks:
        return Tasks()

    def attach(self, _: web.Application) -> None:
        async def handle_started(_, __):
            await self._repo.run_migrations()
            await self._load_tasks()
            await self._init_handlers_service(self._scheduler)

        Services.get_instance().add("tasks_service", self).add("tasks_repository", self._repo)

        async def handle_config_update(e: Event, _):
            if isinstance(e.data, ConfigEvent) and CEFeature.TASKS == e.data.feature:
                await self._handle_task_change(e.data)

        EventBus.get_instance().subscribe(
            Events.CONFIG_UPDATE, handle_config_update, "Tasks.config_update_scheduler"
        ).subscribe(Events.STARTED, handle_started, "TasksRepository.run_migrations")

    async def on_shutdown(self, _: web.Application) -> None:
        pass

    async def _load_tasks(self) -> None:
        tasks = await self._repo.all()

        for task in tasks:
            if not task.timer or not task.enabled:
                continue

            try:
                self._scheduler.add(timer=task.timer, func=self._runner, args=(task,), id=f"task-cronjob-{task.id}")
                LOG.info(
                    "Queued task '%s' to run at '%s'.",
                    task.name,
                    cron_time(task.timer),
                    extra={"task_id": task.id, "task_name": task.name, "timer": task.timer},
                )
            except Exception as e:
                LOG.exception(
                    "Failed to queue task '%s'.",
                    task.name,
                    extra={
                        "task_id": task.id,
                        "task_name": task.name,
                        "timer": task.timer,
                        "exception_type": type(e).__name__,
                    },
                )

    async def _init_handlers_service(self, scheduler) -> None:
        if self._handlers_service is not None:
            return

        from app.features.tasks.definitions.service import TaskHandle
        from app.library.config import Config

        config = Config.get_instance()
        self._handlers_service = TaskHandle(scheduler, self._repo, config)
        self._handlers_service.load()
        LOG.debug("Task handlers service initialized.")
        Services.get_instance().add("task_handle_service", self._handlers_service)

    async def _handle_task_change(self, event_data) -> None:
        task_data: dict = event_data.data
        task_id: str = f"task-cronjob-{task_data['id']}"

        if CEAction.DELETE == event_data.action:
            if self._scheduler.has(task_id):
                self._scheduler.remove(task_id)

        elif event_data.action in (CEAction.CREATE, CEAction.UPDATE):
            if not (task := await self._repo.get(int(task_data["id"]))):
                return

            if self._scheduler.has(task_id):
                self._scheduler.remove(task_id)

            if task.timer and task.enabled:
                self._scheduler.add(timer=task.timer, func=self._runner, args=(task,), id=task_id)
                LOG.info(
                    "Queued task '%s' to run at '%s'.",
                    task.name,
                    cron_time(task.timer),
                    extra={"task_id": task.id, "task_name": task.name, "timer": task.timer},
                )

    async def _runner(self, task: TaskModel) -> None:
        import time
        from datetime import UTC, datetime

        from app.features.downloads.items import Item
        from app.features.downloads.runtime.queue_manager import DownloadQueue
        from app.library.config import Config

        timeNow: str = datetime.now(UTC).isoformat()
        task_id: int = task.id
        task_name: str = task.name
        notify: EventBus = EventBus.get_instance()
        try:
            current_task = await self._repo.get(task_id)
            if not current_task:
                LOG.info("Task '%s' no longer exists.", task_name, extra={"task_id": task_id, "task_name": task_name})
                return
            task = current_task

            if not task.enabled:
                LOG.debug(
                    "Task '%s' is disabled. Skipping execution.",
                    task.name,
                    extra={"task_id": task.id, "task_name": task.name},
                )
                return

            if not task.url:
                LOG.error(
                    "Failed to dispatch task '%s' because it has no URL.",
                    task.name,
                    extra={"task_id": task.id, "task_name": task.name},
                )
                notify.emit(
                    Events.TASK_ERROR,
                    data={"task_id": task.id, "task_name": task.name, "preset": task.preset},
                    title=f"Task '{task.name}' failed",
                    message=f"Task '{task.name}' failed because it has no URL.",
                )
                return

            started: float = time.time()

            config = Config.get_instance()
            preset: str = task.preset or config.default_preset
            folder: str = task.folder or ""
            template: str = task.template or ""
            cli: str = task.cli or ""

            status = await DownloadQueue.get_instance().add(
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
                            "source_id": str(task.id),
                            "source_handler": "Tasks",
                        },
                    }
                )
            )

            timeNow = datetime.now(UTC).isoformat()
            ended: float = time.time()
            status_data = {
                "task_id": task.id,
                "task_name": task.name,
                "preset": preset,
                **(status or {}),
            }
            if status and status.get("status") == "error":
                notify.emit(
                    Events.TASK_ERROR,
                    data=status_data,
                    title=f"Task '{task.name}' failed",
                    message=f"Task '{task.name}' failed while dispatching items.",
                )
                return

            LOG.info(
                "Task '%s' finished dispatching items in %.2f seconds.",
                task.name,
                ended - started,
                extra={
                    "task_id": task.id,
                    "task_name": task.name,
                    "url": task.url,
                    "preset": preset,
                    "elapsed_s": round(ended - started, 2),
                    "status": status.get("status") if isinstance(status, dict) else None,
                },
            )

            notify.emit(
                Events.TASK_FINISHED,
                data=status_data,
                title=f"Task '{task.name}' finished",
                message=f"Task '{task.name}' finished dispatching items at '{timeNow}'.",
            )
        except Exception as e:
            LOG.exception(
                "Failed to execute scheduled task '%s'.",
                task.name,
                extra={
                    "task_id": task.id,
                    "task_name": task.name,
                    "url": task.url,
                    "time": timeNow,
                    "exception_type": type(e).__name__,
                },
            )
            notify.emit(
                Events.TASK_ERROR,
                data={"task_id": task.id, "task_name": task.name, "preset": task.preset, "error": str(e)},
                title=f"Task '{task.name}' failed",
                message=f"Task '{task.name}' failed while dispatching items.",
            )

    @property
    def handlers(self):
        return self._handlers_service
