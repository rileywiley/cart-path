from __future__ import annotations
"""
CartPath Data Audit — Baldwin Park, FL (30-mile radius)
========================================================
Queries the OSM Overpass API to measure speed limit and road surface
tag coverage for all drivable roads in the pilot region.

Usage:
    python cartpath_data_audit.py

Output:
    - Console summary with coverage percentages
    - cartpath_audit_results.csv with per-road-type breakdown
    - cartpath_audit_report.json with full structured results

Requirements:
    pip install requests pandas
"""

import requests
import json
import time
import pandas as pd
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────────────
# Baldwin Park, FL center coordinates
CENTER_LAT = 28.5641
CENTER_LON = -81.3089
RADIUS_MILES = 30
RADIUS_METERS = int(RADIUS_MILES * 1609.34)  # ~48,280m

# Road types relevant to golf cart navigation
# Excludes motorway, motorway_link, trunk, trunk_link (always >35 MPH)
ROAD_TYPES = [
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "residential",
    "unclassified",
    "living_street",
    "service",
]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TIMEOUT = 180  # seconds


def build_query() -> str:
    """Build the Overpass QL query to fetch all relevant roads with their tags."""
    highway_filter = "|".join(ROAD_TYPES)
    query = f"""
[out:json][timeout:{TIMEOUT}];
(
  way["highway"~"^({highway_filter})$"]
    (around:{RADIUS_METERS},{CENTER_LAT},{CENTER_LON});
);
out tags;
"""
    return query.strip()


def run_query(query: str) -> dict:
    """Execute the Overpass query and return the JSON response."""
    print(f"Querying Overpass API...")
    print(f"  Center: {CENTER_LAT}, {CENTER_LON}")
    print(f"  Radius: {RADIUS_MILES} miles ({RADIUS_METERS:,} meters)")
    print(f"  Road types: {len(ROAD_TYPES)}")
    print()

    start = time.time()
    resp = requests.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=TIMEOUT + 30,
    )
    elapsed = time.time() - start

    if resp.status_code != 200:
        print(f"ERROR: Overpass returned status {resp.status_code}")
        print(resp.text[:500])
        raise SystemExit(1)

    data = resp.json()
    count = len(data.get("elements", []))
    print(f"  Received {count:,} road segments in {elapsed:.1f}s")
    print()
    return data


def classify_surface(tags: dict) -> str:
    """Classify a road's surface as paved, unpaved, or unknown."""
    surface = tags.get("surface", "").lower()

    paved_values = {
        "paved", "asphalt", "concrete", "concrete:lanes", "concrete:plates",
        "paving_stones", "sett", "cobblestone", "metal", "wood",
        "unhewn_cobblestone", "brickwork", "brick",
    }
    unpaved_values = {
        "unpaved", "gravel", "fine_gravel", "compacted", "dirt", "earth",
        "grass", "ground", "mud", "sand", "woodchips", "pebblestone",
        "grass_paver", "clay",
    }

    if surface in paved_values:
        return "paved"
    elif surface in unpaved_values:
        return "unpaved"
    elif surface:
        return f"other ({surface})"
    else:
        return "unknown"


def classify_speed_source(tags: dict) -> str:
    """Determine how we know (or can infer) the speed limit."""
    if "maxspeed" in tags:
        return "explicit_tag"
    # Check for source:maxspeed or maxspeed:type (some mappers use these)
    if "source:maxspeed" in tags or "maxspeed:type" in tags:
        return "implicit_tagged"
    return "untagged"


