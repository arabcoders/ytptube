import asyncio
import datetime
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.features.core.utils import gen_random
from app.library.logging import get_logger

from .BackgroundWorker import BackgroundWorker
from .Singleton import Singleton

LOG = get_logger()


class Events:
    STARTUP: str = "startup"
    LOADED: str = "loaded"
    STARTED: str = "started"
    SHUTDOWN: str = "shutdown"

    CONNECTED: str = "connected"

    CONFIG_UPDATE: str = "config_update"

    LOG_INFO: str = "log_info"
    LOG_WARNING: str = "log_warning"
    LOG_ERROR: str = "log_error"
    LOG_SUCCESS: str = "log_success"

    ITEM_ADDED: str = "item_added"
    ITEM_UPDATED: str = "item_updated"
    ITEM_PROGRESS: str = "item_progress"
    ITEM_COMPLETED: str = "item_completed"
    ITEM_CANCELLED: str = "item_cancelled"
    ITEM_DELETED: str = "item_deleted"
    ITEM_BULK_DELETED: str = "item_bulk_deleted"
    ITEM_PAUSED: str = "item_paused"
    ITEM_RESUMED: str = "item_resumed"
    ITEM_MOVED: str = "item_moved"
    QUEUE_REORDERED: str = "queue_reordered"
    ITEM_STATUS: str = "item_status"
    ITEM_ERROR: str = "item_error"

    TEST: str = "test"
    ADD_URL: str = "add_url"

    PAUSED: str = "paused"
    RESUMED: str = "resumed"

    TASKS_ADD: str = "task_add"
    TASK_FINISHED: str = "task_finished"
    TASK_ERROR: str = "task_error"

    SCHEDULE_ADD: str = "schedule_add"

    def get_all() -> list:
        return [
            getattr(Events, ev) for ev in dir(Events) if not ev.startswith("_") and not callable(getattr(Events, ev))
        ]

    def frontend() -> list:
        return [
            Events.CONFIG_UPDATE,
            Events.CONNECTED,
            Events.LOG_INFO,
            Events.LOG_WARNING,
            Events.LOG_ERROR,
            Events.LOG_SUCCESS,
            Events.ITEM_ADDED,
            Events.ITEM_UPDATED,
            Events.ITEM_PROGRESS,
            Events.ITEM_CANCELLED,
            Events.ITEM_DELETED,
            Events.ITEM_BULK_DELETED,
            Events.ITEM_MOVED,
            Events.QUEUE_REORDERED,
            Events.ITEM_STATUS,
            Events.PAUSED,
            Events.RESUMED,
            Events.TASK_FINISHED,
            Events.TASK_ERROR,
        ]

    def only_debug() -> list:
        return [Events.ITEM_UPDATED, Events.ITEM_PROGRESS]


@dataclass(kw_only=True)
class Event:
    id: str = field(default_factory=lambda: str(gen_random(16)), init=False)
    created_at: str = field(default_factory=lambda: str(datetime.datetime.now(tz=datetime.UTC).isoformat()))
    event: str
    title: str | None = None
    message: str | None = None
    data: Any
    extras: dict = field(default_factory=dict)

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "event": self.event,
            "title": self.title,
            "message": self.message,
            "data": self.data,
        }

    def __repr__(self) -> str:
        return f"Event(id={self.id}, created_at={self.created_at}, event={self.event}, title={self.title}, message={self.message} data={self.data})"

    def put(self, key: str, value: Any) -> None:
        self.extras[key] = value

    def datatype(self) -> str:
        return type(self.data).__name__

    def __str__(self):
        return f"Event(id={self.id}, created_at={self.created_at}, event={self.event}, title={self.title}, message={self.message})"


class EventListener:
    def __init__(self, name: str, callback: Callable[..., Any]):
        self.name: str = name
        self.call_back: Callable[..., Any] = callback
        self.is_coroutine: bool = inspect.iscoroutinefunction(callback)

    async def handle(self, event: Event, **kwargs):
        if self.is_coroutine:
            return self.call_back(event, self.name, **kwargs)

        return asyncio.create_task(self.call_back(event, self.name, **kwargs), name=f"EL-{self.name}-{event.id}")


