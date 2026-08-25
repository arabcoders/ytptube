import asyncio
import inspect
import threading
from queue import Empty, Queue

from aiohttp import web

from app.library.logging import get_logger

from .Services import Services
from .Singleton import Singleton

LOG = get_logger()
SHUTDOWN_ERROR = "Background worker is shutting down"


class CloseThread:
    pass


class BackgroundWorker(metaclass=Singleton):
    """Run queued synchronous work in one thread and coroutine work on its event-loop thread."""

    def __init__(self):
        self.queue: Queue = Queue()
        self.running = True
        self.thread: threading.Thread | None = None
        self.loop_thread: threading.Thread | None = None
        self._submit_lock = threading.Lock()
        self._tasks: set[asyncio.Task] = set()

    @staticmethod
    def get_instance() -> "BackgroundWorker":
        return BackgroundWorker()

    def attach(self, app: web.Application):
        Services.get_instance().add("background_worker", self)
        app.on_shutdown.append(self.on_shutdown)

        LOG.debug("Started background worker thread.")
        self.thread = threading.Thread(target=self._run, daemon=True, name="Background Worker")
        self.thread.start()

    async def on_shutdown(self, _: web.Application):
        with self._submit_lock:
            self.running = False
        LOG.debug("Stopping background worker thread.")
        self.queue.put((CloseThread, (), {}))
        try:
            if self.thread is not None:
                await asyncio.wait_for(asyncio.to_thread(self.thread.join, 5), timeout=5.5)
        except Exception as e:
            LOG.exception(
                "Failed to shut down background worker thread.",
                extra={"exception_type": type(e).__name__},
            )
            raise
        if self.thread is not None and self.thread.is_alive():
            msg = "Background worker thread did not stop before the deadline."
            LOG.error(msg)
            raise TimeoutError(msg)
        LOG.debug("Background worker thread has been shut down.")

    def _run(self):
        loop = asyncio.new_event_loop()

        def _loop_runner():
            asyncio.set_event_loop(loop)
            try:
                loop.run_forever()
            except Exception:
                pass

        self.loop_thread = threading.Thread(target=_loop_runner, daemon=True, name="Background Runner")
        self.loop_thread.start()

        while self.running:
            try:
                fn, args, kwargs = self.queue.get(timeout=1)
                try:
                    if fn is CloseThread:
                        LOG.info("Received shutdown signal for background worker.")
                        break

                    result = fn(*args, **kwargs)
                    if inspect.iscoroutine(result):
                        loop.call_soon_threadsafe(self._track_task, loop, result)
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
            cleanup = asyncio.run_coroutine_threadsafe(self._cancel_tasks(), loop)
            try:
                cleanup.result(timeout=5)
            finally:
                loop.call_soon_threadsafe(loop.stop)
                self.loop_thread.join(timeout=5)
                if self.loop_thread.is_alive():
                    msg = "Background worker event loop thread did not stop before the deadline."
                    raise TimeoutError(msg)
                loop.close()
                LOG.debug("Stopped background worker event loop.")
        except Exception as e:
            LOG.exception(
                "Failed to stop background worker event loop.",
                extra={"thread_name": self.loop_thread.name, "exception_type": type(e).__name__},
            )

    def _track_task(self, loop: asyncio.AbstractEventLoop, coroutine) -> None:
        task = loop.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._forget_task)

    def _forget_task(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled():
            task.exception()

    async def _cancel_tasks(self) -> None:
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def submit(self, fn, *args, **kwargs):
        with self._submit_lock:
            if not self.running:
                raise RuntimeError(SHUTDOWN_ERROR)
            self.queue.put((fn, args, kwargs))
