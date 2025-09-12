import asyncio
import datetime
import logging
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any

from .BackgroundWorker import BackgroundWorker
from .Singleton import Singleton

LOG: logging.Logger = logging.getLogger("Events")


class Events:
    """
    The events that can be emitted.
    """

    STARTUP: str = "startup"
    LOADED: str = "loaded"
    STARTED: str = "started"
    SHUTDOWN: str = "shutdown"

    CONNECTED: str = "connected"

    LOG_INFO: str = "log_info"
    LOG_WARNING: str = "log_warning"
    LOG_ERROR: str = "log_error"
    LOG_SUCCESS: str = "log_success"

    ITEM_ADDED: str = "item_added"
    ITEM_UPDATED: str = "item_updated"
    ITEM_COMPLETED: str = "item_completed"
    ITEM_CANCELLED: str = "item_cancelled"
    ITEM_DELETED: str = "item_deleted"
    ITEM_PAUSED: str = "item_paused"
    ITEM_RESUMED: str = "item_resumed"
    ITEM_MOVED: str = "item_moved"
    ITEM_STATUS: str = "item_status"
    ITEM_ERROR: str = "item_error"

    TEST: str = "test"
    ADD_URL: str = "add_url"

    PAUSED: str = "paused"
    RESUMED: str = "resumed"

    CLI_POST: str = "cli_post"
    CLI_CLOSE: str = "cli_close"
    CLI_OUTPUT: str = "cli_output"

    TASKS_ADD: str = "task_add"
    TASK_DISPATCHED: str = "task_dispatched"
    TASK_FINISHED: str = "task_finished"
    TASK_ERROR: str = "task_error"

    PRESETS_ADD: str = "presets_add"
    PRESETS_UPDATE: str = "presets_update"

    DLFIELDS_ADD: str = "dlfields_add"
    DLFIELDS_UPDATE: str = "dlfields_update"

    SCHEDULE_ADD: str = "schedule_add"

    CONDITIONS_ADD: str = "conditions_add"
    CONDITIONS_UPDATE: str = "conditions_update"

    SUBSCRIBED: str = "subscribed"
    UNSUBSCRIBED: str = "unsubscribed"

    def get_all() -> list:
        """
        Get all the events.

        Returns:
            list: The list of events.

        """
        return [
            getattr(Events, ev) for ev in dir(Events) if not ev.startswith("_") and not callable(getattr(Events, ev))
        ]

    def frontend() -> list:
        """
        Get the frontend events.

        Returns:
            list: The list of frontend events.

        """
        return [
            Events.CONNECTED,
            Events.LOG_INFO,
            Events.LOG_WARNING,
            Events.LOG_ERROR,
            Events.LOG_SUCCESS,
            Events.ITEM_ADDED,
            Events.ITEM_UPDATED,
            Events.ITEM_COMPLETED,
            Events.ITEM_CANCELLED,
            Events.ITEM_DELETED,
            Events.ITEM_MOVED,
            Events.ITEM_STATUS,
            Events.PAUSED,
            Events.RESUMED,
            Events.CLI_CLOSE,
            Events.CLI_OUTPUT,
            Events.PRESETS_UPDATE,
            Events.DLFIELDS_UPDATE,
        ]

    def only_debug() -> list:
        """
        High frequency events that should only be logged in debug mode.

        Returns:
            list: The list of debug events.

        """
        return [Events.ITEM_UPDATED, Events.CLI_OUTPUT]