class EventBus(metaclass=Singleton):
    def __init__(self):
        self._listeners: dict[str, list[tuple[str, EventListener]]] = {}
        self.debug: bool = False
        self._offload: BackgroundWorker | None = None

    @staticmethod
    def get_instance() -> "EventBus":
        return EventBus()

    def subscribe(self, event: str | list | tuple, callback: Callable[..., Any], name: str | None = None) -> "EventBus":
        all_events = Events.get_all()

        if isinstance(event, str):
            if "*" == event:
                event = all_events
            elif "frontend" == event:
                event = Events.frontend()
            else:
                if event not in all_events:
                    LOG.error(
                        "Listener '%s' tried to subscribe to unknown event '%s'.",
                        name,
                        event,
                        extra={"listener": name, "event": event},
                    )
                    return self

                event = [event]

        if not name:
            name = gen_random(12)

        for e in event:
            if e not in all_events:
                LOG.error(
                    "Listener '%s' tried to subscribe to unknown event '%s'.",
                    name,
                    e,
                    extra={"listener": name, "event": e},
                )
                continue

            if e not in self._listeners:
                self._listeners[e] = []

            self._listeners[e] = [(n, listener) for n, listener in self._listeners[e] if n != name]
            self._listeners[e].append((name, EventListener(name, callback)))

        LOG.debug("Listener '%s' has subscribed.", name, extra={"listener": name, "events": event})

        return self

    def unsubscribe(self, event: str | list | tuple, name: str) -> "EventBus":
        if isinstance(event, str):
            event = [event]

        events = []
        for e in event:
            if e in self._listeners:
                original_len: int = len(self._listeners[e])
                self._listeners[e] = [(n, listener) for n, listener in self._listeners[e] if n != name]
                if len(self._listeners[e]) < original_len:
                    events.append(e)

        if len(events) > 0:
            LOG.debug("Listener '%s' unsubscribed from '%s'.", name, events, extra={"listener": name, "events": events})

        return self

    def emit(
        self, event: str, data: Any | None = None, title: str | None = None, message: str | None = None, **kwargs
    ) -> None:
        if event not in self._listeners:
            return

        if not data:
            data = {}

        ev = Event(event=event, title=title, message=message, data=data)

        if self.debug or event not in Events.only_debug():
            LOG.debug(
                "Delivering '%s' event to %s listener(s).",
                ev.event,
                len(self._listeners[event]),
                extra={
                    "event_id": ev.id,
                    "event": ev.event,
                    "handler_count": len(self._listeners[event]),
                    "data": data,
                },
            )

        try:
            loop = asyncio.get_running_loop()

            async def execute_handlers():
                for _, handler in self._listeners[event]:
                    try:
                        if handler.is_coroutine:
                            coro = handler.call_back(ev, handler.name, **kwargs)
                            if asyncio.iscoroutine(coro):
                                await coro
                            else:
                                LOG.warning(
                                    "Async handler '%s' returned '%s' instead of a coroutine.",
                                    handler.name,
                                    type(coro).__name__,
                                    extra={"handler": handler.name, "returned_type": type(coro).__name__},
                                )
                        else:
                            await self._call(handler, ev, kwargs)
                    except Exception as e:
                        LOG.exception(
                            "Failed to emit '%s' event to listener '%s'.",
                            ev.event,
                            handler.name,
                            extra={
                                "event_id": ev.id,
                                "event": ev.event,
                                "handler": handler.name,
                                "exception_type": type(e).__name__,
                            },
                        )

            loop.create_task(execute_handlers())
        except RuntimeError:
            LOG.debug(
                "No event loop detected; offloading '%s' event to %s background listener(s).",
                ev.event,
                len(self._listeners[event]),
                extra={"event_id": ev.id, "event": ev.event, "handler_count": len(self._listeners[event])},
            )
            for _, handler in self._listeners[event]:
                try:
                    if not self._offload:
                        self._offload = BackgroundWorker.get_instance()

                    self._offload.submit(handler.handle, ev, **kwargs)
                except Exception as e:
                    LOG.exception(
                        "Failed to offload '%s' event to listener '%s'.",
                        ev.event,
                        handler.name,
                        extra={
                            "event_id": ev.id,
                            "event": ev.event,
                            "handler": handler.name,
                            "exception_type": type(e).__name__,
                        },
                    )

    def clear(self) -> None:
        self._listeners.clear()

    def debug_enable(self) -> None:
        self.debug = True

    def debug_disable(self) -> None:
        self.debug = False

    @staticmethod
    def _call(h, event, kw):
        async def call_handler():
            return h.call_back(event, h.name, **kw)

        return call_handler()
