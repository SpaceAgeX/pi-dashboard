"""PI-4 Control FastAPI application."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from dashboard.access import decide, list_devices, list_pending, rename, revoke, revoke_all
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dashboard.network import get_network_status
from dashboard.security import LocalNetworkMiddleware
from dashboard.services import get_services, restart_service
from dashboard.storage import get_storage_status
from dashboard.system import get_system_status, request_power_action

BASE_DIR = Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pi-dashboard")

app = FastAPI(title="PI-4 Control", docs_url=None, redoc_url=None)
app.add_middleware(LocalNetworkMiddleware)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

class DeviceName(BaseModel):
    name: str = Field(min_length=1, max_length=80)

def same_origin(value: str | None) -> None:
    if value != "same-origin": raise HTTPException(403, "Same-origin request required")


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "Invalid request", "detail": exc.errors()})


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled request error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/system")
async def system_status() -> dict[str, object]:
    return get_system_status()


@app.get("/api/network")
async def network_status() -> dict[str, object]:
    return get_network_status()


@app.get("/api/services")
async def services_status() -> dict[str, object]:
    return {"services": get_services()}


@app.get("/api/storage")
async def storage_status() -> dict[str, object]:
    return get_storage_status()

@app.get("/api/access")
async def access_status() -> dict[str, object]: return {"pending": list_pending(), "trusted": list_devices()}

@app.post("/api/access/pending/{request_id}/approve")
async def approve(request_id: str, marker: str | None = Header(None, alias="X-PI-Dashboard")): same_origin(marker); return {"success": decide(request_id,"approved")}

@app.post("/api/access/pending/{request_id}/deny")
async def deny(request_id: str, marker: str | None = Header(None, alias="X-PI-Dashboard")): same_origin(marker); return {"success": decide(request_id,"denied")}

@app.put("/api/access/devices/{device_id}")
async def rename_device(device_id: str, body: DeviceName, marker: str | None = Header(None, alias="X-PI-Dashboard")): same_origin(marker); return {"success": rename(device_id,body.name)}

@app.delete("/api/access/devices/{device_id}")
async def revoke_device(device_id: str, marker: str | None = Header(None, alias="X-PI-Dashboard")): same_origin(marker); return {"success": revoke(device_id)}

@app.delete("/api/access/devices")
async def revoke_every_device(confirm: str = "", marker: str | None = Header(None, alias="X-PI-Dashboard")):
    same_origin(marker)
    if confirm != "REVOKE ALL": raise HTTPException(400,"Confirmation required")
    return {"revoked": revoke_all()}


@app.post("/api/services/{service_id}/restart")
async def service_restart(service_id: str) -> JSONResponse:
    result, status_code = restart_service(service_id)
    return JSONResponse(status_code=status_code, content=result)


@app.post("/api/system/{action}")
async def power_action(action: str) -> JSONResponse:
    result, status_code = request_power_action(action)
    return JSONResponse(status_code=status_code, content=result)
