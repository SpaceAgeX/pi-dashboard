"""PI-4 Control FastAPI application."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dashboard.network import get_network_status
from dashboard.security import LocalNetworkMiddleware
from dashboard.services import get_services, restart_service
from dashboard.system import get_system_status, request_power_action

BASE_DIR = Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pi-dashboard")

app = FastAPI(title="PI-4 Control", docs_url=None, redoc_url=None)
app.add_middleware(LocalNetworkMiddleware)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


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


@app.post("/api/services/{service_id}/restart")
async def service_restart(service_id: str) -> JSONResponse:
    result, status_code = restart_service(service_id)
    return JSONResponse(status_code=status_code, content=result)


@app.post("/api/system/{action}")
async def power_action(action: str) -> JSONResponse:
    result, status_code = request_power_action(action)
    return JSONResponse(status_code=status_code, content=result)

