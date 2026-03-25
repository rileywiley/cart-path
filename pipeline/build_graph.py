#!/usr/bin/env python3
"""
CartPath — OSRM Graph Builder
================================
Combines speed and surface classifications to generate an OSRM-ready OSM XML
file and a coverage boundary GeoJSON. Also writes pipeline health.json.

Usage:
    python build_graph.py
    python build_graph.py --osm-graph data/osm_roads.geojson --speeds data/classified_speeds.json --surfaces data/classified_surfaces.json
    python build_graph.py --help

Requirements:
    pip install shapely
"""

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter

from shapely.geometry import MultiPoint, shape
from shapely.ops import unary_union


# ── Constants ─────────────────────────────────────────────────────────
MAX_SPEED_MPH = 35
DEFAULT_CART_SPEED_MPH = 23
SERVICE_ROAD_SPEED_MPH = 10


def load_json(path: str, label: str) -> dict:
    """Load a JSON file or exit with error."""
    if not os.path.exists(path):
        print(f"ERROR: {label} not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def build_osm_xml(features: list, speed_data: dict, surface_data: dict) -> ET.Element:
    """
    Build an OSM XML document from classified features.
    Includes custom tags for cart_legal, surface_type, routing_speed.
    """
    osm = ET.Element("osm", version="0.6", generator="cartpath-build-graph")

    node_id_counter = -1
    node_cache = {}  # (lon, lat) -> node_id

    def get_node_id(lon: float, lat: float) -> int:
        nonlocal node_id_counter
        # Round to 7 decimal places to deduplicate nearby nodes
        key = (round(lon, 7), round(lat, 7))
        if key not in node_cache:
            node_cache[key] = node_id_counter
            node_id_counter -= 1
        return node_cache[key]

    # First pass: collect all nodes and ways
    ways_data = []
    for feature in features:
        props = feature["properties"]
        osm_id = str(props.get("osm_id", ""))
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [])

        if not coords or len(coords) < 2:
            continue

        # Check if excluded
        speed_info = speed_data.get(osm_id, {})
        if speed_info.get("excluded"):
            continue

        surface_info = surface_data.get(osm_id, {})

        # Build node references
        node_refs = []
        for lon, lat in coords:
            nid = get_node_id(lon, lat)
            node_refs.append(nid)

        ways_data.append({
            "osm_id": props.get("osm_id"),
            "node_refs": node_refs,
            "props": props,
            "speed_info": speed_info,
            "surface_info": surface_info,
        })

    # Write nodes
    for (lon, lat), nid in node_cache.items():
        ET.SubElement(osm, "node", id=str(nid), lat=str(lat), lon=str(lon), version="1")

    # Write ways with enriched tags
    for wd in ways_data:
        way = ET.SubElement(osm, "way", id=str(wd["osm_id"]), version="1")

        for nid in wd["node_refs"]:
            ET.SubElement(way, "nd", ref=str(nid))

        props = wd["props"]
        speed_info = wd["speed_info"]
        surface_info = wd["surface_info"]

        # Standard OSM tags
        tags = {
            "highway": props.get("highway", ""),
            "name": props.get("name", ""),
            "oneway": props.get("oneway", ""),
            "lanes": props.get("lanes", ""),
        }

        # Speed tags
        if speed_info.get("speed_limit") is not None:
            tags["maxspeed"] = str(int(speed_info["speed_limit"]))
        tags["cartpath:speed_source"] = speed_info.get("speed_source", "unknown")
        tags["cartpath:cart_legal"] = str(speed_info.get("cart_legal", "unknown")).lower()
        tags["cartpath:routing_speed"] = str(speed_info.get("routing_speed", DEFAULT_CART_SPEED_MPH))

        # Surface tags
        if props.get("surface"):
            tags["surface"] = props["surface"]
        tags["cartpath:surface_type"] = surface_info.get("surface_type", "unknown")
        tags["cartpath:surface_source"] = surface_info.get("surface_source", "unknown")

        # Service road subtype
        if props.get("service"):
            tags["service"] = props["service"]

        for k, v in tags.items():
            if v:
                ET.SubElement(way, "tag", k=k, v=v)

    return osm


