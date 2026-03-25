"""
CartPath — FastAPI Application
================================
Main entry point for the CartPath routing API.

Usage:
    uvicorn routing.api.main:app --reload --port 8000
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .auth import router as auth_router
from .db import close_db, init_db
from .geocode import router as geocode_router
from .health import check_data_staleness, router as health_router
from .routes import load_speed_data, router as routes_router
from .saved import router as saved_router

logger = logging.getLogger("cartpath")

HEALTH_CHECK_INTERVAL = int(os.environ.get("CARTPATH_HEALTH_CHECK_INTERVAL", 6 * 3600))


async def periodic_health_check():
    """Background task: check data staleness every 6 hours and log warnings."""
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        try:
            result = check_data_staleness()
            if result["status"] == "stale":
                logger.warning(
                    "Data staleness alert: %s (age: %.1f days)",
                    result["message"],
                    result["age_days"],
                )
                # Optional webhook alert
                webhook_url = os.environ.get("CARTPATH_ALERT_WEBHOOK")
                if webhook_url:
                    import httpx
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(webhook_url, json={
                            "text": f"CartPath data staleness alert: {result['message']}",
                        })
            elif result["status"] == "missing":
                logger.warning("Health check: health.json not found — pipeline may not have run")
            else:
                logger.info("Health check: data is fresh (%.1f days old)", result.get("age_days", 0))
        except Exception:
            logger.exception("Periodic health check failed")


@asynccontextmanager
async def lifespan(app):
    # Load speed classification data once at startup
    load_speed_data()
    # Initialize user database
    await init_db()
    # Start periodic health check
    health_task = asyncio.create_task(periodic_health_check())
    # Run initial staleness check
    result = check_data_staleness()
    if result["status"] in ("stale", "missing"):
        logger.warning("Startup health check: %s", result.get("message", result["status"]))
    yield
    health_task.cancel()
    await close_db()


app = FastAPI(
    title="CartPath API",
    description="Golf cart navigation routing API — routes on roads ≤35 MPH",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — configurable via CARTPATH_CORS_ORIGINS env var (comma-separated)
_cors_env = os.environ.get("CARTPATH_CORS_ORIGINS", "")
cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
if not cors_origins:
    cors_origins = [
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(routes_router, prefix="/api")
app.include_router(geocode_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(saved_router, prefix="/api")

# Serve static data files (coverage boundary, etc.)
DATA_DIR = os.environ.get("CARTPATH_DATA_DIR", "pipeline/data")
if os.path.isdir(DATA_DIR):
    app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")


@app.get("/")
async def root():
    return {"service": "CartPath API", "version": "1.0.0", "docs": "/docs"}
