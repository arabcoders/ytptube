from __future__ import annotations

import asyncio
import functools
import os
import shutil
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psutil

from app.library.config import Config
from app.library.Events import EventBus, Events
from app.library.log import get_logger
from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.Singleton import Singleton

from . import monitor_cgroup as cg
from .monitor_store import MonitorStore

if TYPE_CHECKING:
    from logging import Logger

    from aiohttp import web

LOG: Logger = get_logger()


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


def _mb(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value / 1024 / 1024, 2)


@dataclass(kw_only=True)
class ResourceSample:
    ts: float

    process_cpu_percent: float
    system_cpu_percent: float
    cpu_limit: float | None
    effective_cpu_count: float

    rss_mb: float | None
    uss_mb: float | None
    vms_mb: float | None

    memory_percent: float | None
    cgroup_memory: dict[str, Any]

    process_read_bps: float | None
    process_write_bps: float | None
    process_io_available: bool

    disk_read_bps: float | None
    disk_write_bps: float | None

    disk_usage: dict[str, Any]

    network_recv_bps: float | None
    network_sent_bps: float | None

    threads: int | None
    open_files: int | None
    connections: int | None

    children: list[dict[str, Any]]

    active_jobs: int
    queued_jobs: int
    is_paused: bool

    uptime_seconds: float

    def to_flat(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "process_cpu_percent": self.process_cpu_percent,
            "system_cpu_percent": self.system_cpu_percent,
            "rss_mb": self.rss_mb,
            "uss_mb": self.uss_mb,
            "memory_percent": self.memory_percent,
            "process_read_bps": self.process_read_bps,
            "process_write_bps": self.process_write_bps,
            "disk_read_bps": self.disk_read_bps,
            "disk_write_bps": self.disk_write_bps,
            "network_recv_bps": self.network_recv_bps,
            "network_sent_bps": self.network_sent_bps,
            "threads": self.threads,
            "open_files": self.open_files,
            "connections": self.connections,
            "active_jobs": self.active_jobs,
            "queued_jobs": self.queued_jobs,
            "is_paused": int(self.is_paused),
            "children_count": len(self.children),
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _process_io(proc: psutil.Process) -> dict[str, Any]:
    try:
        io = proc.io_counters()
        return {
            "available": True,
            "read_bytes": getattr(io, "read_bytes", None),
            "write_bytes": getattr(io, "write_bytes", None),
            "read_count": getattr(io, "read_count", None),
            "write_count": getattr(io, "write_count", None),
        }
    except Exception:
        return {"available": False, "read_bytes": None, "write_bytes": None}


def _disk_usage(paths: list[str]) -> dict[str, Any]:
    result = {}
    for path in paths:
        try:
            usage = shutil.disk_usage(path)
            result[path] = {
                "total_gb": round(usage.total / 1024**3, 2),
                "used_gb": round(usage.used / 1024**3, 2),
                "free_gb": round(usage.free / 1024**3, 2),
                "used_percent": round((usage.used / usage.total) * 100, 2),
            }
        except Exception:  # noqa: S112
            continue
    return result


def _children_stats(proc: psutil.Process, limit: int = 10) -> list[dict[str, Any]]:
    result = []
    try:
        children = proc.children(recursive=True)
    except Exception:
        return result

    for child in children:
        try:
            with child.oneshot():
                mem = child.memory_info()
                result.append(
                    {
                        "pid": child.pid,
                        "name": child.name() or "unknown",
                        "status": child.status(),
                        "cpu_percent": child.cpu_percent(),
                        "rss_mb": _mb(mem.rss),
                        "threads": child.num_threads(),
                    }
                )
        except Exception:  # noqa: S112
            continue

    result.sort(key=lambda item: item.get("rss_mb") or 0, reverse=True)
    return result[:limit]


class ResourceTracker(metaclass=Singleton):
    @staticmethod
    def get_instance() -> ResourceTracker:
        return ResourceTracker()

    def __init__(self):
        self._config = Config.get_instance()
        self._notify = EventBus.get_instance()
        self._scheduler = Scheduler.get_instance()
        self._store: MonitorStore | None = None
        self._history: deque[ResourceSample] = deque(maxlen=900)
        self._proc = psutil.Process(os.getpid())
        self._started_at = time.time()
        self._cpu_limit: float | None = None
        self._effective_cpus: float = 1.0
        self._disk_paths: list[str] = []
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_ts: float | None = None
        self._last_proc_io: dict[str, Any] | None = None
        self._last_disk_io: Any = None
        self._last_net_io: Any = None
        self._prune_lock = threading.Lock()
        self._prune_count = 0
        self._subscribers: set[asyncio.Queue[ResourceSample | None]] = set()
        self._subscriber_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _enabled(self) -> bool:
        return self._config.monitor_enabled

    def attach(self, _app: web.Application) -> None:
        if not self._enabled():
            LOG.info("Resource monitoring is disabled (YTP_MONITOR_ENABLED=false).")
            return

        Services.get_instance().add("monitor", self)

        async def on_started(_, __):
            await self._init()

        self._notify.subscribe(Events.STARTED, on_started, f"{ResourceTracker.__name__}.init")

        async def on_shutdown(_, __):
            self.stop()

        self._notify.subscribe(Events.SHUTDOWN, on_shutdown, f"{ResourceTracker.__name__}.shutdown")

    async def _init(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._cpu_limit = cg.get_cpu_limit()
        self._effective_cpus = self._cpu_limit or float(psutil.cpu_count() or 1)

        db_dir = str(Path(self._config.config_path) / "stats")
        Path(db_dir).mkdir(parents=True, exist_ok=True)
        self._store = MonitorStore(str(Path(db_dir) / "stats.db"))
        self._store.open()
        LOG.debug("Monitor store opened at '%s'.", self._store._db_path)

        self._disk_paths = [self._config.download_path, self._config.temp_path, self._config.config_path]

        self._proc.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None)

        self.start()

        self._scheduler.add(
            timer="5 */1 * * *",
            func=functools.partial(self._prune_handler, self._config),
            id="monitor_prune",
        )
        LOG.info(
            "Resource monitoring started (interval=%ss, retention=%sh).",
            self._config.monitor_interval,
            self._config.monitor_retention_hours,
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="resource-tracker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._store:
            self._store.close()

    def _run(self) -> None:
        interval: int = max(1, self._config.monitor_interval)
        while not self._stop.wait(interval):
            try:
                self.sample()
            except Exception:
                pass

    def sample(self) -> ResourceSample | None:
        now: float = time.time()
        elapsed: None | float = None if self._last_ts is None else max(0.001, now - self._last_ts)

        proc_io = _process_io(self._proc)
        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()

        proc_read_bps: float | None = None
        proc_write_bps: float | None = None
        disk_read_bps: float | None = None
        disk_write_bps: float | None = None
        net_recv_bps: float | None = None
        net_sent_bps: float | None = None

        if elapsed and self._last_proc_io and proc_io["available"] and self._last_proc_io.get("available"):
            if (r := proc_io.get("read_bytes")) is not None and (
                lr := self._last_proc_io.get("read_bytes")
            ) is not None:
                proc_read_bps = max(0, (r - lr) / elapsed)
            if (w := proc_io.get("write_bytes")) is not None and (
                lw := self._last_proc_io.get("write_bytes")
            ) is not None:
                proc_write_bps = max(0, (w - lw) / elapsed)

        if elapsed and self._last_disk_io and disk_io:
            disk_read_bps = max(0, (disk_io.read_bytes - self._last_disk_io.read_bytes) / elapsed)
            disk_write_bps = max(0, (disk_io.write_bytes - self._last_disk_io.write_bytes) / elapsed)

        if elapsed and self._last_net_io and net_io:
            net_recv_bps = max(0, (net_io.bytes_recv - self._last_net_io.bytes_recv) / elapsed)
            net_sent_bps = max(0, (net_io.bytes_sent - self._last_net_io.bytes_sent) / elapsed)

        mem = self._proc.memory_info()
        rss_mb: float | None = _mb(mem.rss)
        vms_mb: float | None = _mb(mem.vms)

        try:
            full = self._proc.memory_full_info()
            uss = getattr(full, "uss", None)
            uss_mb = _mb(uss)
        except Exception:
            uss_mb = None

        vm = psutil.virtual_memory()
        mem_pct: float = vm.percent

        children: list[dict[str, Any]] = _children_stats(self._proc)

        app_stats = self._app_stats()
        active_jobs: int | bool = app_stats.get("active_jobs", 0)
        queued_jobs: int | bool = app_stats.get("queued_jobs", 0)
        is_paused: int | bool = app_stats.get("is_paused", False)

        sample = ResourceSample(
            ts=now,
            process_cpu_percent=round(self._proc.cpu_percent(interval=None) / self._effective_cpus, 2),
            system_cpu_percent=round(psutil.cpu_percent(interval=None), 2),
            cpu_limit=self._cpu_limit,
            effective_cpu_count=self._effective_cpus,
            rss_mb=rss_mb,
            uss_mb=uss_mb,
            vms_mb=vms_mb,
            memory_percent=mem_pct,
            cgroup_memory=cg.get_memory(),
            process_read_bps=proc_read_bps,
            process_write_bps=proc_write_bps,
            process_io_available=proc_io["available"],
            disk_read_bps=disk_read_bps,
            disk_write_bps=disk_write_bps,
            disk_usage=_disk_usage(self._disk_paths),
            network_recv_bps=net_recv_bps,
            network_sent_bps=net_sent_bps,
            threads=_safe(lambda: self._proc.num_threads()),
            open_files=_safe(lambda: len(self._proc.open_files())),
            connections=_safe(lambda: len(self._proc.net_connections(kind="inet"))),
            children=children,
            active_jobs=active_jobs,
            queued_jobs=queued_jobs,
            is_paused=bool(is_paused),
            uptime_seconds=round(now - self._started_at, 2),
        )

        self._last_ts = now
        self._last_proc_io = proc_io
        self._last_disk_io = disk_io
        self._last_net_io = net_io

        self._history.append(sample)

        if self._store:
            self._store.insert(sample.to_flat())

        self._notify_subscribers(sample)

        return sample

    def _app_stats(self) -> dict[str, int | bool]:
        try:
            result: dict[str, int | bool] = {"active_jobs": 0, "queued_jobs": 0, "is_paused": False}
            try:
                dq = Services.get_instance().get("queue")
                if hasattr(dq, "pool"):
                    result["active_jobs"] = len(dq.pool.get_active_downloads())
                    result["is_paused"] = dq.pool.is_paused()
                if hasattr(dq, "queue") and hasattr(dq.queue, "items"):
                    result["queued_jobs"] = len(dq.queue.items())
            except Exception:
                pass
            return result
        except Exception:
            return {"active_jobs": 0, "queued_jobs": 0, "is_paused": False}

    def latest(self) -> dict[str, Any]:
        h = list(self._history)
        if not h:
            return {}
        return h[-1].to_dict()

    def snapshot(self, range_seconds: float | None = None) -> list[dict[str, Any]]:
        h: list[ResourceSample] = list(self._history)
        cutoff: float | None = None
        if range_seconds is not None:
            cutoff = time.time() - range_seconds
            h = [s for s in h if s.ts >= cutoff]

        if self._store and len(h) <= 1:
            stored: list[dict[str, Any]] = self._store.query(limit=900, since=cutoff)
            if stored:
                return stored

        return [s.to_flat() for s in h]

    def subscribe(self) -> asyncio.Queue[ResourceSample | None]:
        q: asyncio.Queue[ResourceSample | None] = asyncio.Queue()
        with self._subscriber_lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[ResourceSample | None]) -> None:
        with self._subscriber_lock:
            self._subscribers.discard(q)

    def _notify_subscribers(self, sample: ResourceSample) -> None:
        loop = self._loop
        if loop is None:
            return
        with self._subscriber_lock:
            subs = set(self._subscribers)
        for q in subs:
            try:
                loop.call_soon_threadsafe(q.put_nowait, sample)
            except Exception:
                pass

    def _prune_handler(self, config: Config) -> None:
        if not self._store:
            return
        with self._prune_lock:
            removed: int = self._store.prune(config.monitor_retention_hours)
            if removed > 0:
                LOG.info("Pruned %d old monitor samples.", removed)
