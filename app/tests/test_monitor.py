from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.monitor_bottlenecks import detect
from app.library.monitor_store import MonitorStore
from app.tests.helpers import make_test_temp_dir


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
