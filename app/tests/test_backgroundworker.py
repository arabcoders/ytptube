import threading
from typing import Any

from aiohttp import web

from app.library.BackgroundWorker import BackgroundWorker


class TestBackgroundWorker:
    def setup_method(self) -> None:
        BackgroundWorker._reset_singleton()

    def teardown_method(self) -> None:
        # Attempt to stop any running worker thread
        try:
            worker = BackgroundWorker()
            if worker.thread and worker.thread.is_alive():
                worker.running = False
                worker.queue.put((BackgroundWorker, (), {}))
                worker.thread.join(timeout=2)
        except Exception:
            pass
        BackgroundWorker._reset_singleton()

    def test_attach_starts_and_shutdown_stops(self) -> None:
        app = web.Application()
        worker = BackgroundWorker()

        worker.attach(app)
        assert worker.thread is not None
        assert worker.thread.is_alive() is True

        # Shutdown should stop the worker thread
        # on_shutdown is async; call via event loop runner
        # Using a small helper to run the coroutine
        import asyncio

        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
        except RuntimeError:
            pass

        asyncio.get_event_loop().run_until_complete(worker.on_shutdown(app))

        # Give a short moment for the background thread to exit
        worker.thread.join(timeout=2)
        assert worker.thread.is_alive() is False

    def test_submit_executes_sync_function(self) -> None:
        app = web.Application()
        worker = BackgroundWorker()
        worker.attach(app)

        done = threading.Event()
        received: dict[str, Any] = {}

        def job(x: int, y: int) -> None:
            received["sum"] = x + y
            done.set()

        worker.submit(job, 2, 3)

        assert done.wait(timeout=2.0) is True
        assert received["sum"] == 5

        # Cleanup
        import asyncio

        asyncio.get_event_loop().run_until_complete(worker.on_shutdown(app))

    def test_submit_executes_async_coroutine(self) -> None:
        app = web.Application()
        worker = BackgroundWorker()
        worker.attach(app)

        done = threading.Event()

        async def coro_task(flag: threading.Event) -> None:
            # Simulate a small async operation
            await asyncio.sleep(0)
            flag.set()

        # Submit coroutine factory
        import asyncio

        worker.submit(coro_task, done)

        assert done.wait(timeout=2.0) is True

        # Cleanup
        asyncio.get_event_loop().run_until_complete(worker.on_shutdown(app))
