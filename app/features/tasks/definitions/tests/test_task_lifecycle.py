from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.downloads.runtime.queue_manager import DownloadQueue
from app.features.tasks.definitions.results import HandleTask, TaskFailure, TaskResult
from app.features.tasks.definitions.service import TaskHandle
from app.features.tasks.models import TaskModel
from app.features.tasks.service import Tasks
from app.library.Events import EventBus, Events


def _task() -> HandleTask:
    return HandleTask(id=7, name="Example", url="https://example.com", preset="default")


@pytest.mark.asyncio
async def test_dispatch_success(monkeypatch: pytest.MonkeyPatch) -> None:
    service = TaskHandle.__new__(TaskHandle)
    service.dispatch = AsyncMock(return_value=TaskResult(items=[]))
    events = MagicMock()
    monkeypatch.setattr(EventBus, "get_instance", staticmethod(lambda: events))

    await service._dispatch(_task(), MagicMock(), 0)

    task_events = [call.args[0] for call in events.emit.call_args_list if call.args[0].startswith("task_")]
    assert task_events == [Events.TASK_FINISHED]


@pytest.mark.asyncio
async def test_dispatch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    service = TaskHandle.__new__(TaskHandle)
    service.dispatch = AsyncMock(return_value=TaskFailure(message="Extraction failed"))
    events = MagicMock()
    monkeypatch.setattr(EventBus, "get_instance", staticmethod(lambda: events))

    await service._dispatch(_task(), MagicMock(), 0)

    assert [call.args[0] for call in events.emit.call_args_list] == [Events.TASK_ERROR]


@pytest.mark.asyncio
async def test_queue_error(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = DownloadQueue.__new__(DownloadQueue)
    events = MagicMock()
    queue._notify = events
    item = MagicMock(extras={"source_handler": "web", "source_id": 7, "source_name": "Example"}, preset="default")
    monkeypatch.setattr(
        "app.features.downloads.runtime.queue_manager.add_impl",
        AsyncMock(return_value={"status": "error", "msg": "Invalid URL"}),
    )

    result = await queue.add(item)

    assert result["status"] == "error"
    task_events = [call.args[0] for call in events.emit.call_args_list if call.args[0].startswith("task_")]
    assert task_events == [Events.TASK_ERROR]


@pytest.mark.asyncio
async def test_queue_success(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = DownloadQueue.__new__(DownloadQueue)
    events = MagicMock()
    queue._notify = events
    item = MagicMock(extras={"source_handler": "wEb", "source_id": 7, "source_name": "Example"}, preset="default")
    monkeypatch.setattr(
        "app.features.downloads.runtime.queue_manager.add_impl",
        AsyncMock(return_value={"status": "ok"}),
    )

    await queue.add(item)

    task_events = [call.args[0] for call in events.emit.call_args_list if call.args[0].startswith("task_")]
    assert task_events == [Events.TASK_FINISHED]


@pytest.mark.asyncio
async def test_queue_recursive(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = DownloadQueue.__new__(DownloadQueue)
    events = MagicMock()
    queue._notify = events
    item = MagicMock(extras={"source_handler": "Web", "source_id": 7, "source_name": "Example"}, preset="default")
    monkeypatch.setattr(
        "app.features.downloads.runtime.queue_manager.add_impl",
        AsyncMock(return_value={"status": "ok"}),
    )

    await queue.add(item, already=set())

    assert not [call for call in events.emit.call_args_list if call.args[0].startswith("task_")]


def _scheduled_task() -> TaskModel:
    return TaskModel(
        id=7,
        name="Example",
        url="https://example.com",
        preset="default",
        folder="",
        template="",
        cli="",
        auto_start=True,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_runner_error(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Tasks.__new__(Tasks)
    monkeypatch.setattr(service, "_repo", MagicMock(get=AsyncMock(return_value=_scheduled_task())), raising=False)
    events = MagicMock()
    queue = SimpleNamespace(add=AsyncMock(return_value={"status": "error", "msg": "Invalid URL"}))
    config = SimpleNamespace(default_preset="default")
    monkeypatch.setattr(EventBus, "get_instance", staticmethod(lambda: events))
    monkeypatch.setattr("app.library.config.Config.get_instance", staticmethod(lambda: config))
    monkeypatch.setattr(DownloadQueue, "get_instance", staticmethod(lambda: queue))

    await service._runner(_scheduled_task())

    emitted = [call.args[0] for call in events.emit.call_args_list]
    assert emitted == [Events.TASK_ERROR]


@pytest.mark.asyncio
async def test_runner_success(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Tasks.__new__(Tasks)
    monkeypatch.setattr(service, "_repo", MagicMock(get=AsyncMock(return_value=_scheduled_task())), raising=False)
    events = MagicMock()
    queue = SimpleNamespace(add=AsyncMock(return_value={"status": "ok"}))
    config = SimpleNamespace(default_preset="default")
    monkeypatch.setattr(EventBus, "get_instance", staticmethod(lambda: events))
    monkeypatch.setattr("app.library.config.Config.get_instance", staticmethod(lambda: config))
    monkeypatch.setattr(DownloadQueue, "get_instance", staticmethod(lambda: queue))

    await service._runner(_scheduled_task())

    emitted = [call.args[0] for call in events.emit.call_args_list]
    assert emitted == [Events.TASK_FINISHED]
