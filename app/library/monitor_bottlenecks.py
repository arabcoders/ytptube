from __future__ import annotations

from statistics import mean
from typing import Any


def _avg(values: list[float | None]) -> float | None:
    cleaned: list[float] = [v for v in values if v is not None]
    return round(mean(cleaned), 2) if cleaned else None


def _mbps(bps: float | None) -> float | None:
    return None if bps is None else round(bps / 1024 / 1024, 2)


def detect(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze recent samples and return bottleneck diagnosis."""
    if not history:
        return {"status": "unknown", "bottlenecks": []}

    window: list[dict[str, Any]] = history[-30:]

    cpu: float | None = _avg([s.get("process_cpu_percent") for s in window])
    sys_cpu: float | None = _avg([s.get("system_cpu_percent") for s in window])
    mem: float | None = _avg([s.get("memory_percent") for s in window])
    proc_read: float | None = _avg([s.get("process_read_bps") for s in window])
    proc_write: float | None = _avg([s.get("process_write_bps") for s in window])
    disk_read: float | None = _avg([s.get("disk_read_bps") for s in window])
    disk_write: float | None = _avg([s.get("disk_write_bps") for s in window])
    net_recv: float | None = _avg([s.get("network_recv_bps") for s in window])
    net_sent: float | None = _avg([s.get("network_sent_bps") for s in window])
    active: float | None = _avg([s.get("active_jobs") for s in window])

    bottlenecks: list[dict[str, Any]] = []

    if cpu is not None and cpu >= 80:
        level: str = "critical" if cpu >= 95 else "warning"
        details: str = f"Average app CPU usage was {cpu}% over the last {len(window)} samples."
        if active and active > 0:
            details += f" {int(active)} active downloads were running."
        bottlenecks.append({"type": "cpu", "level": level, "summary": "App CPU usage is high.", "details": details})

    if mem is not None and mem >= 80:
        level: str = "critical" if mem >= 90 else "warning"
        bottlenecks.append(
            {
                "type": "memory",
                "level": level,
                "summary": "Memory pressure is high.",
                "details": f"Average memory usage was {mem}% over the last {len(window)} samples.",
            }
        )

    if proc_write and proc_write > 20 * 1024 * 1024 and (cpu is None or cpu < 60):
        bottlenecks.append(
            {
                "type": "process_io_write",
                "level": "warning",
                "summary": "The app appears to be write I/O bound.",
                "details": f"App write rate averaged {_mbps(proc_write)} MB/s while CPU averaged {cpu}%.",
            }
        )

    if proc_read and proc_read > 20 * 1024 * 1024 and (cpu is None or cpu < 60):
        bottlenecks.append(
            {
                "type": "process_io_read",
                "level": "warning",
                "summary": "The app appears to be read I/O bound.",
                "details": f"App read rate averaged {_mbps(proc_read)} MB/s while CPU averaged {cpu}%.",
            }
        )

    if disk_write and disk_write > 50 * 1024 * 1024:
        bottlenecks.append(
            {
                "type": "disk_write",
                "level": "info",
                "summary": "System disk write throughput is high.",
                "details": f"Disk write rate averaged {_mbps(disk_write)} MB/s.",
            }
        )

    if disk_read and disk_read > 50 * 1024 * 1024:
        bottlenecks.append(
            {
                "type": "disk_read",
                "level": "info",
                "summary": "System disk read throughput is high.",
                "details": f"Disk read rate averaged {_mbps(disk_read)} MB/s.",
            }
        )

    if net_recv and net_recv > 50 * 1024 * 1024:
        bottlenecks.append(
            {
                "type": "network_download",
                "level": "info",
                "summary": "Network receive throughput is high.",
                "details": f"Network receive rate averaged {_mbps(net_recv)} MB/s.",
            }
        )

    if net_sent and net_sent > 50 * 1024 * 1024:
        bottlenecks.append(
            {
                "type": "network_upload",
                "level": "info",
                "summary": "Network send throughput is high.",
                "details": f"Network send rate averaged {_mbps(net_sent)} MB/s.",
            }
        )

    return {
        "status": "ok" if not bottlenecks else "attention",
        "window_samples": len(window),
        "averages": {
            "process_cpu_percent": cpu,
            "system_cpu_percent": sys_cpu,
            "memory_percent": mem,
            "process_read_mbps": _mbps(proc_read),
            "process_write_mbps": _mbps(proc_write),
            "disk_read_mbps": _mbps(disk_read),
            "disk_write_mbps": _mbps(disk_write),
            "network_recv_mbps": _mbps(net_recv),
            "network_sent_mbps": _mbps(net_sent),
            "active_jobs": active,
        },
        "bottlenecks": bottlenecks,
    }
