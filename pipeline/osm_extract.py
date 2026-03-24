#!/usr/bin/env python3
"""
CartPath — OSM Road Extraction
================================
Queries the Overpass API for all drivable roads (with geometry) within the
pilot region and outputs a GeoJSON file ready for the classification pipeline.

Usage:
    python osm_extract.py
    python osm_extract.py --center-lat 28.5641 --center-lon -81.3089 --radius-miles 30
    python osm_extract.py --output data/osm_roads.geojson --verbose

Requirements:
    pip install requests
"""

import argparse
import json
import os
import sys
import time

import requests

# ── Defaults ──────────────────────────────────────────────────────────
CENTER_LAT = 28.5641
CENTER_LON = -81.3089
RADIUS_MILES = 30

# Road types relevant to golf cart navigation
# Excludes motorway, motorway_link, trunk, trunk_link (always >35 MPH)
ROAD_TYPES = [
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "residential", "unclassified",
    "living_street", "service",
]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TIMEOUT = 300  # seconds — geometry queries are larger than tag-only


def build_query(center_lat: float, center_lon: float, radius_meters: int) -> str:
    """Build an Overpass QL query to fetch roads with full geometry."""
    highway_filter = "|".join(ROAD_TYPES)
    return f"""
[out:json][timeout:{TIMEOUT}];
(
  way["highway"~"^({highway_filter})$"]
    (around:{radius_meters},{center_lat},{center_lon});
);
out body geom;
""".strip()


def query_overpass(query: str, verbose: bool = False) -> dict:
    """Execute the Overpass query with retry logic."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if verbose:
                print(f"  Attempt {attempt + 1}/{max_retries}...")
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=TIMEOUT + 60,
            )
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  Request failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"ERROR: Overpass query failed after {max_retries} attempts: {e}", file=sys.stderr)
                sys.exit(1)


def parse_speed(raw: str) -> float | None:
    """Parse an OSM maxspeed tag into numeric MPH."""
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


def elements_to_geojson(elements: list) -> dict:
    """Convert Overpass elements (with geometry) to a GeoJSON FeatureCollection."""
    features = []
    for el in elements:
        if el.get("type") != "way":
            continue
        geometry = el.get("geometry")
        if not geometry:
            continue

        # Build LineString from node coordinates
        coords = [[node["lon"], node["lat"]] for node in geometry]
        if len(coords) < 2:
            continue

        tags = el.get("tags", {})
        props = {
            "osm_id": el["id"],
            "highway": tags.get("highway", ""),
            "name": tags.get("name", ""),
            "maxspeed": tags.get("maxspeed", ""),
            "maxspeed_mph": parse_speed(tags.get("maxspeed", "")),
            "surface": tags.get("surface", ""),
            "service": tags.get("service", ""),
            "lanes": tags.get("lanes", ""),
            "oneway": tags.get("oneway", ""),
        }

        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def print_summary(geojson: dict, verbose: bool = False):
    """Print extraction summary statistics."""
    features = geojson["features"]
    total = len(features)
    print(f"\n  Total road segments extracted: {total:,}")

    # Count by highway type
    by_type: dict[str, int] = {}
    with_speed = 0
    with_surface = 0
    for f in features:
        p = f["properties"]
        ht = p["highway"]
        by_type[ht] = by_type.get(ht, 0) + 1
        if p["maxspeed"]:
            with_speed += 1
        if p["surface"]:
            with_surface += 1

    print(f"  With maxspeed tag: {with_speed:,} ({with_speed / max(total, 1) * 100:.1f}%)")
    print(f"  With surface tag:  {with_surface:,} ({with_surface / max(total, 1) * 100:.1f}%)")

    if verbose:
        print("\n  By road type:")
        for rt in ROAD_TYPES:
            count = by_type.get(rt, 0)
            if count:
                print(f"    {rt:<20} {count:>7,}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Extract drivable roads from OSM via Overpass API for the CartPath pilot region."
    )
    parser.add_argument("--center-lat", type=float, default=CENTER_LAT, help=f"Center latitude (default: {CENTER_LAT})")
    parser.add_argument("--center-lon", type=float, default=CENTER_LON, help=f"Center longitude (default: {CENTER_LON})")
    parser.add_argument("--radius-miles", type=float, default=RADIUS_MILES, help=f"Radius in miles (default: {RADIUS_MILES})")
    parser.add_argument("--output", "-o", default="pipeline/data/osm_roads.geojson", help="Output GeoJSON file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    radius_meters = int(args.radius_miles * 1609.34)

    print("CartPath — OSM Road Extraction")
    print(f"  Center: {args.center_lat}, {args.center_lon}")
    print(f"  Radius: {args.radius_miles} miles ({radius_meters:,} meters)")
    print(f"  Road types: {len(ROAD_TYPES)}")
    print()

    # Build and execute query
    query = build_query(args.center_lat, args.center_lon, radius_meters)
    if args.verbose:
        print(f"  Overpass query:\n{query}\n")

    print("  Querying Overpass API (this may take 1-3 minutes)...")
    start = time.time()
    data = query_overpass(query, verbose=args.verbose)
    elapsed = time.time() - start

    elements = data.get("elements", [])
    print(f"  Received {len(elements):,} elements in {elapsed:.1f}s")

    # Convert to GeoJSON
    geojson = elements_to_geojson(elements)
    print_summary(geojson, verbose=args.verbose)

    # Write output
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(geojson, f)

    file_size = os.path.getsize(args.output)
    print(f"  Written to: {args.output} ({file_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
