import asyncio
import inspect
import logging
import threading
from queue import Empty, Queue

from .Singleton import Singleton

LOG: logging.Logger = logging.getLogger(__name__)


class BackgroundWorker(metaclass=Singleton):
    """
    Background worker to run tasks in a separate thread.
    This class uses a queue to submit tasks that will be executed in the background.
    It is designed to run in a separate thread and uses asyncio to handle asynchronous tasks.
    """

    _instance = None
    """The instance of the Notification class."""

    def __init__(self):
        self.queue = Queue()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    @staticmethod
    def get_instance() -> "BackgroundWorker":
        if BackgroundWorker._instance is None:
            BackgroundWorker._instance = BackgroundWorker()

        return BackgroundWorker._instance

    def _run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()

        # Start loop in a background thread
        def _loop_runner():
            try:
                loop.run_forever()
            except Exception as e:
                LOG.exception("Loop error: %s", e)

        threading.Thread(target=_loop_runner, daemon=True, name="Background Runner").start()

        while self.running:
            try:
                fn, args, kwargs = self.queue.get(timeout=1)
                try:
                    result = fn(*args, **kwargs)
                    if inspect.iscoroutine(result):
                        loop.call_soon_threadsafe(loop.create_task, result)
                except Exception as e:
                    LOG.exception(e)
                    LOG.error(f"Failed to run '{fn.__name__}'. {e!s}")
            except Empty:
                continue

    def submit(self, fn, *args, **kwargs):
        self.queue.put((fn, args, kwargs))

    def shutdown(self):
        self.running = False
        self.thread.join()
