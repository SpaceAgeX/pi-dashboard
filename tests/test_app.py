from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx

from app import app
from dashboard.security import is_allowed_ip


def request(method: str, path: str, client_ip: str = "127.0.0.1") -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, client=(client_ip, 12345), raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path)
    return asyncio.run(run())


def test_allowed_networks() -> None:
    for address in ("127.0.0.1", "::1", "192.168.1.1", "192.168.1.254", "100.64.0.1", "100.127.255.254"):
        assert is_allowed_ip(address)
    for address in ("192.168.2.1", "100.128.0.1", "8.8.8.8", "invalid"):
        assert not is_allowed_ip(address)


def test_external_peer_is_rejected() -> None:
    response = request("GET", "/api/system", "8.8.8.8")
    assert response.status_code == 403
    assert response.json() == {"error": "Access denied"}


def test_status_routes_and_static_assets() -> None:
    for path in ("/api/system", "/api/network", "/api/services"):
        response = request("GET", path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
    assert request("GET", "/").status_code == 200
    assert request("GET", "/static/app.js").status_code == 200
    assert request("GET", "/static/style.css").status_code == 200


def test_only_predefined_operations_exist() -> None:
    assert request("POST", "/api/services/cloudflared/restart").status_code == 404
    assert request("POST", "/api/services/anything/restart").status_code == 404
    assert request("POST", "/api/system/anything").status_code == 404


def test_restart_uses_fixed_command() -> None:
    with patch("dashboard.services.Path.is_file", return_value=True), patch("dashboard.services.subprocess.run") as run:
        run.return_value.returncode = 0
        response = request("POST", "/api/services/aryehlab/restart")
    assert response.status_code == 200
    assert run.call_args.args[0] == ["/usr/bin/sudo", "-n", "/usr/local/sbin/pi-dashboard-restart-aryehlab"]

