from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.features.core.schemas import CEAction, CEFeature, ConfigEvent
from app.features.tasks.models import TaskModel
from app.features.tasks.utils import cron_time
from app.library.Events import Event, EventBus, Events
from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from aiohttp import web

LOG: logging.Logger = logging.getLogger("tasks.service")


class Tasks(metaclass=Singleton):
    def __init__(self):
        from app.features.tasks.deps import get_tasks_repo

        self._repo = get_tasks_repo()
        self._loaded: bool = False
        self._handlers_service = None
        self._scheduler = Scheduler.get_instance()

    @staticmethod
    def get_instance() -> Tasks:
        """Get the singleton instance of Tasks."""
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
        tasks = await self._repo.list()

        for task in tasks:
            if not task.timer or not task.enabled:
                continue

            try:
                self._scheduler.add(timer=task.timer, func=self._runner, args=(task,), id=f"task-cronjob-{task.id}")
                LOG.info(f"Task '{task.id}: {task.name}' queued to be executed '{cron_time(task.timer)}'.")
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to queue task '{task.name}'. '{e!s}'.")

    async def _init_handlers_service(self, scheduler) -> None:
        """Initialize the handlers service after migrations."""
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
                LOG.info(f"Task '{task.id}: {task.name}' queued to be executed '{cron_time(task.timer)}'.")

    async def _runner(self, task: TaskModel) -> None:
        """
        Execute a scheduled task.

        Args:
            task: The TaskModel to execute.

        """
        import time
        from datetime import UTC, datetime

        from app.library.config import Config
        from app.library.downloads import DownloadQueue
        from app.library.ItemDTO import Item

        timeNow: str = datetime.now(UTC).isoformat()
        try:
            if not (task := await self._repo.get(task.id)):
                LOG.info(f"Task '{task.name}' no longer exists.")
                return

            if not task.enabled:
                LOG.debug(f"Task '{task.name}' is disabled. Skipping execution.")
                return

            if not task.url:
                LOG.error(f"Failed to dispatch '{task.name}'. No URL found.")
                return

            started: float = time.time()

            config = Config.get_instance()
            preset: str = task.preset or config.default_preset
            folder: str = task.folder or ""
            template: str = task.template or ""
            cli: str = task.cli or ""

            notify: EventBus = EventBus.get_instance()

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
            LOG.info(f"Task '{task.name}' completed at '{timeNow}' took '{ended - started:.2f}' seconds.")

            notify.emit(
                Events.TASK_DISPATCHED,
                data={**status, "preset": task.preset} if status else {"preset": task.preset},
                title=f"Task '{task.name}' dispatched",
                message=f"Task '{task.name}' dispatched at '{timeNow}'.",
            )
            notify.emit(
                Events.LOG_SUCCESS,
                data={"preset": task.preset, "lowPriority": True},
                title="Task completed",
                message=f"Task '{task.name}' completed in '{ended - started:.2f}'.",
            )
        except Exception as e:
            LOG.error(f"Failed to execute '{task.name}' at '{timeNow}'. '{e!s}'.")
            EventBus.get_instance().emit(
                Events.LOG_ERROR,
                data={"preset": task.preset},
                title="Task failed",
                message=f"Failed to execute '{task.name}'. '{e!s}'",
            )

    @property
    def handlers(self):
        """Get the handlers service instance."""
        return self._handlers_service
