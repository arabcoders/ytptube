import asyncio
import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure aiocron module exists to allow importing Scheduler without external dep
if "aiocron" not in sys.modules:
    aiocron_stub = types.ModuleType("aiocron")

    class _CronImportStub:  # Minimal placeholder; tests will patch real behavior per-test
        def __init__(self, *args, **kwargs):
            pass

        def stop(self) -> None:
            pass

        @property
        def uuid(self) -> str:
            return "stub-uuid"

    aiocron_stub.Cron = _CronImportStub
    sys.modules["aiocron"] = aiocron_stub


from app.library.Events import EventBus, Events
from app.library.Scheduler import Scheduler


class DummyCron:
    """Simple Cron stub to capture construction and allow stop()."""

    def __init__(
        self,
        *,
        spec: str,
        func: callable,
        args: tuple = (),
        kwargs: dict | None = None,
        uuid: str | None = None,
        start: bool | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.spec = spec
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self._uuid = uuid or "generated-uuid"
        self.start = start
        self.loop = loop
        self.stopped = False

    @property
    def uuid(self) -> str:
        return self._uuid

    def stop(self) -> None:
        self.stopped = True


class FailingCron(DummyCron):
    def stop(self) -> None:
        msg = "stop failed"
        raise RuntimeError(msg)


class TestScheduler:
    """Tests for the Scheduler singleton and behavior."""

    def setup_method(self) -> None:
        # Reset singletons between tests
        Scheduler._reset_singleton()
        EventBus._reset_singleton()

    def teardown_method(self) -> None:
        Scheduler._reset_singleton()
        EventBus._reset_singleton()

    def test_singleton_behavior(self) -> None:
        s1 = Scheduler()
        s2 = Scheduler()
        s3 = Scheduler.get_instance()

        assert s1 is s2 is s3

    @patch("app.library.Scheduler.Cron", new=DummyCron)
    def test_add_creates_and_stores_job(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            sched = Scheduler(loop=loop)

            def fn(a: int, b: int) -> int:  # noqa: ARG001
                return 42

            job_id = sched.add(
                timer="*/5 * * * *",
                func=fn,
                args=(1, 2),
                kwargs={"x": 3},
                id="job1",
            )

            assert job_id == "job1"
            assert sched.has("job1") is True

            job = sched.get("job1")
            assert isinstance(job, DummyCron)
            assert job.spec == "*/5 * * * *"
            assert job.args == (1, 2)
            assert job.kwargs == {"x": 3}
            assert job.loop is loop
            assert job.start is True
        finally:
            loop.close()

    @patch("app.library.Scheduler.Cron", new=DummyCron)
    def test_add_replaces_existing_job(self) -> None:
        sched = Scheduler()

        # Seed with an existing job
        old = DummyCron(spec="* * * * *", func=lambda: None, uuid="job1", start=True, loop=sched._loop)
        sched._jobs["job1"] = old

        # Replace with a new one
        new_id = sched.add(timer="*/2 * * * *", func=lambda: None, id="job1")

        assert new_id == "job1"
        assert sched.has("job1") is True
        new_job = sched.get("job1")
        assert new_job is not old
        # Old job should have been stopped via remove()
        assert old.stopped is True

    @patch("app.library.Scheduler.Cron", new=DummyCron)
    def test_remove_single_job_success(self) -> None:
        sched = Scheduler()
        cron = DummyCron(spec="* * * * *", func=lambda: None, uuid="jobA", start=True, loop=sched._loop)
        sched._jobs["jobA"] = cron

        result = sched.remove("jobA")

        assert result is True
        assert cron.stopped is True
        assert sched.has("jobA") is False

    @patch("app.library.Scheduler.Cron", new=FailingCron)
    def test_remove_single_job_failure_on_stop(self) -> None:
        sched = Scheduler()
        cron = FailingCron(spec="* * * * *", func=lambda: None, uuid="jobB", start=True, loop=sched._loop)
        sched._jobs["jobB"] = cron

        result = sched.remove("jobB")

        assert result is False
        # Job should remain since stop failed
        assert sched.has("jobB") is True

    @patch("app.library.Scheduler.Cron", new=DummyCron)
    def test_remove_list_of_jobs(self) -> None:
        sched = Scheduler()
        for jid in ("j1", "j2", "j3"):
            sched._jobs[jid] = DummyCron(spec="* * * * *", func=lambda: None, uuid=jid, start=True, loop=sched._loop)

        result = sched.remove(["j1", "j2", "j3"])

        assert result is True
        assert all(not sched.has(j) for j in ("j1", "j2", "j3"))

    @pytest.mark.asyncio
    @patch("app.library.Scheduler.Cron", new=DummyCron)
    async def test_on_shutdown_stops_and_clears_jobs(self) -> None:
        from aiohttp import web

        sched = Scheduler()
        a = DummyCron(spec="* * * * *", func=lambda: None, uuid="a", start=True, loop=sched._loop)
        b = DummyCron(spec="* * * * *", func=lambda: None, uuid="b", start=True, loop=sched._loop)
        sched._jobs = {"a": a, "b": b}

        await sched.on_shutdown(web.Application())

        assert a.stopped is True
        assert b.stopped is True
        assert len(sched.get_all()) == 0

    @pytest.mark.asyncio
    @patch("app.library.Scheduler.Cron", new=DummyCron)
    async def test_attach_registers_shutdown_and_handles_schedule_add_event(self) -> None:
        from aiohttp import web

        app = web.Application()
        sched = Scheduler()
        sched.attach(app)

        # on_shutdown handler should be registered
        assert Scheduler.on_shutdown in [cb.__func__ if hasattr(cb, "__func__") else cb for cb in app.on_shutdown]

        # Patch add to verify it is called from event handler
        add_spy = MagicMock(wraps=sched.add)
        # Bind spy to the instance
        sched.add = add_spy

        # Emit schedule add event
        EventBus.get_instance().emit(
            Events.SCHEDULE_ADD,
            data={
                "timer": "*/3 * * * *",
                "func": lambda: None,
                "args": (1,),
                "kwargs": {"k": "v"},
                "id": "evt-job",
            },
        )

        # Allow event loop to schedule and run handler
        await asyncio.sleep(0.02)

        add_spy.assert_called_once()
        kwargs = add_spy.call_args.kwargs
        assert kwargs["timer"] == "*/3 * * * *"
        assert callable(kwargs["func"]) is True
        assert kwargs["args"] == (1,)
        assert kwargs["kwargs"] == {"k": "v"}
        assert kwargs["id"] == "evt-job"

    @patch("app.library.Scheduler.Cron")
    def test_add_executes_function_when_cron_runs(self, cron_patch) -> None:
        # Cron stub that auto-runs the function on creation when start=True
        class AutoRunCron(DummyCron):
            def __init__(self, *_, spec: str, func: callable, args: tuple = (), kwargs: dict | None = None, uuid: str | None = None, start: bool | None = None, loop: asyncio.AbstractEventLoop | None = None):
                super().__init__(spec=spec, func=func, args=args, kwargs=kwargs, uuid=uuid, start=start, loop=loop)
                if start:
                    # Simulate immediate execution
                    self.func(*self.args, **self.kwargs)

        cron_patch.side_effect = AutoRunCron

        sched = Scheduler()
        ran: dict[str, Any] = {"count": 0, "last": None}

        def job_func(x: int, y: int, label: str = "") -> None:
            ran["count"] += 1
            ran["last"] = (x, y, label)

        _ = sched.add(timer="*/1 * * * *", func=job_func, args=(2, 3), kwargs={"label": "ok"}, id="run1")

        assert ran["count"] == 1
        assert ran["last"] == (2, 3, "ok")

    @pytest.mark.asyncio
    @patch("app.library.Scheduler.Cron")
    async def test_event_schedule_runs_function(self, cron_patch) -> None:
        # Cron stub that auto-runs the function on creation
        class AutoRunCron(DummyCron):
            def __init__(self, *_, spec: str, func: callable, args: tuple = (), kwargs: dict | None = None, uuid: str | None = None, start: bool | None = None, loop: asyncio.AbstractEventLoop | None = None):
                super().__init__(spec=spec, func=func, args=args, kwargs=kwargs, uuid=uuid, start=start, loop=loop)
                if start:
                    self.func(*self.args, **self.kwargs)

        cron_patch.side_effect = AutoRunCron

        from aiohttp import web

        app = web.Application()
        sched = Scheduler()
        sched.attach(app)

        bucket: list[tuple[int, str]] = []

        def job(val: int, tag: str) -> None:
            bucket.append((val, tag))

        # Emit event that should cause add() and immediate execution via AutoRunCron
        EventBus.get_instance().emit(
            Events.SCHEDULE_ADD,
            data={
                "timer": "*/1 * * * *",
                "func": job,
                "args": (7,),
                "kwargs": {"tag": "evt"},
                "id": "evt-run",
            },
        )

        # Give the event handler a tick to run
        await asyncio.sleep(0.02)

        assert bucket == [(7, "evt")]
