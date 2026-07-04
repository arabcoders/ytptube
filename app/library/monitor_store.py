from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

CREATE_TABLE: str = """
CREATE TABLE IF NOT EXISTS resource_samples (
    ts REAL PRIMARY KEY,
    process_cpu_percent REAL,
    system_cpu_percent REAL,
    rss_mb REAL,
    uss_mb REAL,
    memory_percent REAL,
    process_read_bps REAL,
    process_write_bps REAL,
    disk_read_bps REAL,
    disk_write_bps REAL,
    network_recv_bps REAL,
    network_sent_bps REAL,
    threads INTEGER,
    open_files INTEGER,
    connections INTEGER,
    active_jobs INTEGER,
    queued_jobs INTEGER,
    is_paused INTEGER,
    children_count INTEGER
);
"""

MIGRATIONS: list[tuple[int, list[str]]] = [
    (1, [CREATE_TABLE]),
]

PRUNE_SQL: str = "DELETE FROM resource_samples WHERE ts < ?"
INSERT_SQL: str = """
INSERT INTO resource_samples (
    ts, process_cpu_percent, system_cpu_percent,
    rss_mb, uss_mb, memory_percent,
    process_read_bps, process_write_bps,
    disk_read_bps, disk_write_bps,
    network_recv_bps, network_sent_bps,
    threads, open_files, connections,
    active_jobs, queued_jobs, is_paused, children_count
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

COLUMNS: list[str] = [
    "ts",
    "process_cpu_percent",
    "system_cpu_percent",
    "rss_mb",
    "uss_mb",
    "memory_percent",
    "process_read_bps",
    "process_write_bps",
    "disk_read_bps",
    "disk_write_bps",
    "network_recv_bps",
    "network_sent_bps",
    "threads",
    "open_files",
    "connections",
    "active_jobs",
    "queued_jobs",
    "is_paused",
    "children_count",
]


def _row_to_dict(row: tuple) -> dict[str, Any]:
    return dict(zip(COLUMNS, row, strict=False))


class MonitorStore:
    """SQLite time-series store for resource samples."""

    def __init__(self, db_path: str):
        self._db_path: str = db_path
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

        self._conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        self._conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (0)")
        self._conn.commit()
        current: int = self._conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 0

        for version, stmts in MIGRATIONS:
            if version <= current:
                continue
            try:
                self._conn.execute("BEGIN")
                for stmt in stmts:
                    self._conn.execute(stmt)
                self._conn.execute("UPDATE schema_version SET version = ?", (version,))
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def insert(self, sample: dict[str, Any]) -> None:
        if not self._conn:
            return
        values = tuple(sample.get(col) for col in COLUMNS)
        self._conn.execute(INSERT_SQL, values)
        self._conn.commit()

    def query(self, limit: int = 900, since: float | None = None) -> list[dict[str, Any]]:
        if not self._conn:
            return []
        if since is not None:
            rows = self._conn.execute(
                "SELECT * FROM resource_samples WHERE ts >= ? ORDER BY ts ASC LIMIT ?",
                (since, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM resource_samples ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
            rows.reverse()
        return [_row_to_dict(r) for r in rows]

    def prune(self, retention_hours: float) -> int:
        if not self._conn:
            return 0
        cutoff = time.time() - (retention_hours * 3600)
        cursor = self._conn.execute(PRUNE_SQL, (cutoff,))
        self._conn.commit()
        return cursor.rowcount