def parse_speed(tags: dict) -> float | None:
    """Parse the maxspeed tag into a numeric MPH value."""
    raw = tags.get("maxspeed", "")
    if not raw:
        return None

    raw = raw.strip().lower()

    # Handle special values
    if raw in ("none", "signals", "walk", "variable"):
        return None

    # Try to parse numeric value
    try:
        if "mph" in raw:
            return float(raw.replace("mph", "").strip())
        elif "km/h" in raw or "kmh" in raw:
            val = float(raw.replace("km/h", "").replace("kmh", "").strip())
            return round(val * 0.621371, 1)
        else:
            # Assume km/h if no unit (OSM convention), but in the US it's usually mph
            val = float(raw)
            if val > 100:  # Likely km/h
                return round(val * 0.621371, 1)
            return val  # Likely already mph
    except ValueError:
        return None


def infer_speed_from_road_type(highway: str) -> dict:
    """
    Infer likely speed limit from Florida road classification conventions.
    Returns a dict with the inferred speed and confidence level.
    Based on FDOT conventions documented in the OSM Florida wiki.
    """
    inferences = {
        "primary":        {"speed_mph": 45, "range": "40-55", "confidence": "medium", "cart_legal": False},
        "primary_link":   {"speed_mph": 35, "range": "25-45", "confidence": "low",    "cart_legal": "maybe"},
        "secondary":      {"speed_mph": 40, "range": "35-55", "confidence": "medium", "cart_legal": False},
        "secondary_link": {"speed_mph": 35, "range": "25-40", "confidence": "low",    "cart_legal": "maybe"},
        "tertiary":       {"speed_mph": 30, "range": "25-35", "confidence": "medium", "cart_legal": True},
        "tertiary_link":  {"speed_mph": 25, "range": "25-35", "confidence": "medium", "cart_legal": True},
        "residential":    {"speed_mph": 25, "range": "15-30", "confidence": "high",   "cart_legal": True},
        "unclassified":   {"speed_mph": 35, "range": "25-45", "confidence": "low",    "cart_legal": "maybe"},
        "living_street":  {"speed_mph": 15, "range": "10-20", "confidence": "high",   "cart_legal": True},
        "service":        {"speed_mph": 15, "range": "10-25", "confidence": "high",   "cart_legal": True},
    }
    return inferences.get(highway, {"speed_mph": None, "range": "unknown", "confidence": "none", "cart_legal": "unknown"})


def analyze(data: dict) -> dict:
    """Analyze the Overpass response and compute coverage statistics."""
    elements = data.get("elements", [])

    results = {
        "total_ways": len(elements),
        "by_highway_type": defaultdict(lambda: {
            "count": 0,
            "has_maxspeed": 0,
            "has_surface": 0,
            "surface_paved": 0,
            "surface_unpaved": 0,
            "surface_unknown": 0,
            "speed_lte_35": 0,
            "speed_gt_35": 0,
            "speed_unknown": 0,
        }),
        "speed_distribution": defaultdict(int),
        "surface_values": defaultdict(int),
        "cart_legal_estimate": {
            "definitely_legal": 0,
            "likely_legal": 0,
            "likely_illegal": 0,
            "unknown": 0,
        },
    }

    for el in elements:
        tags = el.get("tags", {})
        highway = tags.get("highway", "unknown")
        bucket = results["by_highway_type"][highway]
        bucket["count"] += 1

        # ── Speed analysis ──
        speed_source = classify_speed_source(tags)
        speed_mph = parse_speed(tags)

        if speed_mph is not None:
            bucket["has_maxspeed"] += 1
            rounded = int(round(speed_mph / 5) * 5)  # Round to nearest 5
            results["speed_distribution"][rounded] += 1

            if speed_mph <= 35:
                bucket["speed_lte_35"] += 1
                results["cart_legal_estimate"]["definitely_legal"] += 1
            else:
                bucket["speed_gt_35"] += 1
                results["cart_legal_estimate"]["likely_illegal"] += 1
        else:
            bucket["speed_unknown"] += 1
            inference = infer_speed_from_road_type(highway)
            if inference["cart_legal"] is True:
                results["cart_legal_estimate"]["likely_legal"] += 1
            elif inference["cart_legal"] is False:
                results["cart_legal_estimate"]["likely_illegal"] += 1
            else:
                results["cart_legal_estimate"]["unknown"] += 1

        # ── Surface analysis ──
        surface_class = classify_surface(tags)
        results["surface_values"][tags.get("surface", "(none)")] += 1

        if surface_class == "paved":
            bucket["has_surface"] += 1
            bucket["surface_paved"] += 1
        elif surface_class == "unpaved":
            bucket["has_surface"] += 1
            bucket["surface_unpaved"] += 1
        elif surface_class.startswith("other"):
            bucket["has_surface"] += 1
            bucket["surface_paved"] += 1  # Most "other" in FL are paved variants
        else:
            bucket["surface_unknown"] += 1

    return results


