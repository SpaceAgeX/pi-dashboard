"""Read fixed systemd units and invoke fixed restart helpers."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)
SERVICES = {
    "aryehlab": {"label": "AryehLab", "unit": "aryehlab.service", "url": "http://localhost:8001"},
    "printer-camera": {"label": "Printer Camera", "unit": "printer-camera.service", "url": "http://localhost:8000"},
    "cloudflared": {"label": "Cloudflare Tunnel", "unit": "cloudflared.service", "url": None},
    "tailscaled": {"label": "Tailscale", "unit": "tailscaled.service", "url": None},
}
RESTART_HELPERS = {
    "aryehlab": "/usr/local/sbin/pi-dashboard-restart-aryehlab",
    "printer-camera": "/usr/local/sbin/pi-dashboard-restart-camera",
}
VALID_STATES = {"running", "stopped", "failed", "unavailable"}


def _unit_details(unit: str) -> dict[str, object]:
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return {"state": "unavailable", "pid": None, "started_at": None, "restart_count": None, "memory_bytes": None, "cpu_percent": None}
    try:
        result = subprocess.run(
            [systemctl, "show", unit, "--property=LoadState,ActiveState,MainPID,ActiveEnterTimestampMonotonic,NRestarts", "--value"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"state": "unavailable", "pid": None, "started_at": None, "restart_count": None, "memory_bytes": None, "cpu_percent": None}
    values = result.stdout.strip().splitlines()
    if not values or "not-found" in values:
        return {"state": "unavailable", "pid": None, "started_at": None, "restart_count": None, "memory_bytes": None, "cpu_percent": None}
    load = values[0] if len(values) > 0 else "not-found"
    active = values[1] if len(values) > 1 else "unknown"
    pid = int(values[2]) if len(values) > 2 and values[2].isdigit() and values[2] != "0" else None
    started_at = int(psutil.boot_time() + int(values[3]) / 1_000_000) if len(values) > 3 and values[3].isdigit() else None
    restart_count = int(values[4]) if len(values) > 4 and values[4].isdigit() else 0
    if active == "active":
        state = "running"
    elif active == "failed":
        state = "failed"
    else:
        state = "stopped" if load != "not-found" and active in {"inactive", "activating", "deactivating"} else "unavailable"
    memory_bytes = None
    cpu_percent = None
    if pid:
        try:
            process = psutil.Process(pid)
            memory_bytes = process.memory_info().rss
            cpu_percent = process.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return {"state": state, "pid": pid, "started_at": started_at, "restart_count": restart_count, "memory_bytes": memory_bytes, "cpu_percent": cpu_percent}


def get_services() -> list[dict[str, object]]:
    return [
        {"id": service_id, "label": data["label"], "unit": data["unit"], "url": data["url"], **_unit_details(str(data["unit"]))}
        for service_id, data in SERVICES.items()
    ]


def restart_service(service_id: str) -> tuple[dict[str, object], int]:
    helper = RESTART_HELPERS.get(service_id)
    if helper is None:
        return {"error": "Service restart is not allowed"}, 404
    if not Path(helper).is_file():
        return {"error": "Restart helper is not installed"}, 503
    try:
        result = subprocess.run(
            ["/usr/bin/sudo", "-n", helper], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Restart helper failed for %s", service_id)
        return {"error": "Unable to restart service"}, 500
    if result.returncode != 0:
        logger.error("Restart helper returned %s for %s", result.returncode, service_id)
        return {"error": "Service restart failed"}, 500
    return {"ok": True, "service": service_id}, 200
