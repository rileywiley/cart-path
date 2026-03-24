"""
CartPath — Health Check Endpoint
==================================
GET /api/health — checks OSRM status and data freshness.
"""

import json
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter

router = APIRouter()

OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5000")
HEALTH_JSON = os.environ.get("CARTPATH_HEALTH_JSON", "pipeline/data/health.json")
STALENESS_DAYS = 10


@router.get("/health")
async def health_check():
    status = {
        "status": "ok",
        "osrm": "unknown",
        "data_freshness": "unknown",
        "warnings": [],
    }

    # Check OSRM
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OSRM_URL}/nearest/v1/driving/0,0")
            status["osrm"] = "ok" if resp.status_code in (200, 400) else "error"
    except Exception:
        status["osrm"] = "unreachable"
        status["warnings"].append("OSRM routing engine is not responding")

    # Check data freshness
    if os.path.exists(HEALTH_JSON):
        try:
            with open(HEALTH_JSON) as f:
                health_data = json.load(f)

            timestamp = health_data.get("timestamp", "")
            status["data_timestamp"] = timestamp
            status["pipeline_stats"] = {
                "total_segments": health_data.get("total_segments"),
                "speed_classification": health_data.get("speed_classification"),
                "cart_legality": health_data.get("cart_legality"),
                "surface_classification": health_data.get("surface_classification"),
            }

            # Check staleness
            if timestamp:
                data_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - data_time).total_seconds() / 86400
                status["data_age_days"] = round(age_days, 1)
                if age_days > STALENESS_DAYS:
                    status["warnings"].append(
                        f"Data is {age_days:.0f} days old (threshold: {STALENESS_DAYS} days)"
                    )
                    status["data_freshness"] = "stale"
                else:
                    status["data_freshness"] = "fresh"
        except (json.JSONDecodeError, KeyError, ValueError):
            status["data_freshness"] = "error"
            status["warnings"].append("Could not parse health.json")
    else:
        status["data_freshness"] = "missing"
        status["warnings"].append("health.json not found — run the data pipeline")

    # Overall status
    if status["osrm"] != "ok" or status["data_freshness"] not in ("fresh",):
        status["status"] = "degraded"

    return status
