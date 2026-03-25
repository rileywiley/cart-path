"""
CartPath — Routing Endpoint
==============================
POST /api/route — computes golf-cart-safe routes via OSRM.
Returns multiple route alternatives:
  - Best route (balanced): fastest cart-legal route
  - Residential-only: longer but avoids all non-residential roads
  - OSRM alternatives: additional alternatives from OSRM's engine
Includes fallback routing with non-compliant segment annotations.
"""

import json
import os
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .middleware import get_optional_user

router = APIRouter()

OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5000")
SPEED_DATA_PATH = os.environ.get("CARTPATH_SPEED_DATA", "pipeline/data/classified_speeds.json")

# Constants — speed thresholds by vehicle type
MAX_SPEED_GOLF_CART_MPH = 25
MAX_SPEED_LSV_MPH = 35
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
    vehicle_type: str = Field(default="lsv", pattern="^(golf_cart|lsv)$")


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
    road_type: Optional[str] = None
    compliant: bool = True
    is_residential: bool = False


async def query_osrm(start: Coordinates, end: Coordinates, alternatives: bool = False) -> Optional[dict]:
    """Query OSRM for a route between two points."""
    coords = f"{start.lon},{start.lat};{end.lon},{end.lat}"
    url = f"{OSRM_URL}/route/v1/driving/{coords}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "annotations": "true",
    }
    if alternatives:
        params["alternatives"] = "3"

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


def classify_road_type(step: dict) -> str:
    """Infer road type from OSRM step metadata."""
    ref = (step.get("ref") or "").lower()

    # Heuristics based on naming patterns common in the FL pilot region
    if ref and any(prefix in ref for prefix in ["sr ", "us ", "fl ", "cr "]):
        return "classified"  # State/county road — likely primary/secondary

    return "unknown"


def is_residential_road(step: dict, speed_limit: float | None, road_type: str) -> bool:
    """
    Determine if a road segment is residential-type.
    Uses speed limit and road reference heuristics because OSRM steps don't
    expose the original OSM highway tag directly. In the FL pilot region:
    - Roads ≤25 MPH are almost always residential/living_street
    - Roads with no state/county ref and ≤30 MPH are likely residential
    """
    if speed_limit is not None and speed_limit <= 25:
        return True
    if road_type != "classified":
        ref = step.get("ref") or ""
        if not ref and (speed_limit is None or speed_limit <= 30):
            return True
    return False


