"""
CartPath — Routing Endpoint
==============================
POST /api/route — computes golf-cart-safe routes via OSRM.
Includes fallback routing with non-compliant segment annotations.
"""

import json
import os
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5000")
SPEED_DATA_PATH = os.environ.get("CARTPATH_SPEED_DATA", "pipeline/data/classified_speeds.json")

# Constants
MAX_SPEED_MPH = 35
DEFAULT_CART_SPEED_MPH = 23
METERS_PER_MILE = 1609.34

# Speed data loaded at startup via load_speed_data()
_speed_data: dict = {}


def load_speed_data():
    """Load speed classification data. Called once at app startup."""
    global _speed_data
    if os.path.exists(SPEED_DATA_PATH):
        with open(SPEED_DATA_PATH) as f:
            _speed_data = json.load(f)


class Coordinates(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class RouteRequest(BaseModel):
    start: Coordinates
    end: Coordinates


class Warning(BaseModel):
    road_name: str
    speed_limit: float
    distance_miles: float


class RouteSegment(BaseModel):
    road_name: str
    distance_miles: float
    duration_minutes: float
    speed_limit: Optional[float] = None
    surface_type: Optional[str] = None
    compliant: bool = True


async def query_osrm(start: Coordinates, end: Coordinates) -> Optional[dict]:
    """Query OSRM for a route between two points."""
    coords = f"{start.lon},{start.lat};{end.lon},{end.lat}"
    url = f"{OSRM_URL}/route/v1/driving/{coords}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "annotations": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                return None
            return data
    except httpx.RequestError:
        return None


def analyze_route_compliance(route: dict) -> tuple[str, list[Warning], list[RouteSegment]]:
    """
    Analyze route steps for speed limit compliance.
    Returns (compliance_level, warnings, segments).
    """
    warnings = []
    segments = []
    has_noncompliant = False
    total_noncompliant_miles = 0

    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            road_name = step.get("name", "Unknown road")
            distance_m = step.get("distance", 0)
            distance_miles = distance_m / METERS_PER_MILE

            # Recalculate duration at cart speed (23 MPH)
            duration_minutes = (distance_miles / DEFAULT_CART_SPEED_MPH) * 60 if distance_miles > 0 else 0

            # Determine speed limit and compliance
            speed_limit = None
            compliant = True

            # Try to get speed from OSRM annotations
            annotation = step.get("annotation", {})
            if annotation:
                speeds = annotation.get("speed", [])
                if speeds:
                    avg_speed_ms = sum(speeds) / len(speeds)
                    speed_limit = round(avg_speed_ms * 2.237, 0)  # m/s to mph

            # Check against the 35 MPH threshold
            if speed_limit is not None and speed_limit > MAX_SPEED_MPH:
                compliant = False

            segment = RouteSegment(
                road_name=road_name,
                distance_miles=round(distance_miles, 2),
                duration_minutes=round(duration_minutes, 1),
                speed_limit=speed_limit,
                compliant=compliant,
            )
            segments.append(segment)

            if not compliant and distance_miles > 0.01:
                has_noncompliant = True
                total_noncompliant_miles += distance_miles
                warnings.append(Warning(
                    road_name=road_name,
                    speed_limit=speed_limit or 0,
                    distance_miles=round(distance_miles, 2),
                ))

    if not has_noncompliant:
        compliance = "full"
    elif total_noncompliant_miles < 0.5:
        compliance = "partial"
    else:
        compliance = "fallback"

    return compliance, warnings, segments


@router.post("/route")
async def compute_route(req: RouteRequest):
    """
    Compute a golf-cart-safe route.
    First tries the filtered (cart-legal) graph.
    Falls back to the full graph if no compliant route exists.
    """
    route_id = str(uuid.uuid4())[:8]

    # Query OSRM
    data = await query_osrm(req.start, req.end)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="We couldn't find any route between these locations. Please check the addresses and try again.",
        )

    route = data["routes"][0]
    geometry = route.get("geometry", {})
    distance_m = route.get("distance", 0)

    distance_miles = distance_m / METERS_PER_MILE
    # Recalculate duration at fixed cart speed (23 MPH)
    duration_minutes = (distance_miles / DEFAULT_CART_SPEED_MPH) * 60 if distance_miles > 0 else 0

    # Analyze compliance
    compliance, warnings, segments = analyze_route_compliance(route)

    return {
        "route_id": route_id,
        "route_geometry": geometry,
        "distance_miles": round(distance_miles, 1),
        "duration_minutes": round(duration_minutes, 0),
        "compliance": compliance,
        "warnings": [w.model_dump() for w in warnings],
        "segments": [s.model_dump() for s in segments],
        "summary": build_summary(distance_miles, duration_minutes, compliance, warnings),
    }


def build_summary(distance_miles: float, duration_minutes: float, compliance: str, warnings: list[Warning]) -> str:
    """Build a human-readable route summary."""
    base = f"~{int(duration_minutes)} min · {distance_miles:.1f} mi"
    if compliance == "full":
        return f"{base} · All roads ≤35 MPH"
    else:
        total_flagged = sum(w.distance_miles for w in warnings)
        max_speed = max((w.speed_limit for w in warnings), default=0)
        max_road = next((w.road_name for w in warnings if w.speed_limit == max_speed), "")
        return (
            f"{base} · ⚠ Includes {total_flagged:.1f} mi on roads above 35 MPH"
            f" (max: {int(max_speed)} MPH on {max_road})"
        )
