import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable

from .Singleton import Singleton

LOG = logging.getLogger("EventsSubscriber")


class Events:
    """
    The events that can be emitted.
    """

    ADDED = "added"
    UPDATED = "updated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    CLEARED = "cleared"
    ERROR = "error"
    LOG_INFO = "log_info"
    LOG_SUCCESS = "log_success"

    INITIAL_DATA = "initial_data"
    YTDLP_CONVERT = "ytdlp_convert"
    ITEM_DELETE = "item_delete"
    ITEM_CANCEL = "item_cancel"
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


@dataclass(kw_only=True)
class Event:
    id: str
    data: dict


class EventsSubscriber(metaclass=Singleton):
    """
    This class is used to subscribe to and emit events to the registered listeners.
    """

    _instance = None
    """the instance of the EventsSubscriber"""

    _listeners: dict[str, list[str, Awaitable]] = {}
    """The listeners for the events."""

    def __init__(self):
        EventsSubscriber._instance = self

    @staticmethod
    def get_instance() -> "EventsSubscriber":
        """
        Get the instance of the EventsSubscriber.

        Returns:
            EventsSubscriber: The instance of the EventsSubscriber

        """
        if not EventsSubscriber._instance:
            EventsSubscriber._instance = EventsSubscriber()
        return EventsSubscriber._instance

    def subscribe(self, event: str | list | tuple, id: str, callback: Awaitable) -> "EventsSubscriber":
        """
        Subscribe to an event.

        Args:
            event (str): The event to subscribe to.
            id (str|None): The id of the subscriber, if None a random uuid will be generated.
            callback (Awaitable): The function to call. Must be a coroutine.

        Returns:
            EventsSubscriber: The instance of the EventsSubscriber

        """
        if isinstance(event, str):
            event = [event]

        for e in event:
            if e not in self._listeners:
                self._listeners[e] = {}

            self._listeners[e][id] = callback

        return self

    def unsubscribe(self, event: str | list | tuple, id: str) -> "EventsSubscriber":
        """
        Unsubscribe from an event.

        Args:
            event (str): The event to unsubscribe from.
            id (str): The id of the subscriber.

        Returns:
            EventsSubscriber: The instance of the EventsSubscriber

        """
        if isinstance(event, str):
            event = [event]

        for e in event:
            if e in self._listeners and id in self._listeners[e]:
                del self._listeners[e][id]

        return self

    def emit_sync(self, event: str, *args, **kwargs):
        """
        Emit an event synchronously.

        Args:
            event (str): The event to emit.
            *args: The arguments to pass to the event.
            **kwargs: The keyword arguments to pass to the event.

        Returns:
            list: The results are the return values of the coroutines. If the coroutine raises an exception,
                  the exception is caught and logged. If event does not exist, an empty list is returned.

        """
        if event not in self._listeners:
            return []

        results = []
        for id, callback in self._listeners[event].items():
            try:
                if "data" not in kwargs or not isinstance(kwargs["data"], Event):
                    data = Event(id=id, data={"args": args if args else [], **kwargs})
                else:
                    data = kwargs["data"]

                results.append(asyncio.get_event_loop().run_until_complete(callback(event, data)))
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to emit event '{event}' to '{id}'. Error message '{e!s}'.")

        return results

    def emit(self, event: str, *args, **kwargs):
        """
        Emit an event.

        Args:
            event (str): The event to emit.
            *args: The arguments to pass to the event.
            **kwargs: The keyword arguments to pass to the event.

        Returns:
            Awaitable: The task that was created to run the event.

        """
        if event not in self._listeners:
            return None

        tasks = []
        for id, callback in self._listeners[event].items():
            try:
                if args and isinstance(args[0], Event):
                    data = args[0]
                elif "data" in kwargs and isinstance(kwargs["data"], Event):
                    data = kwargs["data"]
                else:
                    data = Event(id=id, data={"args": args if args else [], **kwargs})

                tasks.append(asyncio.create_task(callback(event, data)))
            except Exception as e:
                LOG.error(f"Failed to emit event '{event}' to '{id}'. Error message '{e!s}'.")
                LOG.exception(e)

        return asyncio.gather(*tasks)