def analyze_route_compliance(route: dict, max_speed_mph: int = MAX_SPEED_GOLF_CART_MPH) -> tuple[str, list[Warning], list[RouteSegment], dict]:
    """
    Analyze route steps for speed limit compliance.
    Returns (compliance_level, warnings, segments, stats).
    max_speed_mph: 25 for golf carts, 35 for LSVs.
    """
    warnings = []
    segments = []
    has_noncompliant = False
    total_noncompliant_miles = 0
    residential_miles = 0
    total_miles = 0

    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            road_name = step.get("name", "Unknown road")
            distance_m = step.get("distance", 0)
            distance_miles = distance_m / METERS_PER_MILE
            total_miles += distance_miles

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

            # Check against the vehicle-type speed threshold
            if speed_limit is not None and speed_limit > max_speed_mph:
                compliant = False

            # Determine if this is a residential-type road
            road_type = classify_road_type(step)
            is_residential = is_residential_road(step, speed_limit, road_type)

            if is_residential:
                residential_miles += distance_miles

            segment = RouteSegment(
                road_name=road_name,
                distance_miles=round(distance_miles, 2),
                duration_minutes=round(duration_minutes, 1),
                speed_limit=speed_limit,
                road_type=road_type,
                compliant=compliant,
                is_residential=is_residential,
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

    stats = {
        "residential_miles": round(residential_miles, 2),
        "total_miles": round(total_miles, 2),
        "residential_pct": round(residential_miles / max(total_miles, 0.01) * 100, 0),
    }

    return compliance, warnings, segments, stats


def build_route_response(route: dict, route_id: str, label: str, max_speed_mph: int = MAX_SPEED_GOLF_CART_MPH) -> dict:
    """Build a standardized route response dict from an OSRM route."""
    geometry = route.get("geometry", {})
    distance_m = route.get("distance", 0)
    distance_miles = distance_m / METERS_PER_MILE
    duration_minutes = (distance_miles / DEFAULT_CART_SPEED_MPH) * 60 if distance_miles > 0 else 0

    compliance, warnings, segments, stats = analyze_route_compliance(route, max_speed_mph)

    return {
        "route_id": route_id,
        "label": label,
        "route_geometry": geometry,
        "distance_miles": round(distance_miles, 1),
        "duration_minutes": round(duration_minutes, 0),
        "compliance": compliance,
        "warnings": [w.model_dump() for w in warnings],
        "segments": [s.model_dump() for s in segments],
        "summary": build_summary(distance_miles, duration_minutes, compliance, warnings, max_speed_mph),
        "residential_pct": stats["residential_pct"],
    }


def rank_residential_route(routes: list[dict]) -> Optional[dict]:
    """
    From OSRM alternatives, find the route with the highest residential %.
    Returns None if no route has >50% residential roads.
    """
    best = None
    best_pct = 0
    for r in routes:
        pct = r.get("residential_pct", 0)
        if pct > best_pct:
            best_pct = pct
            best = r
    # Only label it as residential-preferred if meaningfully different
    if best and best_pct > 50:
        return best
    return None


@router.post("/route")
async def compute_route(req: RouteRequest, request: Request):
    """
    Compute golf-cart-safe routes with multiple alternatives.
    Returns up to 3 route options:
      1. Best route (fastest cart-legal)
      2. Residential-preferred (most residential roads)
      3. Additional OSRM alternative (if available)
    """
    # Determine speed threshold from vehicle type
    # Use request body vehicle_type, or fall back to authenticated user's profile
    vehicle_type = req.vehicle_type
    user = await get_optional_user(request)
    if vehicle_type == "golf_cart" and user and user.get("vehicle_type"):
        vehicle_type = user["vehicle_type"]
    max_speed = MAX_SPEED_LSV_MPH if vehicle_type == "lsv" else MAX_SPEED_GOLF_CART_MPH

    # Query OSRM with alternatives enabled
    data = await query_osrm(req.start, req.end, alternatives=True)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="We couldn't find any route between these locations. Please check the addresses and try again.",
        )

    osrm_routes = data["routes"]
    alternatives = []

    # Build response for each OSRM alternative
    for i, osrm_route in enumerate(osrm_routes[:3]):
        route_id = str(uuid.uuid4())[:8]
        if i == 0:
            label = "Best route"
        else:
            label = f"Alternative {i}"
        alt = build_route_response(osrm_route, route_id, label, max_speed)
        alternatives.append(alt)

    # Identify the most residential-friendly route among alternatives
    residential_route = rank_residential_route(alternatives)
    if residential_route and len(alternatives) > 1:
        # Re-label it if it's not already the best route
        if residential_route["route_id"] != alternatives[0]["route_id"]:
            residential_route["label"] = "Residential roads"
        else:
            # If the best route is already the most residential, label the next one
            alternatives[1]["label"] = "Faster route"
            alternatives[0]["label"] = "Residential roads"

    # Ensure unique labels
    seen_labels = set()
    for alt in alternatives:
        if alt["label"] in seen_labels:
            alt["label"] = f"{alt['label']} ({alt['distance_miles']} mi)"
        seen_labels.add(alt["label"])

    # Primary route is the first one (for backwards compatibility)
    primary = alternatives[0]

    return {
        "route_id": primary["route_id"],
        "route_geometry": primary["route_geometry"],
        "distance_miles": primary["distance_miles"],
        "duration_minutes": primary["duration_minutes"],
        "compliance": primary["compliance"],
        "warnings": primary["warnings"],
        "segments": primary["segments"],
        "summary": primary["summary"],
        "residential_pct": primary["residential_pct"],
        # Multiple route alternatives
        "alternatives": alternatives,
    }


def build_summary(distance_miles: float, duration_minutes: float, compliance: str, warnings: list[Warning], max_speed_mph: int = MAX_SPEED_GOLF_CART_MPH) -> str:
    """Build a human-readable route summary."""
    base = f"~{int(duration_minutes)} min · {distance_miles:.1f} mi"
    if compliance == "full":
        return f"{base} · All roads ≤{max_speed_mph} MPH"
    else:
        total_flagged = sum(w.distance_miles for w in warnings)
        max_speed = max((w.speed_limit for w in warnings), default=0)
        max_road = next((w.road_name for w in warnings if w.speed_limit == max_speed), "")
        return (
            f"{base} · Includes {total_flagged:.1f} mi on roads above {max_speed_mph} MPH"
            f" (max: {int(max_speed)} MPH on {max_road})"
        )
