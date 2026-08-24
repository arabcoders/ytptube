import asyncio
import threading
from typing import Any

from aiohttp import web
import pytest

from app.library.BackgroundWorker import BackgroundWorker


class TestBackgroundWorker:
    @pytest.fixture
    def worker(self):
        BackgroundWorker._reset_singleton()
        worker = BackgroundWorker()
        try:
            yield worker
        finally:
            if worker.thread and worker.thread.is_alive():
                asyncio.run(worker.on_shutdown(web.Application()))
            BackgroundWorker._reset_singleton()

    def test_attach_starts_shutdown_stops(self, worker) -> None:
        app = web.Application()

        worker.attach(app)
        assert worker.thread is not None
        assert worker.thread.is_alive() is True

        asyncio.run(worker.on_shutdown(app))
        assert worker.thread.is_alive() is False
        assert worker.loop_thread.is_alive() is False

    def test_submit_executes_sync_function(self, worker) -> None:
        app = web.Application()
        worker.attach(app)

        done = threading.Event()
        received: dict[str, Any] = {}

        def job(x: int, y: int) -> None:
            received["sum"] = x + y
            done.set()

        worker.submit(job, 2, 3)

        assert done.wait(timeout=2.0) is True
        assert received["sum"] == 5

        asyncio.run(worker.on_shutdown(app))

    def test_submit_executes_async_coroutine(self, worker) -> None:
        app = web.Application()
        worker.attach(app)

        done = threading.Event()

        async def coro_task(flag: threading.Event) -> None:
            await asyncio.sleep(0)
            flag.set()

        worker.submit(coro_task, done)

        assert done.wait(timeout=2.0) is True

        asyncio.run(worker.on_shutdown(app))

    def test_shutdown_cancels_pending(self, worker) -> None:
        app = web.Application()
        worker.attach(app)
        started = threading.Event()
        cancelled = threading.Event()

        async def pending() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        worker.submit(pending)
        assert started.wait(timeout=2) is True

        asyncio.run(worker.on_shutdown(app))
        assert cancelled.is_set() is True
        assert worker.thread.is_alive() is False
        assert worker.loop_thread is not None
        assert worker.loop_thread.is_alive() is False

    def test_submit_after_shutdown_fails(self, worker) -> None:
        app = web.Application()
        worker.attach(app)
        asyncio.run(worker.on_shutdown(app))

        with pytest.raises(RuntimeError, match="shutting down"):
            worker.submit(lambda: None)
