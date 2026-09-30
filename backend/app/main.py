"""API mínima de saúde do protótipo SIG-ES; não conecta a dados oficiais."""

from contextlib import asynccontextmanager
from dataclasses import asdict
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine
from app.file_monitor import make_monitor
from app.routes import router as domain_router

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Start the optional, explicitly configured local filesystem monitor."""
    monitor = make_monitor(os.getenv("SIGES_MONITOR_ROOT"))
    application.state.file_monitor = monitor
    try:
        yield
    finally:
        if monitor is not None:
            monitor.stop()


app = FastAPI(
    title="SIG-ES API",
    description="API local do SIG-ES. A instância não está homologada para produção.",
    version="0.1.0",
    lifespan=lifespan,
)

# Development-only frontend origin. Configure explicitly before deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(domain_router)


@app.get("/api/v1/monitor/status", tags=["monitoring"])
def monitor_status() -> dict[str, object]:
    """Return monitor counters without disclosing the monitored absolute path."""
    monitor = getattr(app.state, "file_monitor", None)
    if monitor is None:
        return {"enabled": False, "running": False}
    status = monitor.status()
    return {"enabled": True, **asdict(status)}


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
    database_engine: str
    integrations_enabled: bool


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Check the configured database without exposing connection details."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "database": "unavailable"},
        ) from exc
    return HealthResponse(
        status="ok",
        environment="local_unverified",
        database="connected",
        database_engine=engine.dialect.name,
        integrations_enabled=False,
    )
