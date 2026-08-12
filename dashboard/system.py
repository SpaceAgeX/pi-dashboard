"""Host metrics and fixed power operations."""

from __future__ import annotations

import logging
import os
import platform
import socket
import subprocess
import time
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)
THERMAL_SENSOR = Path("/sys/class/thermal/thermal_zone0/temp")
POWER_HELPERS = {
    "reboot": "/usr/local/sbin/pi-dashboard-reboot",
    "shutdown": "/usr/local/sbin/pi-dashboard-shutdown",
}
_process_samples: dict[int, tuple[float, float]] = {}


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _os_name() -> str:
    data = _read_text("/etc/os-release") or ""
    for line in data.splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip('"')
    return platform.system()


def _throttling() -> dict[str, object]:
    """Read Pi firmware throttle flags with one fixed, bounded command."""
    try:
        result = subprocess.run(
            ["/usr/bin/vcgencmd", "get_throttled"], capture_output=True, text=True,
            timeout=2, check=False,
        )
        value = int(result.stdout.strip().split("=", 1)[1], 16)
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        return {"available": False, "throttled": False, "undervoltage": False, "raw": None}
    return {
        "available": True,
        "throttled": bool(value & ((1 << 2) | (1 << 18))),
        "undervoltage": bool(value & ((1 << 0) | (1 << 16))),
        "raw": f"0x{value:x}",
    }


def _top_processes(limit: int = 5) -> list[dict[str, object]]:
    global _process_samples
    processes: list[dict[str, object]] = []
    next_samples: dict[int, tuple[float, float]] = {}
    now = time.monotonic()
    for process in psutil.process_iter(["pid", "name", "cpu_times", "memory_info"]):
        try:
            info = process.info
            memory = info.get("memory_info")
            cpu_times = info.get("cpu_times")
            total_cpu = cpu_times.user + cpu_times.system if cpu_times else 0
            previous = _process_samples.get(info["pid"])
            cpu_percent = max(0, (total_cpu - previous[1]) / (now - previous[0]) * 100) if previous and now > previous[0] else 0
            next_samples[info["pid"]] = (now, total_cpu)
            processes.append({
                "pid": info["pid"], "name": info.get("name") or "unknown",
                "cpu_percent": round(cpu_percent, 1),
                "memory_bytes": memory.rss if memory else 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _process_samples = next_samples
    return sorted(processes, key=lambda item: (item["cpu_percent"], item["memory_bytes"]), reverse=True)[:limit]


def _temperature() -> float | None:
    try:
        return round(float(THERMAL_SENSOR.read_text(encoding="ascii").strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def get_system_status() -> dict[str, object]:
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")
    boot_time = psutil.boot_time()
    temperature = _temperature()
    throttle = _throttling()
    cpu_percent = psutil.cpu_percent(interval=None, percpu=True)
    frequency = psutil.cpu_freq()
    warnings: list[str] = []
    if temperature is not None and temperature >= 75:
        warnings.append("CPU temperature is high")
    if disk.percent >= 90:
        warnings.append("Storage is running low")
    if memory.percent >= 90:
        warnings.append("Memory pressure is high")
    if throttle["throttled"]:
        warnings.append("CPU throttling detected")
    if throttle["undervoltage"]:
        warnings.append("Undervoltage detected")
    return {
        "hostname": socket.gethostname(),
        "model": _read_text("/proc/device-tree/model") or "Unknown hardware",
        "os": _os_name(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu_percent": round(sum(cpu_percent) / len(cpu_percent), 1) if cpu_percent else 0,
        "cpu_per_core": cpu_percent,
        "cpu_frequency_mhz": round(frequency.current, 0) if frequency else None,
        "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        "memory": {
            "used": memory.used, "free": memory.free, "cached": getattr(memory, "cached", 0),
            "available": memory.available, "total": memory.total, "percent": memory.percent,
        },
        "swap": {"used": swap.used, "total": swap.total, "percent": swap.percent},
        "temperature_c": temperature,
        "throttling": throttle,
        "disk": {"used": disk.used, "total": disk.total, "free": disk.free, "percent": disk.percent},
        "process_count": len(psutil.pids()),
        "uptime_seconds": max(0, int(time.time() - boot_time)),
        "boot_time": int(boot_time),
        "health": {"status": "warning" if warnings else "good", "warnings": warnings},
        "top_processes": _top_processes(),
    }


def request_power_action(action: str) -> tuple[dict[str, object], int]:
    helper = POWER_HELPERS.get(action)
    if helper is None:
        return {"error": "Unknown power action"}, 404
    if not Path(helper).is_file():
        return {"error": f"{action.capitalize()} helper is not installed"}, 503
    try:
        subprocess.Popen(
            ["/usr/bin/sudo", "-n", helper],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        logger.exception("Could not start %s helper", action)
        return {"error": f"Unable to request {action}"}, 500
    return {"ok": True, "action": action}, 202
