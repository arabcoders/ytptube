from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.monitor import _disk_usage, _process_tree_stats
from app.library.monitor_bottlenecks import detect
from app.library.monitor_store import MonitorStore
from app.tests.helpers import make_test_temp_dir


MB = 1024 * 1024


@dataclass
class FakeTimes:
    user: float
    system: float = 0


@dataclass
class FakeMem:
    rss: int
    vms: int
    uss: int | None = None


@dataclass
class FakeIo:
    read_bytes: int
    write_bytes: int
    read_count: int = 0
    write_count: int = 0


@dataclass
class FakeThread:
    id: int
    name: str


class FakeProcess:
    def __init__(
        self,
        pid: int,
        *,
        created: float,
        cpu: float,
        rss: int,
        uss: int,
        vms: int,
        read: int,
        write: int,
        threads: int,
        files: int,
        conns: int,
        children: list | None = None,
        name: str = "python",
        status: str = "sleeping",
        cmdline: list[str] | None = None,
        thread_names: list[str] | None = None,
    ):
        self.pid = pid
        self.created = created
        self.cpu = cpu
        self.rss = rss
        self.uss = uss
        self.vms = vms
        self.read = read
        self.write = write
        self.thread_count = threads
        self.files = files
        self.conns = conns
        self._children = children or []
        self._name = name
        self._status = status
        self._cmdline = cmdline or [name]
        self._thread_names = thread_names or []

    def oneshot(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def create_time(self):
        return self.created

    def cpu_times(self):
        return FakeTimes(user=self.cpu)

    def memory_info(self):
        return FakeMem(rss=self.rss, vms=self.vms)

    def memory_full_info(self):
        return FakeMem(rss=self.rss, uss=self.uss, vms=self.vms)

    def io_counters(self):
        return FakeIo(read_bytes=self.read, write_bytes=self.write)

    def num_threads(self):
        return self.thread_count

    def threads(self):
        return [FakeThread(id=self.pid * 100 + idx, name=name) for idx, name in enumerate(self._thread_names, start=1)]

    def open_files(self):
        return [object()] * self.files

    def net_connections(self, *, kind: str):
        assert kind == "inet"
        return [object()] * self.conns

    def name(self):
        return self._name

    def status(self):
        return self._status

    def cmdline(self):
        return self._cmdline

    def children(self, *, recursive: bool = False):
        if not recursive:
            return list(self._children)

        result = []
        for child in self._children:
            result.append(child)
            result.extend(child.children(recursive=True))
        return result


def _key(proc: FakeProcess) -> tuple[int, float]:
    return proc.pid, proc.created


class TestMonitorStore:
    def setup_method(self):
        self.tmpdir = make_test_temp_dir("monitor-store")
        self.db_path = str(self.tmpdir / "test.db")

    def teardown_method(self):
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def test_open_creates_table(self):
        store = MonitorStore(self.db_path)
        store.open()
        assert store._conn is not None
        rows = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='resource_samples'"
        ).fetchall()
        assert len(rows) == 1
        store.close()

    def test_migration_version(self):
        store = MonitorStore(self.db_path)
        store.open()
        assert store._conn is not None
        version = store._conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        assert version == 1
        store.close()

    def test_insert_and_query(self):
        store = MonitorStore(self.db_path)
        store.open()

        sample = {
            "ts": 100.0,
            "process_cpu_percent": 25.0,
            "system_cpu_percent": 50.0,
            "rss_mb": 200.0,
            "uss_mb": 150.0,
            "memory_percent": 60.0,
            "process_read_bps": None,
            "process_write_bps": 1024000.0,
            "disk_read_bps": 512000.0,
            "disk_write_bps": 2048000.0,
            "network_recv_bps": None,
            "network_sent_bps": None,
            "threads": 10,
            "open_files": 50,
            "connections": 3,
            "active_jobs": 2,
            "queued_jobs": 5,
            "is_paused": 0,
            "children_count": 1,
        }
        store.insert(sample)

        results = store.query(limit=10)
        assert len(results) == 1
        assert results[0]["rss_mb"] == 200.0
        assert results[0]["process_write_bps"] == 1024000.0
        assert results[0]["active_jobs"] == 2
        store.close()

    def test_query_since(self):
        store = MonitorStore(self.db_path)
        store.open()

        for ts in (100.0, 200.0, 300.0, 400.0):
            store.insert({**self._min_sample(), "ts": ts})

        results = store.query(since=250.0)
        assert len(results) == 2
        assert results[0]["ts"] == 300.0
        store.close()

    def test_prune(self):
        store = MonitorStore(self.db_path)
        store.open()

        store.insert({**self._min_sample(), "ts": 10.0})
        store.insert({**self._min_sample(), "ts": 9999999999.0})

        removed = store.prune(retention_hours=1)
        assert removed == 1
        results = store.query(limit=10)
        assert len(results) == 1
        assert results[0]["ts"] == 9999999999.0
        store.close()

    @staticmethod
    def _min_sample() -> dict:
        return {
            "ts": 0,
            "process_cpu_percent": 0,
            "system_cpu_percent": 0,
            "rss_mb": 0,
            "uss_mb": 0,
            "memory_percent": 0,
            "process_read_bps": 0,
            "process_write_bps": 0,
            "disk_read_bps": 0,
            "disk_write_bps": 0,
            "network_recv_bps": 0,
            "network_sent_bps": 0,
            "threads": 0,
            "open_files": 0,
            "connections": 0,
            "active_jobs": 0,
            "queued_jobs": 0,
            "is_paused": 0,
            "children_count": 0,
        }


