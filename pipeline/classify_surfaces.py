#!/usr/bin/env python3
"""
CartPath — Surface Classification Pipeline
============================================
Applies 3-tier surface classification to OSM road segments.

Tiers:
  1. Explicit OSM surface tags (~20.7%)
  2. Road-type heuristic — suburban FL = paved by default (~77%)
  3. Mapillary dataset (optional for v1, heuristic covers ~98%)

Usage:
    python classify_surfaces.py
    python classify_surfaces.py --osm-graph data/osm_roads.geojson
    python classify_surfaces.py --help

Requirements:
    pip install pandas
"""

import argparse
import json
import os
import sys
from collections import Counter

# ── Surface value mappings ────────────────────────────────────────────
PAVED_VALUES = {
    "paved", "asphalt", "concrete", "concrete:lanes", "concrete:plates",
    "paving_stones", "sett", "cobblestone", "metal", "wood",
    "unhewn_cobblestone", "brickwork", "brick", "bricks",
}

UNPAVED_VALUES = {
    "unpaved", "gravel", "fine_gravel", "compacted", "dirt", "earth",
    "grass", "ground", "mud", "sand", "woodchips", "pebblestone",
    "grass_paver", "clay",
}

# Road types that default to "paved" in suburban Central Florida
# Based on audit data: residential roads tagged 97% paved, service 94.2% paved
PAVED_BY_DEFAULT_TYPES = {
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "residential",
    "living_street",
    "service",
}


def classify_surface(props: dict) -> dict:
    """
    Classify a single road segment's surface type.

    Returns dict with: surface_type, surface_source
    """
    surface_tag = props.get("surface", "").strip().lower()
    highway = props.get("highway", "")

    # ── Tier 1: Explicit OSM surface tag ──
    if surface_tag:
        if surface_tag in PAVED_VALUES:
            return {"surface_type": "paved", "surface_source": "osm_tag"}
        elif surface_tag in UNPAVED_VALUES:
            return {"surface_type": "unpaved", "surface_source": "osm_tag"}
        else:
            # Unknown surface value — assume paved for known road types in FL
            if highway in PAVED_BY_DEFAULT_TYPES:
                return {"surface_type": "paved", "surface_source": "osm_tag_inferred"}
            return {"surface_type": "unknown", "surface_source": "osm_tag_unknown"}

    # ── Tier 2: Road-type heuristic ──
    if highway in PAVED_BY_DEFAULT_TYPES:
        return {"surface_type": "paved", "surface_source": "heuristic"}

    # ── Tier 3: Mapillary (not implemented for v1) ──
    # For v1, remaining roads (primarily unclassified) are marked unknown
    return {"surface_type": "unknown", "surface_source": "unknown"}


def main():
    parser = argparse.ArgumentParser(
        description="Apply 3-tier surface classification to OSM road segments for CartPath."
    )
    parser.add_argument("--osm-graph", default="pipeline/data/osm_roads.geojson", help="Input OSM GeoJSON")
    parser.add_argument("--output", "-o", default="pipeline/data/classified_surfaces.json", help="Output classified JSON")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("CartPath — Surface Classification")

    # Load OSM data
    if not os.path.exists(args.osm_graph):
        print(f"ERROR: OSM graph not found: {args.osm_graph}", file=sys.stderr)
        sys.exit(1)

    with open(args.osm_graph) as f:
        osm_data = json.load(f)
    features = osm_data.get("features", [])
    print(f"  Loaded {len(features):,} OSM segments")

    # Classify each segment
    classifications = {}
    counters = {
        "type": Counter(),
        "source": Counter(),
    }

    for feature in features:
        props = feature["properties"]
        osm_id = str(props.get("osm_id", ""))
        result = classify_surface(props)
        classifications[osm_id] = result
        counters["type"][result["surface_type"]] += 1
        counters["source"][result["surface_source"]] += 1

    # Write output
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(classifications, f)

    # Summary
    total = len(features)
    print(f"\n  Classification Summary ({total:,} segments):")
    print(f"    By surface type:")
    for stype, count in counters["type"].most_common():
        print(f"      {stype:<20} {count:>7,}  ({count / total * 100:.1f}%)")
    print(f"    By source:")
    for source, count in counters["source"].most_common():
        print(f"      {source:<20} {count:>7,}  ({count / total * 100:.1f}%)")
    print(f"\n  Output: {args.output}")


if __name__ == "__main__":
    main()