def print_report(results: dict):
    """Print a formatted console report."""
    total = results["total_ways"]
    print("=" * 70)
    print("  CARTPATH DATA AUDIT — BALDWIN PARK, FL (30-MILE RADIUS)")
    print("=" * 70)
    print()
    print(f"  Total road segments analyzed: {total:,}")
    print()

    # ── Speed limit coverage ──
    print("─" * 70)
    print("  SPEED LIMIT COVERAGE")
    print("─" * 70)

    total_with_speed = sum(b["has_maxspeed"] for b in results["by_highway_type"].values())
    total_without = total - total_with_speed
    pct_explicit = (total_with_speed / total * 100) if total else 0

    print(f"  Explicit maxspeed tag:  {total_with_speed:>7,}  ({pct_explicit:.1f}%)")
    print(f"  No maxspeed tag:        {total_without:>7,}  ({100 - pct_explicit:.1f}%)")
    print()

    # Speed distribution
    print("  Speed limit distribution (tagged roads):")
    for speed in sorted(results["speed_distribution"].keys()):
        count = results["speed_distribution"][speed]
        bar = "█" * max(1, int(count / total * 200))
        marker = " ← cart legal" if speed <= 35 else ""
        print(f"    {speed:>3} mph: {count:>6,}  {bar}{marker}")
    print()

    # Cart legality estimate
    est = results["cart_legal_estimate"]
    def_legal = est["definitely_legal"]
    likely_legal = est["likely_legal"]
    likely_illegal = est["likely_illegal"]
    unknown = est["unknown"]

    print("  Cart-legality estimate (tagged + inferred):")
    print(f"    Definitely ≤35 mph (tagged):     {def_legal:>7,}  ({def_legal/total*100:.1f}%)")
    print(f"    Likely ≤35 mph (from road type):  {likely_legal:>7,}  ({likely_legal/total*100:.1f}%)")
    print(f"    Likely >35 mph:                   {likely_illegal:>7,}  ({likely_illegal/total*100:.1f}%)")
    print(f"    Unknown:                          {unknown:>7,}  ({unknown/total*100:.1f}%)")
    print()

    # ── Surface coverage ──
    print("─" * 70)
    print("  ROAD SURFACE COVERAGE")
    print("─" * 70)

    total_with_surface = sum(b["has_surface"] for b in results["by_highway_type"].values())
    total_paved = sum(b["surface_paved"] for b in results["by_highway_type"].values())
    total_unpaved = sum(b["surface_unpaved"] for b in results["by_highway_type"].values())
    total_surface_unknown = sum(b["surface_unknown"] for b in results["by_highway_type"].values())
    pct_surface = (total_with_surface / total * 100) if total else 0

    print(f"  Has surface tag:     {total_with_surface:>7,}  ({pct_surface:.1f}%)")
    print(f"    ├─ Paved:          {total_paved:>7,}")
    print(f"    └─ Unpaved:        {total_unpaved:>7,}")
    print(f"  No surface tag:      {total_surface_unknown:>7,}  ({100 - pct_surface:.1f}%)")
    print()

    # Top surface values
    print("  Top surface tag values:")
    sorted_surfaces = sorted(results["surface_values"].items(), key=lambda x: -x[1])
    for surface, count in sorted_surfaces[:15]:
        pct = count / total * 100
        print(f"    {surface:<25} {count:>7,}  ({pct:.1f}%)")
    print()

    # ── Per road type breakdown ──
    print("─" * 70)
    print("  BREAKDOWN BY ROAD TYPE")
    print("─" * 70)

    rows = []
    for highway in ROAD_TYPES:
        b = results["by_highway_type"].get(highway)
        if not b or b["count"] == 0:
            continue
        inference = infer_speed_from_road_type(highway)
        rows.append({
            "road_type": highway,
            "count": b["count"],
            "has_speed_%": round(b["has_maxspeed"] / b["count"] * 100, 1),
            "has_surface_%": round(b["has_surface"] / b["count"] * 100, 1),
            "inferred_speed": inference["range"],
            "cart_legal": str(inference["cart_legal"]),
            "confidence": inference["confidence"],
        })

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    print()

    # ── Summary assessment ──
    usable_speed = def_legal + likely_legal
    usable_pct = (usable_speed / total * 100) if total else 0

    print("=" * 70)
    print("  ASSESSMENT SUMMARY")
    print("=" * 70)
    print()
    print(f"  Speed limit coverage (explicit):     {pct_explicit:.1f}%")
    print(f"  Speed limit coverage (w/ inference):  {usable_pct:.1f}%")
    print(f"  Surface tag coverage (explicit):      {pct_surface:.1f}%")
    print()

    if pct_explicit >= 30:
        print("  ✓ Speed data: GOOD — Explicit tags plus road-type inference")
        print("    gives strong coverage. FDOT open data can fill remaining gaps.")
    elif pct_explicit >= 15:
        print("  △ Speed data: MODERATE — Will need FDOT data + inference.")
        print("    HERE API may be needed for edge cases.")
    else:
        print("  ✗ Speed data: LOW explicit coverage.")
        print("    FDOT open data + inference are essential. Consider HERE API.")

    if pct_surface >= 40:
        print("  ✓ Surface data: GOOD — Explicit tags cover most roads.")
        print("    Road-type heuristic fills the rest for suburban Orlando.")
    elif pct_surface >= 20:
        print("  △ Surface data: MODERATE — Heuristic + Mapillary dataset needed.")
    else:
        print("  △ Surface data: LOW explicit tags, but road-type heuristic")
        print("    is reliable in suburban FL (residential = paved).")

    print()
    print("  Files saved:")
    print("    → cartpath_audit_results.csv")
    print("    → cartpath_audit_report.json")
    print()

    return df


