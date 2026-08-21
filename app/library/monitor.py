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
from app.library.logging import get_logger
from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.Singleton import Singleton

from . import monitor_cgroup as cg
from .monitor_store import MonitorStore

if TYPE_CHECKING:
    from logging import Logger

    from aiohttp import web

LOG: Logger = get_logger()
ProcKey = tuple[int, float]


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
    children_count: int

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
            "children_count": self.children_count,
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


@dataclass(kw_only=True)
class _TreeStats:
    process_cpu_percent: float
    rss_mb: float | None
    uss_mb: float | None
    vms_mb: float | None
    process_read_bps: float | None
    process_write_bps: float | None
    process_io_available: bool
    threads: int | None
    open_files: int | None
    connections: int | None
    children: list[dict[str, Any]]
    children_count: int
    cpu: dict[ProcKey, float]
    io: dict[ProcKey, dict[str, Any]]


def _add(total: int | None, value: int | None) -> int | None:
    if value is None:
        return total
    if total is None:
        return value
    return total + value


def _safe_len(fn) -> int | None:
    value = _safe(fn)
    return len(value) if value is not None else None


def _proc_key(proc: psutil.Process) -> ProcKey:
    return proc.pid, float(_safe(lambda: proc.create_time()) or 0)


def _cpu_seconds(proc: psutil.Process) -> float | None:
    times = _safe(lambda: proc.cpu_times())
    if times is None:
        return None
    return float(getattr(times, "user", 0) + getattr(times, "system", 0))


def _short_cmdline(proc: psutil.Process, limit: int = 160) -> str | None:
    parts = _safe(lambda: proc.cmdline())
    if not parts:
        return None
    value = " ".join(str(part) for part in parts)
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1].rstrip()}..."


def _thread_name(pid: int, tid: int) -> str | None:
    path = Path("/proc") / str(pid) / "task" / str(tid) / "comm"
    value = _safe(lambda: path.read_text(encoding="utf-8").strip())
    return value or None


def _thread_names(proc: psutil.Process, limit: int = 5) -> list[str]:
    result: list[str] = []
    threads = _safe(lambda: proc.threads()) or []
    for thread in threads:
        tid = getattr(thread, "id", None)
        name = getattr(thread, "name", None)
        if name is None and tid is not None:
            name = _thread_name(proc.pid, int(tid))
        if not name or name in result:
            continue
        result.append(str(name))
        if len(result) >= limit:
            break
    return result


def _process_tree_stats(
    proc: psutil.Process,
    *,
    last_cpu: dict[ProcKey, float],
    last_io: dict[ProcKey, dict[str, Any]],
    elapsed: float | None,
    effective_cpus: float,
    labels: dict[int, str] | None = None,
    limit: int = 10,
) -> _TreeStats:
    try:
        child_procs = proc.children(recursive=True)
    except Exception:
        child_procs = []

    new_cpu: dict[ProcKey, float] = {}
    new_io: dict[ProcKey, dict[str, Any]] = {}
    children: list[dict[str, Any]] = []

    cpu_delta = 0.0
    read_delta = 0.0
    write_delta = 0.0
    read_seen = False
    write_seen = False
    io_available = False

    rss: int | None = None
    uss: int | None = None
    vms: int | None = None
    threads: int | None = None
    open_files: int | None = None
    connections: int | None = None

    for item in [proc, *child_procs]:
        is_child = item.pid != proc.pid
        try:
            with item.oneshot():
                key = _proc_key(item)
                item_cpu = _cpu_seconds(item)
                if item_cpu is not None:
                    new_cpu[key] = item_cpu

                item_cpu_percent = 0.0
                if elapsed and item_cpu is not None and (last := last_cpu.get(key)) is not None:
                    item_cpu_percent = max(0.0, ((item_cpu - last) / elapsed) * 100)
                    cpu_delta += max(0.0, item_cpu - last)

                mem = _safe(lambda item=item: item.memory_info())
                if mem is not None:
                    rss = _add(rss, getattr(mem, "rss", None))
                    vms = _add(vms, getattr(mem, "vms", None))

                full = _safe(lambda item=item: item.memory_full_info())
                if full is not None:
                    uss = _add(uss, getattr(full, "uss", None))

                item_io = _process_io(item)
                if item_io["available"]:
                    io_available = True
                    new_io[key] = item_io
                    prev_io = last_io.get(key)
                    if elapsed and prev_io and prev_io.get("available"):
                        if (r := item_io.get("read_bytes")) is not None and (
                            lr := prev_io.get("read_bytes")
                        ) is not None:
                            read_delta += max(0.0, r - lr)
                            read_seen = True
                        if (w := item_io.get("write_bytes")) is not None and (
                            lw := prev_io.get("write_bytes")
                        ) is not None:
                            write_delta += max(0.0, w - lw)
                            write_seen = True

                item_threads = _safe(lambda item=item: item.num_threads())
                threads = _add(threads, item_threads)
                open_files = _add(open_files, _safe_len(lambda item=item: item.open_files()))
                connections = _add(connections, _safe_len(lambda item=item: item.net_connections(kind="inet")))

                if is_child:
                    name = _safe(lambda item=item: item.name()) or "unknown"
                    children.append(
                        {
                            "pid": item.pid,
                            "name": name,
                            "display_name": (labels or {}).get(item.pid) or name,
                            "cmdline": _short_cmdline(item),
                            "status": _safe(lambda item=item: item.status()) or "unknown",
                            "cpu_percent": round(item_cpu_percent, 2),
                            "rss_mb": _mb(getattr(mem, "rss", None) if mem is not None else None),
                            "threads": item_threads,
                            "thread_names": _thread_names(item),
                        }
                    )
        except Exception:  # noqa: S112
            continue

    raw_cpu = ((cpu_delta / elapsed) * 100) if elapsed else 0.0
    children.sort(key=lambda item: item.get("rss_mb") or 0, reverse=True)

    return _TreeStats(
        process_cpu_percent=round(raw_cpu / effective_cpus, 2),
        rss_mb=_mb(rss),
        uss_mb=_mb(uss),
        vms_mb=_mb(vms),
        process_read_bps=(read_delta / elapsed) if elapsed and read_seen else None,
        process_write_bps=(write_delta / elapsed) if elapsed and write_seen else None,
        process_io_available=io_available,
        threads=threads,
        open_files=open_files,
        connections=connections,
        children=children[:limit],
        children_count=len(child_procs),
        cpu=new_cpu,
        io=new_io,
    )


