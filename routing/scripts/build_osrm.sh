#!/usr/bin/env bash
# CartPath — OSRM Graph Build Script
# ====================================
# Builds the OSRM routing graph from the classified OSM data
# using the custom golf cart Lua profile.
#
# Usage:
#   ./build_osrm.sh                          # Uses default paths
#   ./build_osrm.sh /path/to/roads.osm       # Custom OSM file
#
# Supports native OSRM tools or Docker-based execution.
# On ARM64 (Oracle Cloud, Apple Silicon), builds a custom image
# since osrm/osrm-backend is x86-only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Defaults
OSM_FILE="${1:-$PROJECT_ROOT/pipeline/data/cartpath_roads.osm}"
PROFILE="$PROJECT_ROOT/routing/profiles/cart.lua"
DATA_DIR="$PROJECT_ROOT/routing/data"
OSRM_IMAGE="cartpath-osrm-tools"

echo "CartPath — OSRM Graph Build"
echo "  OSM file: $OSM_FILE"
echo "  Profile:  $PROFILE"
echo "  Output:   $DATA_DIR"
echo ""

# Validate inputs
if [ ! -f "$OSM_FILE" ]; then
    echo "ERROR: OSM file not found: $OSM_FILE"
    echo "  Run the data pipeline first: python pipeline/build_graph.py"
    exit 1
fi

if [ ! -f "$PROFILE" ]; then
    echo "ERROR: Lua profile not found: $PROFILE"
    exit 1
fi

mkdir -p "$DATA_DIR"

# Copy OSM file to data dir for OSRM processing
cp "$OSM_FILE" "$DATA_DIR/cartpath_roads.osm"

# Detect whether to use native OSRM or Docker
use_native=false
if command -v osrm-extract &>/dev/null; then
    use_native=true
fi

# Build the custom OSRM Docker image if needed (supports ARM64)
if [ "$use_native" = "false" ] && command -v docker &>/dev/null; then
    if ! docker image inspect "$OSRM_IMAGE" &>/dev/null; then
        echo "Building OSRM Docker image for $(uname -m) (first time only, ~5 min)..."
        docker build -t "$OSRM_IMAGE" -f "$PROJECT_ROOT/deploy/Dockerfile.osrm" "$PROJECT_ROOT"
    fi
fi

run_osrm_docker() {
    docker run --rm -t \
        -v "$DATA_DIR:/data" \
        -v "$(dirname "$PROFILE"):/profile:ro" \
        -e "LUA_PATH=/usr/local/share/osrm/profiles/?.lua;/usr/local/share/osrm/profiles/lib/?.lua;/profile/?.lua;;" \
        "$OSRM_IMAGE" \
        "$@"
}

echo "Step 1/3: osrm-extract (parsing road network)..."
if [ "$use_native" = "true" ]; then
    osrm-extract -p "$PROFILE" "$DATA_DIR/cartpath_roads.osm"
else
    run_osrm_docker osrm-extract -p /profile/cart.lua /data/cartpath_roads.osm
fi
echo "  Done."

echo ""
echo "Step 2/3: osrm-partition (building multi-level partition)..."
if [ "$use_native" = "true" ]; then
    osrm-partition "$DATA_DIR/cartpath_roads.osrm"
else
    run_osrm_docker osrm-partition /data/cartpath_roads.osrm
fi
echo "  Done."

echo ""
echo "Step 3/3: osrm-customize (applying weights)..."
if [ "$use_native" = "true" ]; then
    osrm-customize "$DATA_DIR/cartpath_roads.osrm"
else
    run_osrm_docker osrm-customize /data/cartpath_roads.osrm
fi
echo "  Done."

echo ""
echo "OSRM graph built successfully!"
echo "  Graph files: $DATA_DIR/cartpath_roads.osrm*"
