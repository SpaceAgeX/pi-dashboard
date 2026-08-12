"""Network interface and Tailscale monitoring."""

from __future__ import annotations

import ipaddress
import shutil
import subprocess

import psutil


def _interface(kind: str) -> dict[str, object]:
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    prefixes = ("eth", "en") if kind == "ethernet" else ("wlan", "wl")
    name = next((n for n in addrs if n.lower().startswith(prefixes)), None)
    if name is None:
        return {"available": False, "connected": False, "interface": None, "ipv4": None}
    ipv4 = next((a.address for a in addrs[name] if a.family.name == "AF_INET"), None)
    return {
        "available": True,
        "connected": bool(stats.get(name) and stats[name].isup),
        "interface": name,
        "ipv4": ipv4,
    }


def _tailscale() -> dict[str, object]:
    executable = shutil.which("tailscale")
    if not executable:
        return {"available": False, "connected": False, "ipv4": None}
    try:
        result = subprocess.run(
            [executable, "ip", "-4"], capture_output=True, text=True, timeout=2, check=False
        )
        candidate = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        valid = bool(candidate and ipaddress.ip_address(candidate).version == 4)
        return {"available": True, "connected": result.returncode == 0 and valid, "ipv4": candidate if valid else None}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"available": True, "connected": False, "ipv4": None}


def get_network_status() -> dict[str, object]:
    return {"ethernet": _interface("ethernet"), "wifi": _interface("wifi"), "tailscale": _tailscale()}

