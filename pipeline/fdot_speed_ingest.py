#!/usr/bin/env python3
from __future__ import annotations
"""
CartPath — FDOT Speed Limit Ingestion
=======================================
Downloads FDOT Maximum Speed Limit TDA data, clips to the pilot region,
and performs a spatial join to OSM road segments to enrich speed limit data.

Usage:
    python fdot_speed_ingest.py --osm-graph data/osm_roads.geojson
    python fdot_speed_ingest.py --dry-run --verbose
    python fdot_speed_ingest.py --help

Requirements:
    pip install geopandas shapely requests pandas fiona
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

# ── Defaults ──────────────────────────────────────────────────────────
CENTER_LAT = 28.5641
CENTER_LON = -81.3089
RADIUS_MILES = 30
MAX_AGE_DAYS = 7

# FDOT Open Data Hub — Maximum Speed Limit TDA
FDOT_GEOJSON_URL = (
    "https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/"
    "Maximum_Speed_Limit_TDA/FeatureServer/0/query"
)
# Paginated REST API (service max is 2000)
FDOT_PAGE_SIZE = 2000


def get_pilot_bbox(center_lat: float, center_lon: float, radius_miles: float) -> tuple:
    """Calculate bounding box for the pilot region (approximate)."""
    # ~1 degree lat ≈ 69 miles, ~1 degree lon ≈ 69 * cos(lat) miles
    import math
    lat_offset = radius_miles / 69.0
    lon_offset = radius_miles / (69.0 * math.cos(math.radians(center_lat)))
    return (
        center_lon - lon_offset,  # minx
        center_lat - lat_offset,  # miny
        center_lon + lon_offset,  # maxx
        center_lat + lat_offset,  # maxy
    )


def download_fdot_data(
    center_lat: float, center_lon: float, radius_miles: float,
    cache_dir: str, max_age_days: int, verbose: bool = False,
) -> gpd.GeoDataFrame:
    """Download FDOT speed limit data, with caching."""
    cache_path = Path(cache_dir) / "fdot_speed_limits_raw.geojson"

    # Check cache freshness
    if cache_path.exists():
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        if age_days < max_age_days:
            if verbose:
                print(f"  Using cached FDOT data ({age_days:.1f} days old)")
            return gpd.read_file(cache_path)
        else:
            if verbose:
                print(f"  Cache is {age_days:.1f} days old (max: {max_age_days}). Re-downloading...")

    bbox = get_pilot_bbox(center_lat, center_lon, radius_miles)
    # ArcGIS REST API query with spatial filter
    envelope = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

    all_features = []
    offset = 0
    max_retries = 3

    print("  Downloading FDOT speed limit data...")
    while True:
        params = {
            "where": "1=1",
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": FDOT_PAGE_SIZE,
            "inSR": "4326",
            "outSR": "4326",
        }

        for attempt in range(max_retries):
            try:
                resp = requests.get(FDOT_GEOJSON_URL, params=params, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"    Download failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"ERROR: FDOT download failed after {max_retries} attempts: {e}", file=sys.stderr)
                    sys.exit(1)

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        if verbose:
            print(f"    Fetched {len(all_features):,} features (offset={offset})...")

        if len(features) < FDOT_PAGE_SIZE:
            break
        offset += FDOT_PAGE_SIZE

    if not all_features:
        print("ERROR: No FDOT features returned for the pilot region.", file=sys.stderr)
        sys.exit(1)

    # Build GeoJSON collection and read into GeoDataFrame
    fc = {"type": "FeatureCollection", "features": all_features}
    gdf = gpd.GeoDataFrame.from_features(fc, crs="EPSG:4326")

    # Cache
    os.makedirs(cache_dir, exist_ok=True)
    gdf.to_file(cache_path, driver="GeoJSON")
    if verbose:
        print(f"    Cached to {cache_path}")

    return gdf


def extract_fdot_speed(row) -> float | None:
    """Extract speed limit in MPH from an FDOT feature row."""
    # FDOT Maximum_Speed_Limit_TDA uses "SPEED" as the field name
    for field in ["SPEED", "MAXSPEED", "MAX_SPEED", "SPEED_LIM", "SPEEDLIMIT", "max_speed", "maxspeed"]:
        val = row.get(field)
        if val is not None and val != "" and val != 0:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


def spatial_join_to_osm(
    fdot_gdf: gpd.GeoDataFrame,
    osm_gdf: gpd.GeoDataFrame,
    verbose: bool = False,
) -> dict:
    """Spatial join FDOT segments to nearest OSM ways within 15m buffer."""
    # Ensure both are in the same CRS
    if fdot_gdf.crs != osm_gdf.crs:
        fdot_gdf = fdot_gdf.to_crs(osm_gdf.crs)

    # Project to a metric CRS for distance calculations (UTM 17N for Central FL)
    fdot_proj = fdot_gdf.to_crs("EPSG:32617")
    osm_proj = osm_gdf.to_crs("EPSG:32617")

    if verbose:
        print(f"  Performing spatial join ({len(fdot_proj):,} FDOT → {len(osm_proj):,} OSM)...")

    # sjoin_nearest with max distance of 15 meters
    joined = gpd.sjoin_nearest(
        fdot_proj, osm_proj,
        how="inner",
        max_distance=15,
        distance_col="match_distance",
    )

    if verbose:
        print(f"    Matched {len(joined):,} FDOT→OSM pairs")

    # Build enrichment mapping: osm_id → {speed_limit, source, fdot_speed}
    enrichment = {}
    conflicts = 0

    for _, row in joined.iterrows():
        osm_id = row.get("osm_id")
        if osm_id is None:
            continue
        osm_id = int(osm_id)

        fdot_speed = extract_fdot_speed(row)
        if fdot_speed is None:
            continue

        osm_speed = row.get("maxspeed_mph")
        highway = row.get("highway", "")

        # Conflict resolution per PRD Section 6.4 Step 5
        if osm_speed is not None and osm_speed > 0:
            diff = abs(fdot_speed - osm_speed)
            if diff <= 5:
                # Close enough — prefer OSM tag
                enrichment[osm_id] = {
                    "speed_limit": osm_speed,
                    "source": "osm_tag",
                    "fdot_speed": fdot_speed,
                }
            elif highway in ("primary", "primary_link", "secondary", "secondary_link"):
                # FDOT is authoritative for state roads
                enrichment[osm_id] = {
                    "speed_limit": fdot_speed,
                    "source": "fdot",
                    "osm_speed": osm_speed,
                    "conflict": True,
                }
                conflicts += 1
            else:
                # Prefer OSM for local roads
                enrichment[osm_id] = {
                    "speed_limit": osm_speed,
                    "source": "osm_tag",
                    "fdot_speed": fdot_speed,
                    "conflict": True,
                }
                conflicts += 1
        else:
            # OSM has no speed tag — FDOT fills the gap
            enrichment[osm_id] = {
                "speed_limit": fdot_speed,
                "source": "fdot",
            }

    return enrichment, conflicts


def main():
    parser = argparse.ArgumentParser(
        description="Ingest FDOT speed limit data and enrich OSM road segments for CartPath."
    )
    parser.add_argument("--center-lat", type=float, default=CENTER_LAT)
    parser.add_argument("--center-lon", type=float, default=CENTER_LON)
    parser.add_argument("--radius-miles", type=float, default=RADIUS_MILES)
    parser.add_argument("--max-age", type=int, default=MAX_AGE_DAYS, help="Cache freshness in days (default: 7)")
    parser.add_argument("--osm-graph", default="pipeline/data/osm_roads.geojson", help="Path to OSM road graph GeoJSON")
    parser.add_argument("--output", "-o", default="pipeline/data/osm_speed_enrichment.json", help="Output enrichment JSON")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Download and filter FDOT data only, skip OSM matching")
    args = parser.parse_args()

    print("CartPath — FDOT Speed Limit Ingestion")
    print(f"  Center: {args.center_lat}, {args.center_lon}")
    print(f"  Radius: {args.radius_miles} miles")
    print()

    # Step 1-3: Download, filter, reproject
    cache_dir = os.path.dirname(os.path.abspath(args.output))
    fdot_gdf = download_fdot_data(
        args.center_lat, args.center_lon, args.radius_miles,
        cache_dir, args.max_age, verbose=args.verbose,
    )

    print(f"\n  FDOT segments in pilot region: {len(fdot_gdf):,}")

    if args.dry_run:
        print("\n  [DRY RUN] Skipping OSM spatial join.")
        # Print column names to help debug field mapping
        if args.verbose:
            print(f"  FDOT columns: {list(fdot_gdf.columns)}")
            print(f"  FDOT CRS: {fdot_gdf.crs}")
        print("  Done.")
        return

    # Load OSM graph
    if not os.path.exists(args.osm_graph):
        print(f"ERROR: OSM graph not found at {args.osm_graph}", file=sys.stderr)
        print("  Run osm_extract.py first.", file=sys.stderr)
        sys.exit(1)

    print(f"  Loading OSM graph from {args.osm_graph}...")
    osm_gdf = gpd.read_file(args.osm_graph)
    print(f"  OSM segments loaded: {len(osm_gdf):,}")

    # Step 4-5: Spatial join + conflict resolution
    enrichment, conflicts = spatial_join_to_osm(fdot_gdf, osm_gdf, verbose=args.verbose)

    # Step 6: Write output
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    # Convert int keys to strings for JSON
    enrichment_json = {str(k): v for k, v in enrichment.items()}
    with open(args.output, "w") as f:
        json.dump(enrichment_json, f, indent=2)

    # Step 7: Summary report
    total_matched = len(enrichment)
    gap_fills = sum(1 for v in enrichment.values() if v["source"] == "fdot" and not v.get("conflict"))
    print(f"\n  Summary:")
    print(f"    FDOT segments downloaded: {len(fdot_gdf):,}")
    print(f"    Matched to OSM ways:     {total_matched:,}")
    print(f"    Gap fills (new data):    {gap_fills:,}")
    print(f"    Conflicts detected:      {conflicts:,}")
    print(f"    Match rate:              {total_matched / max(len(fdot_gdf), 1) * 100:.1f}%")
    print(f"\n  Output: {args.output}")


if __name__ == "__main__":
    main()
