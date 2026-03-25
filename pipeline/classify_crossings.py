#!/usr/bin/env python3
"""
CartPath — Crossing Classification
======================================
Identifies intersections where cart-legal roads cross major (>35 MPH) roads
and classifies them as signalized or unsignalized. This data feeds into the
OSRM profile to penalize unlit crossings and prefer lighted intersections.

Usage:
    python classify_crossings.py
    python classify_crossings.py --osm-graph data/osm_roads.geojson --signals data/traffic_signals.json --speeds data/classified_speeds.json
    python classify_crossings.py --help

Requirements:
    No external dependencies required.
"""

import argparse
import json
import math
import os
import sys
from collections import defaultdict

# ── Constants ─────────────────────────────────────────────────────────
MAX_SPEED_MPH = 35
SIGNAL_SNAP_DISTANCE_M = 30  # Max distance (meters) to associate a signal with an intersection


def load_json(path: str, label: str):
    """Load a JSON file or exit with error."""
    if not os.path.exists(path):
        print(f"ERROR: {label} not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in meters between two lat/lon points."""
    R = 6371000  # Earth radius in meters
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_road_intersections(features: list, speed_data: dict) -> list[dict]:
    """
    Find points where cart-legal roads share endpoints/nodes with >35 MPH roads.
    Returns a list of crossing points with metadata.
    """
    # Separate roads into cart-legal and major (>35 MPH)
    major_segments = {}  # osm_id -> feature (roads with speed > 35)
    cart_legal_segments = {}  # osm_id -> feature

    for feature in features:
        props = feature["properties"]
        osm_id = str(props.get("osm_id", ""))
        speed_info = speed_data.get(osm_id, {})

        if speed_info.get("excluded"):
            continue

        speed_limit = speed_info.get("speed_limit")
        cart_legal = speed_info.get("cart_legal")

        if speed_limit is not None and speed_limit > MAX_SPEED_MPH:
            major_segments[osm_id] = feature
        elif str(cart_legal).lower() == "true":
            cart_legal_segments[osm_id] = feature

    # Build a spatial index of major road coordinates (rounded for matching)
    # Key: (rounded_lon, rounded_lat) -> list of major road info
    PRECISION = 6  # ~0.11m precision at equator
    major_road_nodes = defaultdict(list)
    for osm_id, feature in major_segments.items():
        coords = feature.get("geometry", {}).get("coordinates", [])
        props = feature["properties"]
        speed_info = speed_data.get(osm_id, {})
        for lon, lat in coords:
            key = (round(lon, PRECISION), round(lat, PRECISION))
            major_road_nodes[key].append({
                "osm_id": osm_id,
                "road_name": props.get("name", "Unknown"),
                "speed_limit": speed_info.get("speed_limit", 0),
            })

    # Find cart-legal road nodes that match major road nodes (shared intersections)
    crossings = []
    seen = set()  # Avoid duplicate crossings at the same point

    for osm_id, feature in cart_legal_segments.items():
        coords = feature.get("geometry", {}).get("coordinates", [])
        props = feature["properties"]
        for lon, lat in coords:
            key = (round(lon, PRECISION), round(lat, PRECISION))
            if key in major_road_nodes and key not in seen:
                seen.add(key)
                major_info = major_road_nodes[key]
                max_speed = max(m["speed_limit"] for m in major_info)
                road_names = list({m["road_name"] for m in major_info if m["road_name"] != "Unknown"})
                crossings.append({
                    "lat": lat,
                    "lon": lon,
                    "major_road_names": road_names,
                    "max_speed_limit": max_speed,
                    "cart_road_osm_id": osm_id,
                    "cart_road_name": props.get("name", ""),
                    "has_signal": False,  # Will be filled in next step
                })

    return crossings


def tag_signalized_crossings(crossings: list[dict], signals: list[dict]) -> list[dict]:
    """
    Match traffic signal nodes to crossing points.
    A crossing is 'signalized' if a traffic signal is within SIGNAL_SNAP_DISTANCE_M.
    Uses a grid-based spatial index for O(N+M) average performance.
    """
    # Build a grid index of signals (~0.0003° ≈ 33m cell size at this latitude)
    GRID_SIZE = 0.0003
    signal_grid: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for signal in signals:
        gx = int(signal["lon"] / GRID_SIZE)
        gy = int(signal["lat"] / GRID_SIZE)
        signal_grid[(gx, gy)].append(signal)

    for crossing in crossings:
        clat, clon = crossing["lat"], crossing["lon"]
        gx = int(clon / GRID_SIZE)
        gy = int(clat / GRID_SIZE)

        # Check the 3x3 neighborhood of grid cells
        found = False
        for dx in (-1, 0, 1):
            if found:
                break
            for dy in (-1, 0, 1):
                for signal in signal_grid.get((gx + dx, gy + dy), []):
                    dist = haversine_m(clat, clon, signal["lat"], signal["lon"])
                    if dist <= SIGNAL_SNAP_DISTANCE_M:
                        crossing["has_signal"] = True
                        crossing["signal_node_id"] = signal["node_id"]
                        found = True
                        break
                if found:
                    break

    return crossings


def build_node_signal_index(crossings: list[dict]) -> dict:
    """
    Build a lookup of (rounded_lon, rounded_lat) -> crossing info
    for use during OSRM graph build. Nodes near these crossings
    get tagged with cartpath:crossing_signal=yes/no.
    """
    PRECISION = 6
    index = {}
    for c in crossings:
        key = f"{round(c['lon'], PRECISION)},{round(c['lat'], PRECISION)}"
        index[key] = {
            "has_signal": c["has_signal"],
            "max_speed_limit": c["max_speed_limit"],
            "major_road_names": c.get("major_road_names", []),
        }
    return index


def main():
    parser = argparse.ArgumentParser(
        description="Classify road crossings as signalized or unsignalized for CartPath routing."
    )
    parser.add_argument("--osm-graph", default="pipeline/data/osm_roads.geojson", help="Input OSM GeoJSON")
    parser.add_argument("--signals", default="pipeline/data/traffic_signals.json", help="Traffic signals JSON")
    parser.add_argument("--speeds", default="pipeline/data/classified_speeds.json", help="Speed classification JSON")
    parser.add_argument("--output", "-o", default="pipeline/data/classified_crossings.json", help="Output crossings JSON")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("CartPath — Crossing Classification")

    # Load inputs
    osm_data = load_json(args.osm_graph, "OSM graph")
    signals = load_json(args.signals, "Traffic signals")
    speed_data = load_json(args.speeds, "Speed classification")

    features = osm_data.get("features", [])
    print(f"  Loaded {len(features):,} road segments")
    print(f"  Loaded {len(signals):,} traffic signal nodes")

    # Find intersections where cart-legal roads meet >35 MPH roads
    print("\n  Finding crossings of cart-legal and major roads...")
    crossings = find_road_intersections(features, speed_data)
    print(f"  Found {len(crossings):,} crossing points")

    # Tag which crossings have traffic signals
    print("  Matching traffic signals to crossings...")
    crossings = tag_signalized_crossings(crossings, signals)

    signalized = sum(1 for c in crossings if c["has_signal"])
    unsignalized = len(crossings) - signalized
    print(f"  Signalized crossings:   {signalized:,}")
    print(f"  Unsignalized crossings: {unsignalized:,}")

    # Build node-level index for graph builder
    node_index = build_node_signal_index(crossings)

    output = {
        "crossings": crossings,
        "node_index": node_index,
        "summary": {
            "total": len(crossings),
            "signalized": signalized,
            "unsignalized": unsignalized,
        },
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Written to: {args.output}")


if __name__ == "__main__":
    main()