def _disk_usage(paths: list[tuple[str, str, str]]) -> dict[str, Any]:
    result = {}
    for path, label, role in paths:
        try:
            usage = shutil.disk_usage(path)
            result[path] = {
                "label": label,
                "role": role,
                "total_gb": round(usage.total / 1024**3, 2),
                "used_gb": round(usage.used / 1024**3, 2),
                "free_gb": round(usage.free / 1024**3, 2),
                "used_percent": round((usage.used / usage.total) * 100, 2),
            }
        except Exception:  # noqa: S112
            continue
    return result


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
        self._disk_paths: list[tuple[str, str, str]] = []
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_ts: float | None = None
        self._last_proc_cpu: dict[ProcKey, float] = {}
        self._last_proc_io: dict[ProcKey, dict[str, Any]] = {}
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

        self._disk_paths = [
            (self._config.download_path, "Downloads", "downloads"),
            (self._config.temp_path, "Temp", "temp"),
            (self._config.config_path, "Config", "config"),
        ]

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
        elapsed: float | None = None if self._last_ts is None else max(0.001, now - self._last_ts)

        tree = _process_tree_stats(
            self._proc,
            last_cpu=self._last_proc_cpu,
            last_io=self._last_proc_io,
            elapsed=elapsed,
            effective_cpus=self._effective_cpus,
            labels=self._worker_labels(),
        )
        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()

        disk_read_bps: float | None = None
        disk_write_bps: float | None = None
        net_recv_bps: float | None = None
        net_sent_bps: float | None = None

        if elapsed and self._last_disk_io and disk_io:
            disk_read_bps = max(0, (disk_io.read_bytes - self._last_disk_io.read_bytes) / elapsed)
            disk_write_bps = max(0, (disk_io.write_bytes - self._last_disk_io.write_bytes) / elapsed)

        if elapsed and self._last_net_io and net_io:
            net_recv_bps = max(0, (net_io.bytes_recv - self._last_net_io.bytes_recv) / elapsed)
            net_sent_bps = max(0, (net_io.bytes_sent - self._last_net_io.bytes_sent) / elapsed)

        vm = psutil.virtual_memory()
        mem_pct: float = vm.percent

        app_stats = self._app_stats()
        active_jobs: int | bool = app_stats.get("active_jobs", 0)
        queued_jobs: int | bool = app_stats.get("queued_jobs", 0)
        is_paused: int | bool = app_stats.get("is_paused", False)

        sample = ResourceSample(
            ts=now,
            process_cpu_percent=tree.process_cpu_percent,
            system_cpu_percent=round(psutil.cpu_percent(interval=None), 2),
            cpu_limit=self._cpu_limit,
            effective_cpu_count=self._effective_cpus,
            rss_mb=tree.rss_mb,
            uss_mb=tree.uss_mb,
            vms_mb=tree.vms_mb,
            memory_percent=mem_pct,
            cgroup_memory=cg.get_memory(),
            process_read_bps=tree.process_read_bps,
            process_write_bps=tree.process_write_bps,
            process_io_available=tree.process_io_available,
            disk_read_bps=disk_read_bps,
            disk_write_bps=disk_write_bps,
            disk_usage=_disk_usage(self._disk_paths),
            network_recv_bps=net_recv_bps,
            network_sent_bps=net_sent_bps,
            threads=tree.threads,
            open_files=tree.open_files,
            connections=tree.connections,
            children=tree.children,
            children_count=tree.children_count,
            active_jobs=active_jobs,
            queued_jobs=queued_jobs,
            is_paused=bool(is_paused),
            uptime_seconds=round(now - self._started_at, 2),
        )

        self._last_ts = now
        self._last_proc_cpu = tree.cpu
        self._last_proc_io = tree.io
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

    def _worker_labels(self) -> dict[int, str]:
        labels: dict[int, str] = {}
        try:
            dq = Services.get_instance().get("queue")
            if not hasattr(dq, "pool"):
                return labels

            for download in dq.pool.get_active_downloads().values():
                manager = getattr(download, "_process_manager", None)
                proc = getattr(manager, "proc", None)
                pid = getattr(proc, "pid", None)
                if not pid:
                    continue

                name = getattr(proc, "name", None) or f"worker-{pid}"
                title = getattr(getattr(download, "info", None), "title", "")
                labels[int(pid)] = f"{name}: {title}" if title else str(name)
        except Exception:
            return labels
        return labels

    def latest(self) -> dict[str, Any]:
        h = list(self._history)
        if not h:
            return {}
        return h[-1].to_dict()

    def snapshot(self, range_seconds: float | None = None) -> list[dict[str, Any]]:
        cutoff: float | None = None
        if range_seconds is not None:
            cutoff = time.time() - range_seconds

        if self._store:
            stored: list[dict[str, Any]] = self._store.query(limit=900, since=cutoff)
            if stored:
                return stored

        h: list[ResourceSample] = list(self._history)
        if cutoff is not None:
            h = [s for s in h if s.ts >= cutoff]

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
