"""Read fixed systemd units and invoke fixed restart helpers."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

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


def _unit_state(unit: str) -> str:
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return "unavailable"
    try:
        result = subprocess.run(
            [systemctl, "show", unit, "--property=LoadState,ActiveState", "--value"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    values = result.stdout.strip().splitlines()
    if not values or "not-found" in values:
        return "unavailable"
    active = values[-1]
    if active == "active":
        return "running"
    if active == "failed":
        return "failed"
    return "stopped" if active in {"inactive", "activating", "deactivating"} else "unavailable"


def get_services() -> list[dict[str, object]]:
    return [
        {"id": service_id, "label": data["label"], "unit": data["unit"], "url": data["url"], "state": _unit_state(str(data["unit"]))}
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
