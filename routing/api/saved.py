"""
CartPath — Saved Routes Endpoints
====================================
Server-side saved routes CRUD for authenticated users.
Supports cross-device sync and localStorage migration.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .db import get_db
from .middleware import get_current_user

router = APIRouter(prefix="/saved-routes", tags=["saved-routes"])

MAX_SAVED_ROUTES = {"free": 10, "premium": 50}


class CoordinatesInput(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class SaveRouteRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    route_id: str | None = None
    summary: str | None = None
    distance_miles: float | None = None
    duration_minutes: float | None = None
    start: CoordinatesInput
    end: CoordinatesInput


class ImportRouteItem(BaseModel):
    label: str
    route_id: str | None = None
    summary: str | None = None
    distance_miles: float | None = None
    duration_minutes: float | None = None
    start: CoordinatesInput
    end: CoordinatesInput
    saved_at: str | None = None


class ImportRoutesRequest(BaseModel):
    routes: list[ImportRouteItem] = Field(..., max_length=50)


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "label": row["label"],
        "route_id": row["route_id"],
        "summary": row["summary"],
        "distance_miles": row["distance_miles"],
        "duration_minutes": row["duration_minutes"],
        "start": {"lat": row["start_lat"], "lon": row["start_lon"]},
        "end": {"lat": row["end_lat"], "lon": row["end_lon"]},
        "saved_at": row["saved_at"],
    }


@router.get("")
async def list_saved_routes(user: dict = Depends(get_current_user)):
    """List saved routes for the current user."""
    db = await get_db()
    limit = MAX_SAVED_ROUTES.get(user["tier"], 10)
    cursor = await db.execute(
        "SELECT * FROM saved_routes WHERE user_id = ? ORDER BY saved_at DESC LIMIT ?",
        (user["user_id"], limit),
    )
    rows = await cursor.fetchall()
    return {"routes": [_row_to_dict(r) for r in rows]}


@router.post("")
async def save_route(req: SaveRouteRequest, user: dict = Depends(get_current_user)):
    """Save a new route."""
    db = await get_db()

    # Check limit
    limit = MAX_SAVED_ROUTES.get(user["tier"], 10)
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM saved_routes WHERE user_id = ?",
        (user["user_id"],),
    )
    row = await cursor.fetchone()
    if row["cnt"] >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Route limit reached ({limit}). Delete a route to save a new one.",
        )

    route_db_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO saved_routes
           (id, user_id, label, route_id, summary, distance_miles, duration_minutes,
            start_lat, start_lon, end_lat, end_lon)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            route_db_id,
            user["user_id"],
            req.label.strip(),
            req.route_id,
            req.summary,
            req.distance_miles,
            req.duration_minutes,
            req.start.lat,
            req.start.lon,
            req.end.lat,
            req.end.lon,
        ),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM saved_routes WHERE id = ?", (route_db_id,))
    created = await cursor.fetchone()
    return _row_to_dict(created)


@router.delete("/{route_id}")
async def delete_saved_route(route_id: str, user: dict = Depends(get_current_user)):
    """Delete a saved route owned by the current user."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM saved_routes WHERE id = ? AND user_id = ?",
        (route_id, user["user_id"]),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Route not found")

    await db.execute("DELETE FROM saved_routes WHERE id = ?", (route_id,))
    await db.commit()
    return {"ok": True}


@router.post("/import")
async def import_routes(req: ImportRoutesRequest, user: dict = Depends(get_current_user)):
    """Bulk import routes from localStorage. Skips duplicates by label."""
    db = await get_db()

    # Get existing labels for this user
    cursor = await db.execute(
        "SELECT label FROM saved_routes WHERE user_id = ?",
        (user["user_id"],),
    )
    existing_labels = {row["label"] for row in await cursor.fetchall()}

    # Check remaining capacity
    limit = MAX_SAVED_ROUTES.get(user["tier"], 10)
    capacity = limit - len(existing_labels)

    imported = 0
    skipped = 0

    for route in req.routes:
        if route.label in existing_labels:
            skipped += 1
            continue
        if imported >= capacity:
            skipped += 1
            continue

        route_db_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO saved_routes
               (id, user_id, label, route_id, summary, distance_miles, duration_minutes,
                start_lat, start_lon, end_lat, end_lon, saved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')))""",
            (
                route_db_id,
                user["user_id"],
                route.label,
                route.route_id,
                route.summary,
                route.distance_miles,
                route.duration_minutes,
                route.start.lat,
                route.start.lon,
                route.end.lat,
                route.end.lon,
                route.saved_at,
            ),
        )
        existing_labels.add(route.label)
        imported += 1

    await db.commit()
    return {"imported": imported, "skipped": skipped}
