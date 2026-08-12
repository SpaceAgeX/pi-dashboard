"""Source-address access control for the local dashboard."""

from __future__ import annotations

import ipaddress
from collections.abc import Sequence

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

ALLOWED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("192.168.1.0/24"),
    ipaddress.ip_network("100.64.0.0/10"),
)


def is_allowed_ip(value: str, networks: Sequence[ipaddress._BaseNetwork] = ALLOWED_NETWORKS) -> bool:
    """Return whether an IP belongs to an explicitly allowed network."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(address in network for network in networks if address.version == network.version)


class LocalNetworkMiddleware:
    """Reject HTTP peers outside the dashboard's private networks."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        peer_ip = client[0] if client else ""
        if not is_allowed_ip(peer_ip):
            response = JSONResponse({"error": "Access denied"}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
