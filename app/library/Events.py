import asyncio
import datetime
import logging
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any

from .Singleton import Singleton

LOG = logging.getLogger("Events")


def error(msg: str, data: dict | None = None) -> dict:
    """
    Create an error message.

    Args:
        msg (str): The message.
        data (dict|None): The data to include in the message.

    Returns:
        dict : The message wrapped in a dictionary.

    """
    return message("error", msg, data)


def warning(msg: str, data: dict | None = None) -> dict:
    """
    Create an error message.

    Args:
        msg (str): The message.
        data (dict|None): The data to include in the message.

    Returns:
        dict : The message wrapped in a dictionary.

    """
    return message("warning", msg, data)


def info(msg: str, data: dict | None = None) -> dict:
    """
    Create an info message.

    Args:
        msg (str): The message.
        data (dict|None): The data to include in the message.

    Returns:
        dict : The message wrapped in a dictionary.

    """
    return message("info", msg, data)


def success(msg: str, data: dict | None = None) -> dict:
    """
    Create a success message.

    Args:
        msg (str): The message.
        data (dict|None): The data to include in the message.

    Returns:
        dict : The message wrapped in a dictionary.

    """
    return message("success", msg, data)


def message(type: str, message: str, data: dict | None = None) -> dict:
    """
    Create a message.

    Args:
        type (str): The type of the message.
        message (str): The message.
        data (dict|None): The data to include in the message.

    Returns:
        dict : The message wrapped in a dictionary.

    """
    return {"type": type, "message": message, "data": data if data else {}}


class Events:
    """
    The events that can be emitted.
    """

    STARTUP = "startup"
    LOADED = "loaded"
    STARTED = "started"
    SHUTDOWN = "shutdown"

    ADDED = "added"
    UPDATED = "updated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    CLEARED = "cleared"
    ERROR = "error"
    LOG_INFO = "log_info"
    LOG_WARNING = "log_warning"
    LOG_ERROR = "log_error"
    LOG_SUCCESS = "log_success"

    INITIAL_DATA = "initial_data"
    ITEM_DELETE = "item_delete"
    ITEM_CANCEL = "item_cancel"
    ITEM_ERROR = "item_error"
    STATUS = "status"
    CLI_CLOSE = "cli_close"
    CLI_OUTPUT = "cli_output"
    UPDATE = "update"
    TEST = "test"
    ADD_URL = "add_url"

    CLI_POST = "cli_post"
    PAUSED = "paused"

    TASKS_ADD = "task_add"
    TASK_DISPATCHED = "task_dispatched"
    TASK_FINISHED = "task_finished"
    TASK_ERROR = "task_error"

    PRESETS_ADD = "presets_add"
    PRESETS_UPDATE = "presets_update"
    SCHEDULE_ADD = "schedule_add"

    CONDITIONS_ADD = "conditions_add"
    CONDITIONS_UPDATE = "conditions_update"

    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"

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
            Events.INITIAL_DATA,
            Events.ADDED,
            Events.ERROR,
            Events.LOG_INFO,
            Events.LOG_WARNING,
            Events.LOG_ERROR,
            Events.LOG_SUCCESS,
            Events.COMPLETED,
            Events.CANCELLED,
            Events.CLEARED,
            Events.UPDATED,
            Events.UPDATE,
            Events.PAUSED,
            Events.PRESETS_UPDATE,
            Events.STATUS,
            Events.CLI_CLOSE,
            Events.CLI_OUTPUT,
        ]

    def only_debug() -> list:
        """
        High frequency events that should only be logged in debug mode.

        Returns:
            list: The list of debug events.

        """
        return [Events.UPDATED]


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

    data: any
    """The data that was passed to the event."""

    def serialize(self) -> dict:
        """
        Serialize the event.

        Returns:
            dict: The serialized event.

        """
        return {"id": self.id, "created_at": self.created_at, "event": self.event, "data": self.data}

    def __repr__(self):
        return f"Event(id={self.id}, created_at={self.created_at}, event={self.event}, data={self.data})"

    def datatype(self) -> str:
        """
        Get the datatype of the data.

        Returns:
            str: The datatype of the data.

        """
        return type(self.data).__name__

    def __str__(self):
        return f"Event(id={self.id}, created_at={self.created_at}, event={self.event})"


