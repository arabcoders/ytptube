import asyncio
import inspect
import logging
import threading
from queue import Empty, Queue

from aiohttp import web

from .Services import Services
from .Singleton import Singleton

LOG: logging.Logger = logging.getLogger("BackgroundWorker")


class CloseThread:
    pass


class BackgroundWorker(metaclass=Singleton):
    """
    Background worker to run tasks in a separate thread.
    This class uses a queue to submit tasks that will be executed in the background.
    It is designed to run in a separate thread and uses asyncio to handle asynchronous tasks.
    """

    def __init__(self):
        self.queue: Queue = Queue()
        "The queue to hold the tasks."
        self.running = True
        "Whether the background worker is running or not."
        self.thread: threading.Thread = None
        "The thread that runs the background worker."

    @staticmethod
    def get_instance() -> "BackgroundWorker":
        return BackgroundWorker()

    def attach(self, app: web.Application):
        Services.get_instance().add("background_worker", self)
        app.on_shutdown.append(self.on_shutdown)

        LOG.debug("Starting background worker thread.")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    async def on_shutdown(self, _: web.Application):
        self.running = False
        try:
            LOG.debug("Shutting down background worker thread...")
            self.queue.put((CloseThread, (), {}))
            self.thread.join(timeout=5)
            LOG.debug("Background worker thread has been shut down.")
        except Exception as e:
            LOG.exception(
                "Failed to shut down background worker thread.",
                extra={"exception_type": type(e).__name__},
            )

    def _run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()

        # Start loop in a background thread
        def _loop_runner():
            try:
                loop.run_forever()
            except Exception:
                pass

        loop_thread = threading.Thread(target=_loop_runner, daemon=True, name="Background Runner")
        loop_thread.start()

        while self.running:
            try:
                fn, args, kwargs = self.queue.get(timeout=1)
                try:
                    if isinstance(fn, CloseThread):
                        LOG.info("Received shutdown signal for background worker.")
                        break

                    result = fn(*args, **kwargs)
                    if inspect.iscoroutine(result):
                        loop.call_soon_threadsafe(loop.create_task, result)
                except Exception as e:
                    function = getattr(fn, "__name__", fn.__class__.__name__)
                    LOG.exception(
                        "Failed to run background worker function '%s'.",
                        function,
                        extra={
                            "function": function,
                            "thread_name": threading.current_thread().name,
                            "exception_type": type(e).__name__,
                        },
                    )
            except Empty:
                continue

        try:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=5)
            loop.close()
            LOG.debug("Event loop has been stopped and closed.")
        except Exception as e:
            LOG.exception(
                "Failed to stop background worker event loop.",
                extra={"thread_name": loop_thread.name, "exception_type": type(e).__name__},
            )

    def submit(self, fn, *args, **kwargs):
        self.queue.put((fn, args, kwargs))
