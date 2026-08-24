import asyncio
import inspect
import threading
from queue import Empty, Queue

from aiohttp import web

from app.library.logging import get_logger

from .Services import Services
from .Singleton import Singleton

LOG = get_logger()


class CloseThread:
    pass


class BackgroundWorker(metaclass=Singleton):
    """Run queued synchronous work in one thread and coroutine work on its event-loop thread."""

    def __init__(self):
        self.queue: Queue = Queue()
        self.running = True
        self.thread: threading.Thread | None = None

    @staticmethod
    def get_instance() -> "BackgroundWorker":
        return BackgroundWorker()

    def attach(self, app: web.Application):
        Services.get_instance().add("background_worker", self)
        app.on_shutdown.append(self.on_shutdown)

        LOG.debug("Started background worker thread.")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    async def on_shutdown(self, _: web.Application):
        self.running = False
        try:
            LOG.debug("Stopping background worker thread.")
            self.queue.put((CloseThread, (), {}))
            if self.thread:
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
            LOG.debug("Stopped background worker event loop.")
        except Exception as e:
            LOG.exception(
                "Failed to stop background worker event loop.",
                extra={"thread_name": loop_thread.name, "exception_type": type(e).__name__},
            )

    def submit(self, fn, *args, **kwargs):
        self.queue.put((fn, args, kwargs))
