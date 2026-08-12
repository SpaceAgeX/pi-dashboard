"""Host metrics and fixed power operations."""

from __future__ import annotations

import logging
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


def _temperature() -> float | None:
    try:
        return round(float(THERMAL_SENSOR.read_text(encoding="ascii").strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def get_system_status() -> dict[str, object]:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "hostname": socket.gethostname(),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory": {"used": memory.used, "total": memory.total, "percent": memory.percent},
        "temperature_c": _temperature(),
        "disk": {"used": disk.used, "total": disk.total, "free": disk.free, "percent": disk.percent},
        "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
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
