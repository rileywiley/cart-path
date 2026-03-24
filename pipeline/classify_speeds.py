#!/usr/bin/env python3
from __future__ import annotations
"""
CartPath — Speed Classification Pipeline
==========================================
Applies 4-tier speed classification to OSM road segments and integrates
service road filtering rules.

Tiers:
  1. Explicit OSM maxspeed tags (~6.4%)
  2. FDOT enrichment data
  3. Road-type inference (Florida legal defaults)
  4. Unknown — excluded from default routing graph (~2.6%)

Usage:
    python classify_speeds.py
    python classify_speeds.py --osm-graph data/osm_roads.geojson --fdot-enrichment data/osm_speed_enrichment.json
    python classify_speeds.py --help

Requirements:
    pip install pandas
"""

import argparse
import json
import os
import sys
from collections import Counter

# ── Constants ─────────────────────────────────────────────────────────
MAX_SPEED_MPH = 35
DEFAULT_CART_SPEED_MPH = 23
SERVICE_ROAD_SPEED_MPH = 10

# Florida legal default speeds by road type (from FL statute + FDOT conventions)
# Used for Tier 3 inference when no explicit tag or FDOT data exists
FL_DEFAULT_SPEEDS = {
    "residential":    25,
    "living_street":  15,
    "service":        15,
    "tertiary":       30,
    "tertiary_link":  25,
    "unclassified":   35,  # conservative — these are ambiguous
    "secondary":      45,
    "secondary_link": 35,
    "primary":        45,
    "primary_link":   35,
}

# Service road subtypes to EXCLUDE from routing graph entirely
SERVICE_EXCLUDE = {"driveway", "parking_aisle"}
# Service road subtypes to INCLUDE (with 10 MPH penalty)
SERVICE_INCLUDE = {"", "alley", "parking"}  # empty string = no subtype tag


def parse_speed(raw: str) -> float | None:
    """Parse OSM maxspeed tag to numeric MPH."""
    if not raw:
        return None
    raw = raw.strip().lower()
    if raw in ("none", "signals", "walk", "variable"):
        return None
    try:
        if "mph" in raw:
            return float(raw.replace("mph", "").strip())
        elif "km/h" in raw or "kmh" in raw:
            val = float(raw.replace("km/h", "").replace("kmh", "").strip())
            return round(val * 0.621371, 1)
        else:
            # In the US pilot region, assume unitless values are MPH
            return float(raw)
    except ValueError:
        return None


def classify_segment(props: dict, fdot_enrichment: dict) -> dict:
    """
    Classify a single road segment's speed and cart-legality.

    Returns dict with: speed_limit, speed_source, cart_legal, routing_speed, excluded, exclude_reason
    """
    osm_id = str(props.get("osm_id", ""))
    highway = props.get("highway", "")
    service_type = props.get("service", "")
    maxspeed_raw = props.get("maxspeed", "")

    result = {
        "speed_limit": None,
        "speed_source": "unknown",
        "cart_legal": "unknown",
        "routing_speed": DEFAULT_CART_SPEED_MPH,
        "excluded": False,
        "exclude_reason": None,
    }

    # ── Service road filtering (PRD Section 6.3) ──
    if highway == "service":
        if service_type in SERVICE_EXCLUDE:
            result["excluded"] = True
            result["exclude_reason"] = f"service={service_type}"
            result["cart_legal"] = False
            return result

        # All included service roads: cart_legal, 10 MPH routing penalty
        result["speed_limit"] = 15
        result["speed_source"] = "service_default"
        result["cart_legal"] = True
        result["routing_speed"] = SERVICE_ROAD_SPEED_MPH
        return result

    # ── Tier 1: Explicit OSM maxspeed tag ──
    osm_speed = parse_speed(maxspeed_raw)
    if osm_speed is not None:
        result["speed_limit"] = osm_speed
        result["speed_source"] = "osm_tag"
        result["cart_legal"] = osm_speed <= MAX_SPEED_MPH
        result["routing_speed"] = DEFAULT_CART_SPEED_MPH if result["cart_legal"] else osm_speed
        return result

    # ── Tier 2: FDOT enrichment ──
    fdot_data = fdot_enrichment.get(osm_id)
    if fdot_data and fdot_data.get("speed_limit") is not None:
        speed = fdot_data["speed_limit"]
        result["speed_limit"] = speed
        result["speed_source"] = fdot_data.get("source", "fdot")
        result["cart_legal"] = speed <= MAX_SPEED_MPH
        result["routing_speed"] = DEFAULT_CART_SPEED_MPH if result["cart_legal"] else speed
        return result

    # ── Tier 3: Road-type inference ──
    default_speed = FL_DEFAULT_SPEEDS.get(highway)
    if default_speed is not None:
        result["speed_limit"] = default_speed
        result["speed_source"] = "inferred"
        result["cart_legal"] = default_speed <= MAX_SPEED_MPH
        result["routing_speed"] = DEFAULT_CART_SPEED_MPH if result["cart_legal"] else default_speed
        return result

    # ── Tier 4: Unknown ──
    result["speed_limit"] = None
    result["speed_source"] = "unknown"
    result["cart_legal"] = "unknown"
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Apply 4-tier speed classification to OSM road segments for CartPath."
    )
    parser.add_argument("--osm-graph", default="pipeline/data/osm_roads.geojson", help="Input OSM GeoJSON")
    parser.add_argument("--fdot-enrichment", default="pipeline/data/osm_speed_enrichment.json", help="FDOT enrichment JSON")
    parser.add_argument("--output", "-o", default="pipeline/data/classified_speeds.json", help="Output classified JSON")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("CartPath — Speed Classification")

    # Load OSM data
    if not os.path.exists(args.osm_graph):
        print(f"ERROR: OSM graph not found: {args.osm_graph}", file=sys.stderr)
        sys.exit(1)

    with open(args.osm_graph) as f:
        osm_data = json.load(f)
    features = osm_data.get("features", [])
    print(f"  Loaded {len(features):,} OSM segments")

    # Load FDOT enrichment (optional — may not exist if FDOT download failed)
    fdot_enrichment = {}
    if os.path.exists(args.fdot_enrichment):
        with open(args.fdot_enrichment) as f:
            fdot_enrichment = json.load(f)
        print(f"  Loaded {len(fdot_enrichment):,} FDOT enrichment entries")
    else:
        print("  WARNING: No FDOT enrichment file found. Using Tier 1 + Tier 3 only.")

    # Classify each segment
    classifications = {}
    counters = {
        "source": Counter(),
        "cart_legal": Counter(),
        "excluded": 0,
    }

    for feature in features:
        props = feature["properties"]
        osm_id = str(props.get("osm_id", ""))
        result = classify_segment(props, fdot_enrichment)
        classifications[osm_id] = result

        if result["excluded"]:
            counters["excluded"] += 1
        else:
            counters["source"][result["speed_source"]] += 1
            counters["cart_legal"][str(result["cart_legal"])] += 1

    # Write output
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(classifications, f)

    # Summary
    total = len(features)
    print(f"\n  Classification Summary ({total:,} segments):")
    print(f"    Excluded (driveway/parking_aisle): {counters['excluded']:,}")
    print(f"    By source:")
    for source, count in counters["source"].most_common():
        print(f"      {source:<20} {count:>7,}  ({count / total * 100:.1f}%)")
    print(f"    Cart legality:")
    for status, count in counters["cart_legal"].most_common():
        print(f"      {status:<20} {count:>7,}  ({count / total * 100:.1f}%)")
    print(f"\n  Output: {args.output}")


if __name__ == "__main__":
    main()