class TestResourceTracker:
    def setup_method(self):
        from app.library.monitor import ResourceTracker

        ResourceTracker._reset_singleton()

    def teardown_method(self):
        from app.library.monitor import ResourceTracker

        ResourceTracker._reset_singleton()

    def test_snapshot_reads_store(self):
        from app.library.monitor import ResourceTracker

        tracker = ResourceTracker.get_instance()
        tracker._store = MagicMock()
        tracker._store.query.return_value = [
            {"ts": 100.0, "process_cpu_percent": 10.0},
            {"ts": 130.0, "process_cpu_percent": 20.0},
        ]

        with patch("app.library.monitor.time.time", return_value=200.0):
            result = tracker.snapshot(range_seconds=120)

        tracker._store.query.assert_called_once_with(limit=900, since=80.0)
        assert len(result) == 2


class TestMonitorHelpers:
    def test_tree_totals(self):
        grandchild = FakeProcess(
            3,
            created=3,
            cpu=5,
            rss=300 * MB,
            uss=80 * MB,
            vms=3000 * MB,
            read=50,
            write=90,
            threads=2,
            files=0,
            conns=0,
            name="ffmpeg",
            status="running",
            cmdline=["ffmpeg", "-i", "input"],
            thread_names=["ffmpeg-main", "ffmpeg-io"],
        )
        child = FakeProcess(
            2,
            created=2,
            cpu=3,
            rss=200 * MB,
            uss=70 * MB,
            vms=2000 * MB,
            read=30,
            write=70,
            threads=3,
            files=1,
            conns=2,
            children=[grandchild],
            cmdline=["python", "worker.py"],
            thread_names=["worker-main", "status-updates"],
        )
        root = FakeProcess(
            1,
            created=1,
            cpu=3,
            rss=100 * MB,
            uss=50 * MB,
            vms=1000 * MB,
            read=300,
            write=150,
            threads=5,
            files=2,
            conns=1,
            children=[child],
        )

        stats = _process_tree_stats(
            root,  # type: ignore
            last_cpu={_key(root): 1, _key(child): 2, _key(grandchild): 3},
            last_io={
                _key(root): {"available": True, "read_bytes": 100, "write_bytes": 50},
                _key(child): {"available": True, "read_bytes": 10, "write_bytes": 20},
                _key(grandchild): {"available": True, "read_bytes": 40, "write_bytes": 60},
            },
            elapsed=2,
            effective_cpus=2,
            labels={2: "download-abc: Example title"},
        )

        assert stats.process_cpu_percent == 125
        assert stats.rss_mb == 600
        assert stats.uss_mb == 200
        assert stats.vms_mb == 6000
        assert stats.process_read_bps == 115
        assert stats.process_write_bps == 90
        assert stats.threads == 10
        assert stats.open_files == 3
        assert stats.connections == 3
        assert stats.children_count == 2
        assert stats.children[0]["pid"] == 3
        assert stats.children[0]["cpu_percent"] == 100
        assert stats.children[0]["display_name"] == "ffmpeg"
        assert stats.children[0]["cmdline"] == "ffmpeg -i input"
        assert stats.children[0]["thread_names"] == ["ffmpeg-main", "ffmpeg-io"]
        assert stats.children[1]["cpu_percent"] == 50
        assert stats.children[1]["display_name"] == "download-abc: Example title"
        assert stats.children[1]["cmdline"] == "python worker.py"
        assert stats.children[1]["thread_names"] == ["worker-main", "status-updates"]

    def test_disk_labels(self, tmp_path: Path) -> None:
        downloads = tmp_path / "downloads"
        temp = downloads / "tmp"
        config = tmp_path / "config"
        downloads.mkdir()
        temp.mkdir()
        config.mkdir()

        result = _disk_usage(
            [
                (str(downloads), "Downloads", "downloads"),
                (str(temp), "Temp", "temp"),
                (str(config), "Config", "config"),
            ]
        )

        assert result[str(downloads)]["label"] == "Downloads"
        assert result[str(temp)]["label"] == "Temp"
        assert result[str(temp)]["role"] == "temp"
        assert result[str(config)]["label"] == "Config"


