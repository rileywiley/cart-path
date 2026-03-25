"""
CartPath — Geocoding Proxy Endpoint
=====================================
Uses the Mapbox Search Box API v1 for autocomplete suggestions (better POI
coverage than Geocoding v5), with a retrieve step to get coordinates.

GET /api/geocode/suggest?q={query}  — autocomplete suggestions
GET /api/geocode/retrieve?id={mapbox_id} — full feature with coordinates
GET /api/geocode?q={query}          — legacy one-shot (suggest + retrieve first result)
"""

from __future__ import annotations

import math
import os
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

MAPBOX_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "")
SEARCH_SUGGEST_URL = "https://api.mapbox.com/search/searchbox/v1/suggest"
SEARCH_RETRIEVE_URL = "https://api.mapbox.com/search/searchbox/v1/retrieve"

# Pilot region center (Baldwin Park, FL)
PROXIMITY_LON = -81.3089
PROXIMITY_LAT = 28.5641
RADIUS_MILES = 30


def _bbox_from_center(lat: float, lon: float, radius_miles: float) -> str:
    """Compute a bounding box string for Mapbox from a center point and radius."""
    # 1 degree latitude ≈ 69 miles
    delta_lat = radius_miles / 69.0
    # 1 degree longitude ≈ 69 * cos(lat) miles
    delta_lon = radius_miles / (69.0 * math.cos(math.radians(lat)))
    return f"{lon - delta_lon},{lat - delta_lat},{lon + delta_lon},{lat + delta_lat}"


def _require_token():
    if not MAPBOX_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Geocoding service not configured. Set MAPBOX_ACCESS_TOKEN.",
        )


@router.get("/geocode/suggest")
async def suggest(
    q: str = Query(..., min_length=2, description="Search query"),
    proximity_lat: Optional[float] = Query(None, description="User latitude"),
    proximity_lon: Optional[float] = Query(None, description="User longitude"),
    session_token: Optional[str] = Query(None, description="Session token for billing"),
):
    """Return autocomplete suggestions using Mapbox Search Box API."""
    _require_token()

    prox_lon = proximity_lon if proximity_lon is not None else PROXIMITY_LON
    prox_lat = proximity_lat if proximity_lat is not None else PROXIMITY_LAT

    params = {
        "q": q,
        "access_token": MAPBOX_TOKEN,
        "session_token": session_token or str(uuid.uuid4()),
        "proximity": f"{prox_lon},{prox_lat}",
        "bbox": _bbox_from_center(prox_lat, prox_lon, RADIUS_MILES),
        "country": "US",
        "types": "poi,address,street,place",
        "limit": 5,
        "language": "en",
    }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(SEARCH_SUGGEST_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Search API error: {e.response.status_code}")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Search service unreachable")

    results = []
    for suggestion in data.get("suggestions", []):
        results.append({
            "name": suggestion.get("name", ""),
            "place_name": suggestion.get("full_address") or suggestion.get("place_formatted", ""),
            "mapbox_id": suggestion.get("mapbox_id", ""),
            "category": suggestion.get("poi_category", suggestion.get("feature_type", "")),
            "address": suggestion.get("address", ""),
            "feature_type": suggestion.get("feature_type", ""),
        })

    return {"query": q, "results": results}


@router.get("/geocode/retrieve")
async def retrieve(
    id: str = Query(..., description="Mapbox feature ID from suggest"),
    session_token: Optional[str] = Query(None, description="Session token for billing"),
):
    """Retrieve full feature (with coordinates) for a suggestion."""
    _require_token()

    params = {
        "access_token": MAPBOX_TOKEN,
        "session_token": session_token or str(uuid.uuid4()),
    }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{SEARCH_RETRIEVE_URL}/{id}", params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Retrieve API error: {e.response.status_code}")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Search service unreachable")

    features = data.get("features", [])
    if not features:
        raise HTTPException(status_code=404, detail="Feature not found")

    feature = features[0]
    coords = feature.get("geometry", {}).get("coordinates", [0, 0])
    props = feature.get("properties", {})

    return {
        "name": props.get("name", ""),
        "place_name": props.get("full_address") or props.get("place_formatted", ""),
        "lat": coords[1],
        "lon": coords[0],
        "category": props.get("poi_category", props.get("feature_type", "")),
        "address": props.get("address", ""),
        "mapbox_id": props.get("mapbox_id", ""),
    }


@router.get("/geocode")
async def geocode(
    q: str = Query(..., min_length=2, description="Search query"),
    proximity_lat: Optional[float] = Query(None, description="User latitude"),
    proximity_lon: Optional[float] = Query(None, description="User longitude"),
):
    """Legacy one-shot geocode: suggest + retrieve first result. Returns coords."""
    _require_token()

    session_token = str(uuid.uuid4())

    # Step 1: suggest
    suggest_resp = await suggest(
        q=q,
        proximity_lat=proximity_lat,
        proximity_lon=proximity_lon,
        session_token=session_token,
    )

    results = suggest_resp.get("results", [])
    if not results:
        return {"query": q, "results": []}

    # Step 2: retrieve coords for each result (up to 5)
    full_results = []
    for s in results:
        mapbox_id = s.get("mapbox_id")
        if not mapbox_id:
            continue
        try:
            retrieved = await retrieve(id=mapbox_id, session_token=session_token)
            full_results.append({
                "name": retrieved["name"],
                "place_name": retrieved["place_name"],
                "lat": retrieved["lat"],
                "lon": retrieved["lon"],
                "relevance": 1.0,
                "category": retrieved["category"],
                "address": retrieved["address"],
            })
        except HTTPException:
            continue

    return {"query": q, "results": full_results}
