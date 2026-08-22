from __future__ import annotations

from pathlib import Path
from typing import Any

CGROUP = Path("/sys/fs/cgroup")


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except Exception:
        return None


def _read_int(path: Path) -> int | None:
    value = _read(path)
    if not value or value == "max":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _mb(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value / 1024 / 1024, 2)


def _pct(value: float | None, total: float | None) -> float | None:
    if value is None or not total:
        return None
    return round((value / total) * 100, 2)


def get_memory() -> dict[str, Any]:
    """Docker / cgroup-aware memory (v1 and v2)."""
    current: int | None = _read_int(CGROUP / "memory.current")
    limit: int | None = _read_int(CGROUP / "memory.max")
    stat_path: Path = CGROUP / "memory.stat"

    if current is None:
        current = _read_int(CGROUP / "memory/memory.usage_in_bytes")
        limit = _read_int(CGROUP / "memory/memory.limit_in_bytes")
        stat_path = CGROUP / "memory/memory.stat"

    inactive = 0
    stat_text: str | None = _read(stat_path)
    if stat_text:
        for line in stat_text.splitlines():
            key, _, raw = line.partition(" ")
            if key in {"inactive_file", "total_inactive_file"}:
                try:
                    inactive = int(raw)
                except ValueError:
                    pass
                break

    working_set: int | None = max(0, current - inactive) if current is not None else None

    return {
        "available": current is not None,
        "usage_bytes": current,
        "usage_mb": _mb(current),
        "working_set_bytes": working_set,
        "working_set_mb": _mb(working_set),
        "limit_bytes": limit,
        "limit_mb": _mb(limit),
        "usage_percent": _pct(current, limit),
        "working_set_percent": _pct(working_set, limit),
    }


def get_cpu_limit() -> float | None:
    """
    Returns container CPU limit as number of CPUs.

    cgroup v2: cpu.max = "200000 100000" means 2 CPUs.
    cgroup v1: cpu.cfs_quota_us / cpu.cfs_period_us
    """
    cpu_max: str | None = _read(CGROUP / "cpu.max")
    if cpu_max:
        parts: list[str] = cpu_max.split()
        if len(parts) >= 2 and parts[0] != "max":
            quota = int(parts[0])
            period = int(parts[1])
            if period > 0:
                return quota / period

    quota: int | None = _read_int(CGROUP / "cpu/cpu.cfs_quota_us")
    period: int | None = _read_int(CGROUP / "cpu/cpu.cfs_period_us")
    if quota is not None and quota > 0 and period:
        return quota / period

    return None