class TestBottlenecks:
    def test_empty_history(self):
        result = detect([])
        assert result["status"] == "unknown"
        assert result["bottlenecks"] == []

    def test_no_bottlenecks(self):
        history = [_low_sample() for _ in range(30)]
        result = detect(history)
        assert result["status"] == "ok"
        assert result["bottlenecks"] == []

    def test_cpu_warning(self):
        history = [_cpu_sample(85) for _ in range(30)]
        result = detect(history)
        assert result["status"] == "attention"
        assert any(b["type"] == "cpu" and b["level"] == "warning" for b in result["bottlenecks"])

    def test_cpu_critical(self):
        history = [_cpu_sample(96) for _ in range(30)]
        result = detect(history)
        assert any(b["type"] == "cpu" and b["level"] == "critical" for b in result["bottlenecks"])

    def test_memory_warning(self):
        history = [_memory_sample(85) for _ in range(30)]
        result = detect(history)
        assert any(b["type"] == "memory" and b["level"] == "warning" for b in result["bottlenecks"])

    def test_write_bound(self):
        history = [_write_sample(30 * 1024 * 1024) for _ in range(30)]
        result = detect(history)
        assert any(b["type"] == "process_io_write" for b in result["bottlenecks"])

    def test_read_bound(self):
        history = [_read_sample(30 * 1024 * 1024) for _ in range(30)]
        result = detect(history)
        assert any(b["type"] == "process_io_read" for b in result["bottlenecks"])

    def test_network_bottleneck(self):
        history = [_network_recv_sample(80 * 1024 * 1024) for _ in range(30)]
        result = detect(history)
        assert any(b["type"] == "network_download" for b in result["bottlenecks"])


def _low_sample() -> dict:
    return {
        "ts": 0,
        "process_cpu_percent": 10,
        "system_cpu_percent": 20,
        "memory_percent": 30,
        "process_read_bps": 1024,
        "process_write_bps": 1024,
        "disk_read_bps": 1024,
        "disk_write_bps": 1024,
        "network_recv_bps": 1024,
        "network_sent_bps": 1024,
        "active_jobs": 0,
        "queued_jobs": 0,
    }


def _cpu_sample(cpu: float) -> dict:
    return {**_low_sample(), "process_cpu_percent": cpu}


def _memory_sample(mem: float) -> dict:
    return {**_low_sample(), "memory_percent": mem}


def _write_sample(bps: float) -> dict:
    return {**_low_sample(), "process_write_bps": bps}


def _read_sample(bps: float) -> dict:
    return {**_low_sample(), "process_read_bps": bps}


def _network_recv_sample(bps: float) -> dict:
    return {**_low_sample(), "network_recv_bps": bps}


class TestStatsRoutes:
    def setup_method(self):
        Config._reset_singleton()

    @pytest.mark.asyncio
    async def test_disabled_returns_403(self):
        from app.routes.api.stats import stats_latest, stats_bottlenecks, stats_history, stats_stream

        config = Config.get_instance()
        config.monitor_enabled = False
        encoder = Encoder()

        with patch("app.library.monitor.ResourceTracker.get_instance") as mock_get:
            mock_tracker = MagicMock()
            mock_get.return_value = mock_tracker
            assert 403 == (await stats_latest(encoder, config)).status
            assert 403 == (await stats_bottlenecks(encoder, config)).status
            assert 403 == (await stats_history(MagicMock(), encoder, config)).status
            assert 403 == (await stats_stream(MagicMock(), encoder, config)).status
