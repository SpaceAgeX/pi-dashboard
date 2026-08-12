"""Root filesystem and SD-card I/O monitoring."""

from __future__ import annotations

import time

import psutil

_previous: tuple[float, int, int] | None = None


def get_storage_status() -> dict[str, object]:
    global _previous
    usage = psutil.disk_usage("/")
    partition = next((item for item in psutil.disk_partitions(all=True) if item.mountpoint == "/"), None)
    io = psutil.disk_io_counters()
    now = time.monotonic()
    read_bytes = io.read_bytes if io else 0
    write_bytes = io.write_bytes if io else 0
    elapsed = now - _previous[0] if _previous else 0
    read_rate = max(0, (read_bytes - _previous[1]) / elapsed) if _previous and elapsed else 0
    write_rate = max(0, (write_bytes - _previous[2]) / elapsed) if _previous and elapsed else 0
    _previous = (now, read_bytes, write_bytes)
    return {
        "mountpoint": "/", "device": partition.device if partition else None,
        "filesystem": partition.fstype if partition else None,
        "total": usage.total, "used": usage.used, "free": usage.free, "percent": usage.percent,
        "read_bps": read_rate, "write_bps": write_rate,
        "read_bytes_since_boot": read_bytes, "write_bytes_since_boot": write_bytes,
        "warning": "Storage is critically low" if usage.percent >= 95 else ("Storage is running low" if usage.percent >= 90 else None),
    }