def main():
    query = build_query()

    print("─" * 70)
    print("  Overpass query:")
    print("─" * 70)
    print(query)
    print()

    data = run_query(query)
    results = analyze(data)
    df = print_report(results)

    # Save CSV
    df.to_csv("cartpath_audit_results.csv", index=False)

    # Save full JSON report
    json_results = {
        "config": {
            "center": {"lat": CENTER_LAT, "lon": CENTER_LON},
            "radius_miles": RADIUS_MILES,
            "road_types": ROAD_TYPES,
            "query_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "summary": {
            "total_ways": results["total_ways"],
            "speed_explicit_pct": round(
                sum(b["has_maxspeed"] for b in results["by_highway_type"].values())
                / max(results["total_ways"], 1) * 100, 1
            ),
            "surface_tagged_pct": round(
                sum(b["has_surface"] for b in results["by_highway_type"].values())
                / max(results["total_ways"], 1) * 100, 1
            ),
        },
        "cart_legal_estimate": dict(results["cart_legal_estimate"]),
        "speed_distribution": dict(results["speed_distribution"]),
        "surface_values": dict(results["surface_values"]),
        "by_highway_type": {k: dict(v) for k, v in results["by_highway_type"].items()},
    }
    with open("cartpath_audit_report.json", "w") as f:
        json.dump(json_results, f, indent=2)


if __name__ == "__main__":
    main()