class EventListener:
    name: str
    is_coroutine: bool = False
    call_back: callable

    def __init__(self, name: str, callback: callable):
        self.name = name
        self.call_back = callback
        self.is_coroutine = asyncio.iscoroutinefunction(callback)

    async def handle(self, event: Event, **kwargs):
        if self.is_coroutine:
            return self.call_back(event, self.name, **kwargs)

        return asyncio.create_task(self.call_back(event, self.name, **kwargs), name=f"EL-{self.name}-{event.id}")


class EventBus(metaclass=Singleton):
    """
    This class is used to subscribe to and emit events to the registered listeners.
    """

    _instance = None
    """the instance of the EventsSubscriber"""

    _listeners: dict[str, list[str, EventListener]] = {}
    """The listeners for the events."""

    debug: bool = False
    """Whether to log debug messages or not."""

    def __init__(self):
        EventBus._instance = self

        from .config import Config

        self.debug = Config.get_instance().debug

    @staticmethod
    def get_instance() -> "EventBus":
        """
        Get the instance of the EventsSubscriber.

        Returns:
            EventsSubscriber: The instance of the EventsSubscriber

        """
        if not EventBus._instance:
            EventBus._instance = EventBus()

        return EventBus._instance

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

    def sync_emit(self, event: str, data: Any, loop=None, wait: bool = True, **kwargs):
        """
        Emit event and (optionally) wait for results.

        Args:
            event (str): The event to emit.
            data (Any): The data to pass to the event.
            loop (asyncio.AbstractEventLoop | None): The event loop to use. If None, the current running loop is used.
            wait (bool): Whether to wait for the results of the event handlers. Defaults to True.
            **kwargs: Additional keyword arguments to pass to the event

        Returns:
            list: The results are the return values of the coroutines. If the coroutine raises an exception,
                  the exception is caught and logged. If event does not exist, an empty list is returned.
                  If wait is False, a list of asyncio.Task objects is returned instead if we are in a running event loop,
                  or the result of the coroutine if we are not in a running event loop.

        """
        if event not in self._listeners:
            return []

        async def emit_all():
            ev = Event(event=event, data=data)
            LOG.debug(f"Emitting event '{ev.id}: {ev.event}'.", extra={"data": data})

            res: list = []

            for h in self._listeners[event].values():
                try:
                    res.append(await h.handle(ev, **kwargs))
                except Exception as e:
                    LOG.exception(e)
                    LOG.error(f"Failed to emit event '{event}' to '{h.name}'. Error message '{e!s}'.")

            return res

        try:
            loop = loop or asyncio.get_running_loop()
            in_same_loop: bool = asyncio.get_running_loop() is loop
        except RuntimeError:
            loop = None
            in_same_loop = False

        if loop is None or not loop.is_running():
            return asyncio.run(emit_all())

        if in_same_loop:
            if wait:
                msg = (
                    "Calling EventsBus.sync_emit(...,wait=True) from within the running event loop would cause dead-lock. "
                    "Use `await EventsBus.emit(...)` or `EventsBus.sync_emit(..., wait=False)`."
                )
                raise RuntimeError(msg)

            return loop.create_task(emit_all())

        fut = asyncio.run_coroutine_threadsafe(emit_all(), loop)
        return fut.result() if wait else fut

    async def emit(self, event: str, data: Any, **kwargs) -> Awaitable:
        """
        Emit an event.

        Args:
            event (str): The event to emit.
            data (Any): The data to pass to the event.
            **kwargs: The keyword arguments to pass to the event.

        Returns:
            Awaitable: The task that was created to run the event.

        """
        if event not in self._listeners:
            return []

        ev = Event(event=event, data=data)

        if self.debug or event not in Events.only_debug():
            LOG.debug(f"Emitting event '{ev.id}: {ev.event}'.", extra={"data": data})

        tasks = []
        for handler in self._listeners[event].values():
            try:
                tasks.append(handler.handle(ev, **kwargs))
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to emit event '{ev.event}' to '{handler.name}'. Error message '{e!s}'.")

        return asyncio.gather(*tasks)
