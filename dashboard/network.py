"""Network interface and Tailscale monitoring."""

from __future__ import annotations

import ipaddress
import json
import shutil
import subprocess
import time
from pathlib import Path

import psutil

_previous_io: tuple[float, dict[str, psutil._common.snetio]] | None = None


def _interface(kind: str) -> dict[str, object]:
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    prefixes = ("eth", "en") if kind == "ethernet" else ("wlan", "wl")
    name = next((n for n in addrs if n.lower().startswith(prefixes)), None)
    if name is None:
        return {"available": False, "connected": False, "interface": None, "ipv4": None}
    ipv4 = next((a.address for a in addrs[name] if a.family.name == "AF_INET"), None)
    mac = next((a.address for a in addrs[name] if a.family.name in {"AF_LINK", "AF_PACKET"}), None)
    stat = stats.get(name)
    return {
        "available": True,
        "connected": bool(stat and stat.isup),
        "interface": name,
        "ipv4": ipv4,
        "mac": mac,
        "speed_mbps": stat.speed if stat and stat.speed > 0 else None,
        "wifi_signal_dbm": _wifi_signal(name) if kind == "wifi" else None,
    }


def _tailscale() -> dict[str, object]:
    executable = shutil.which("tailscale")
    if not executable:
        return {"available": False, "connected": False, "ipv4": None}
    try:
        result = subprocess.run([executable, "status", "--json"], capture_output=True, text=True, timeout=3, check=False)
        data = json.loads(result.stdout) if result.returncode == 0 else {}
        addresses = data.get("TailscaleIPs") or data.get("Self", {}).get("TailscaleIPs", [])
        ipv4 = next((value for value in addresses if ipaddress.ip_address(value).version == 4), None)
        peers = list((data.get("Peer") or {}).values())
        exit_node = bool(data.get("Self", {}).get("ExitNodeOption"))
        return {
            "available": True, "connected": data.get("BackendState") == "Running", "ipv4": ipv4,
            "online_peers": sum(1 for peer in peers if peer.get("Online")), "exit_node_advertising": exit_node,
            "peers": [{"name": (peer.get("HostName") or peer.get("DNSName") or "Device").rstrip("."), "online": bool(peer.get("Online"))} for peer in peers[:8]],
        }
    except (OSError, subprocess.TimeoutExpired, ValueError, json.JSONDecodeError):
        return {"available": True, "connected": False, "ipv4": None}


def _wifi_signal(name: str) -> float | None:
    try:
        for line in Path("/proc/net/wireless").read_text(encoding="ascii").splitlines()[2:]:
            if line.lstrip().startswith(f"{name}:"):
                return float(line.split()[3].rstrip("."))
    except (OSError, ValueError, IndexError):
        pass
    return None


def _gateway() -> str | None:
    try:
        for line in Path("/proc/net/route").read_text(encoding="ascii").splitlines()[1:]:
            fields = line.split()
            if fields[1] == "00000000":
                raw = bytes.fromhex(fields[2])
                return str(ipaddress.ip_address(raw[::-1]))
    except (OSError, ValueError, IndexError):
        pass
    return None


def _dns_servers() -> list[str]:
    try:
        return [line.split()[1] for line in Path("/etc/resolv.conf").read_text().splitlines() if line.startswith("nameserver ")][:3]
    except (OSError, IndexError):
        return []


def _traffic() -> dict[str, object]:
    global _previous_io
    now = time.monotonic()
    current = psutil.net_io_counters(pernic=True)
    rates: dict[str, dict[str, float | int]] = {}
    elapsed = now - _previous_io[0] if _previous_io else 0
    for name, counters in current.items():
        previous = _previous_io[1].get(name) if _previous_io else None
        rates[name] = {
            "bytes_sent": counters.bytes_sent, "bytes_received": counters.bytes_recv,
            "upload_bps": max(0, (counters.bytes_sent - previous.bytes_sent) / elapsed) if previous and elapsed else 0,
            "download_bps": max(0, (counters.bytes_recv - previous.bytes_recv) / elapsed) if previous and elapsed else 0,
        }
    _previous_io = (now, current)
    return {"interfaces": rates}


def get_network_status() -> dict[str, object]:
    return {
        "ethernet": _interface("ethernet"), "wifi": _interface("wifi"), "tailscale": _tailscale(),
        "traffic": _traffic(), "default_gateway": _gateway(), "dns_servers": _dns_servers(),
    }
