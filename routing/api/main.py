"""
CartPath — FastAPI Application
================================
Main entry point for the CartPath routing API.

Usage:
    uvicorn routing.api.main:app --reload --port 8000
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .auth import router as auth_router
from .db import close_db, init_db
from .geocode import router as geocode_router
from .health import router as health_router
from .routes import load_speed_data, router as routes_router
from .saved import router as saved_router


@asynccontextmanager
async def lifespan(app):
    # Load speed classification data once at startup
    load_speed_data()
    # Initialize user database
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="CartPath API",
    description="Golf cart navigation routing API — routes on roads ≤35 MPH",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the frontend dev server and production origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        "https://cartpath.app",
    ],
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