def generate_coverage_boundary(features: list, speed_data: dict) -> dict:
    """Generate a convex hull GeoJSON polygon from all cart-legal road endpoints."""
    points = []
    for feature in features:
        props = feature["properties"]
        osm_id = str(props.get("osm_id", ""))
        speed_info = speed_data.get(osm_id, {})

        if speed_info.get("excluded"):
            continue
        if speed_info.get("cart_legal") != True:
            continue

        coords = feature.get("geometry", {}).get("coordinates", [])
        for lon, lat in coords:
            points.append((lon, lat))

    if len(points) < 3:
        print("  WARNING: Too few cart-legal points for coverage boundary", file=sys.stderr)
        return None

    hull = MultiPoint(points).convex_hull

    return {
        "type": "Feature",
        "properties": {"name": "CartPath Coverage Area", "type": "coverage_boundary"},
        "geometry": json.loads(json.dumps(hull.__geo_interface__)),
    }


def write_health_json(
    output_dir: str, total: int, speed_data: dict, surface_data: dict,
):
    """Write pipeline health.json with run statistics."""
    speed_sources = Counter()
    cart_legal_counts = Counter()
    surface_types = Counter()
    excluded = 0

    for v in speed_data.values():
        if v.get("excluded"):
            excluded += 1
        else:
            speed_sources[v.get("speed_source", "unknown")] += 1
            cart_legal_counts[str(v.get("cart_legal", "unknown"))] += 1

    for v in surface_data.values():
        surface_types[v.get("surface_type", "unknown")] += 1

    health = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pipeline_version": "1.0",
        "total_segments": total,
        "excluded_segments": excluded,
        "speed_classification": dict(speed_sources),
        "cart_legality": dict(cart_legal_counts),
        "surface_classification": dict(surface_types),
        "fdot_match_rate": speed_sources.get("fdot", 0) / max(total, 1),
    }

    path = os.path.join(output_dir, "health.json")
    with open(path, "w") as f:
        json.dump(health, f, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(
        description="Build OSRM-ready OSM XML and coverage boundary for CartPath."
    )
    parser.add_argument("--osm-graph", default="pipeline/data/osm_roads.geojson", help="Input OSM GeoJSON")
    parser.add_argument("--speeds", default="pipeline/data/classified_speeds.json", help="Speed classification JSON")
    parser.add_argument("--surfaces", default="pipeline/data/classified_surfaces.json", help="Surface classification JSON")
    parser.add_argument("--output-dir", default="pipeline/data", help="Output directory")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("CartPath — OSRM Graph Builder")

    # Load inputs
    osm_data = load_json(args.osm_graph, "OSM graph")
    speed_data = load_json(args.speeds, "Speed classification")
    surface_data = load_json(args.surfaces, "Surface classification")

    features = osm_data.get("features", [])
    print(f"  Loaded {len(features):,} OSM segments")
    print(f"  Speed classifications: {len(speed_data):,}")
    print(f"  Surface classifications: {len(surface_data):,}")

    # Build OSM XML
    print("\n  Building OSM XML...")
    osm_xml = build_osm_xml(features, speed_data, surface_data)

    os.makedirs(args.output_dir, exist_ok=True)
    osm_path = os.path.join(args.output_dir, "cartpath_roads.osm")
    tree = ET.ElementTree(osm_xml)
    ET.indent(tree, space="  ")
    tree.write(osm_path, encoding="unicode", xml_declaration=True)
    osm_size = os.path.getsize(osm_path) / 1024 / 1024
    print(f"    Written: {osm_path} ({osm_size:.1f} MB)")

    # Generate coverage boundary
    print("  Generating coverage boundary...")
    boundary = generate_coverage_boundary(features, speed_data)
    if boundary:
        boundary_fc = {"type": "FeatureCollection", "features": [boundary]}
        boundary_path = os.path.join(args.output_dir, "coverage_boundary.geojson")
        with open(boundary_path, "w") as f:
            json.dump(boundary_fc, f)
        print(f"    Written: {boundary_path}")
    else:
        print("    WARNING: Could not generate coverage boundary")

    # Write health.json
    health_path = write_health_json(args.output_dir, len(features), speed_data, surface_data)
    print(f"    Written: {health_path}")

    # Summary
    excluded = sum(1 for v in speed_data.values() if v.get("excluded"))
    cart_legal = sum(1 for v in speed_data.values() if v.get("cart_legal") == True)
    print(f"\n  Graph Summary:")
    print(f"    Total segments:     {len(features):,}")
    print(f"    Excluded:           {excluded:,}")
    print(f"    Cart-legal:         {cart_legal:,}")
    print(f"    In routing graph:   {len(features) - excluded:,}")
    print(f"\n  Next: Run build_osrm.sh to build the OSRM routing graph")


if __name__ == "__main__":
    main()
