"""
CartPath — Geocoding Proxy Endpoint
=====================================
GET /api/geocode?q={query} — proxies to Mapbox Geocoding API,
biased to the Baldwin Park pilot region.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

MAPBOX_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "")
MAPBOX_GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"

# Pilot region bounding box (Baldwin Park, FL — 30-mile radius)
BBOX = "-82.06,27.99,-80.57,29.13"  # minLon,minLat,maxLon,maxLat
PROXIMITY = "-81.3089,28.5641"       # center point for result biasing


@router.get("/geocode")
async def geocode(
    q: str = Query(..., min_length=2, description="Search query"),
    proximity_lat: Optional[float] = Query(None, description="User latitude for proximity bias"),
    proximity_lon: Optional[float] = Query(None, description="User longitude for proximity bias"),
):
    if not MAPBOX_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Geocoding service not configured. Set MAPBOX_ACCESS_TOKEN.",
        )

    # Use user's location for proximity when available, else fall back to region center
    if proximity_lon is not None and proximity_lat is not None:
        proximity = f"{proximity_lon},{proximity_lat}"
    else:
        proximity = PROXIMITY

    params = {
        "access_token": MAPBOX_TOKEN,
        "autocomplete": "true",
        "bbox": BBOX,
        "proximity": proximity,
        "fuzzyMatch": "true",
        "limit": 5,
        "country": "US",
        "types": "poi,address,place,neighborhood,locality",
    }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{MAPBOX_GEOCODE_URL}/{q}.json", params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Geocoding API error: {e.response.status_code}")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Geocoding service unreachable")

    # Transform to simplified response
    results = []
    for feature in data.get("features", []):
        center = feature.get("center", [0, 0])
        properties = feature.get("properties", {})
        # Extract POI category from Mapbox response
        category = properties.get("category", "")
        if not category:
            # Fall back to the place type (e.g., "poi", "address")
            place_types = feature.get("place_type", [])
            category = place_types[0] if place_types else ""
        # Extract address context for display
        address = feature.get("properties", {}).get("address", "")
        results.append({
            "name": feature.get("text", ""),
            "place_name": feature.get("place_name", ""),
            "lat": center[1],
            "lon": center[0],
            "relevance": feature.get("relevance", 0),
            "category": category,
            "address": address,
        })

    return {"query": q, "results": results}