@dataclass(kw_only=True)
class Event:
    """
    Event is a data transfer object that represents an event that was emitted.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)
    """The id of the event."""

    created_at: str = field(default_factory=lambda: str(datetime.datetime.now(tz=datetime.UTC).isoformat()))
    """The time the event was created."""

    event: str
    """The event that was emitted."""

    title: str | None = None
    """The title of the event, if any."""

    message: str | None = None
    """The message of the event, if any."""

    data: Any
    """The data that was passed to the event."""

    extras: dict = field(default_factory=dict)
    """Listeners can add extra data to the event."""

    def serialize(self) -> dict:
        """
        Serialize the event.

        Returns:
            dict: The serialized event.

        """
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
        """
        Put extra data to the event.

        Args:
            key (str): The key of the extra data.
            value (Any): The value of the extra data.

        """
        self.extras[key] = value

    def datatype(self) -> str:
        """
        Get the datatype of the data.

        Returns:
            str: The datatype of the data.

        """
        return type(self.data).__name__

    def __str__(self):
        return f"Event(id={self.id}, created_at={self.created_at}, event={self.event}, title={self.title}, message={self.message})"


class EventListener:
    def __init__(self, name: str, callback: callable):
        self.name: str = name
        "The name of the listener."
        self.call_back: callable = callback
        "The callback function to call when the event is emitted."
        self.is_coroutine: bool = asyncio.iscoroutinefunction(callback)
        "Whether the callback is a coroutine function or not."

    async def handle(self, event: Event, **kwargs):
        if self.is_coroutine:
            return self.call_back(event, self.name, **kwargs)

        return asyncio.create_task(self.call_back(event, self.name, **kwargs), name=f"EL-{self.name}-{event.id}")


class EventBus(metaclass=Singleton):
    """
    This class is used to subscribe to and emit events to the registered listeners.
    """

    def __init__(self):
        self._listeners: dict[str, list[str, EventListener]] = {}
        "The listeners for the events."

        self.debug: bool = False
        "Whether to log debug messages or not."

        self._offload: BackgroundWorker = None
        "The background worker to offload tasks to."

    @staticmethod
    def get_instance() -> "EventBus":
        """
        Get the instance of the EventsSubscriber.

        Returns:
            EventsSubscriber: The instance of the EventsSubscriber

        """
        return EventBus()

    def subscribe(self, event: str | list | tuple, callback: Awaitable, name: str | None = None) -> "EventBus":
        """
        Subscribe to an event.

        Args:
            event (str): The event to subscribe to.
            name (str|None): The name of the subscriber, if None a random uuid will be generated.
            callback(Event, name, **kwargs) (Awaitable): The function to call. Must be a coroutine.

        Returns:
            EventsSubscriber: The instance of the EventsSubscriber

        """
        all_events = Events.get_all()

        if isinstance(event, str):
            if "*" == event:
                event = all_events
            elif "frontend" == event:
                event = Events.frontend()
            else:
                if event not in all_events:
                    LOG.error(f"'{name}' attempted to listen on '{event}' which does not exist.")
                    return self

                event = [event]

        if not name:
            name = str(uuid.uuid4())

        for e in event:
            if e not in all_events:
                LOG.error(f"'{name}' attempted to listen on '{e}' which does not exist.")
                continue

            if e not in self._listeners:
                self._listeners[e] = {}

            self._listeners[e][name] = EventListener(name, callback)

        LOG.debug(f"'{name}' subscribed to '{event}'.")

        return self

    def unsubscribe(self, event: str | list | tuple, name: str) -> "EventBus":
        """
        Unsubscribe from an event.

        Args:
            event (str): The event to unsubscribe from.
            name (str): The name of the subscriber.

        Returns:
            EventsSubscriber: The instance of the EventsSubscriber

        """
        if isinstance(event, str):
            event = [event]

        events = []
        for e in event:
            if e in self._listeners and name in self._listeners[e]:
                events.append(e)
                del self._listeners[e][name]

        if len(events) > 0:
            LOG.debug(f"'{name}' unsubscribed from '{events}'.")

        return self

    def emit(
        self, event: str, data: Any | None = None, title: str | None = None, message: str | None = None, **kwargs
    ) -> None:
        """
        Emit an event to all registered listeners.

        Args:
            event (str): The event to emit.
            data (Any|None): The data to pass to the event.
            title (str | None): The title of the event, if any.
            message (str | None): The message of the event, if any.
            **kwargs: The keyword arguments to pass to the event.

        """
        if event not in self._listeners:
            return

        if not data:
            data = {}

        ev = Event(event=event, title=title, message=message, data=data)

        if self.debug or event not in Events.only_debug():
            LOG.debug(f"Emitting event '{ev.id}: {ev.event}'.", extra={"data": data})

        try:
            loop = asyncio.get_running_loop()

            for handler in self._listeners[event].values():
                try:
                    if handler.is_coroutine:
                        coro = handler.call_back(ev, handler.name, **kwargs)
                        if asyncio.iscoroutine(coro):
                            loop.create_task(coro)
                        else:
                            LOG.warning(f"Expected coroutine from async handler '{handler.name}', got {type(coro)}")
                    else:
                        loop.create_task(self._call(handler, ev, kwargs), name=f"sync-handler-{handler.name}-{ev.id}")
                except Exception as e:
                    LOG.exception(e)
                    LOG.error(f"Failed to emit event '{ev.event}' to '{handler.name}'. Error message '{e!s}'.")
        except RuntimeError:
            LOG.debug(f"No event loop detected - using BackgroundWorker for {len(self._listeners[event])} handlers")
            for handler in self._listeners[event].values():
                try:
                    if not self._offload:
                        self._offload = BackgroundWorker.get_instance()

                    self._offload.submit(handler.handle, ev, **kwargs)
                except Exception as e:
                    LOG.exception(e)
                    LOG.error(f"Failed to emit event '{ev.event}' to '{handler.name}'. Error message '{e!s}'.")

    def clear(self) -> None:
        """
        Clear all listeners. Useful for testing.
        """
        self._listeners.clear()

    def debug_enable(self) -> None:
        """
        Enable debug logging.
        """
        self.debug = True

    def debug_disable(self) -> None:
        """
        Disable debug logging.
        """
        self.debug = False

    @staticmethod
    def _call(h, event, kw):
        async def call_handler():
            return h.call_back(event, h.name, **kw)

        return call_handler()
