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
# Prerequisites:
#   - OSRM backend tools installed (osrm-extract, osrm-partition, osrm-customize)
#   - Or use Docker: docker pull osrm/osrm-backend
#
# The script supports both native OSRM tools and Docker-based execution.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Defaults
OSM_FILE="${1:-$PROJECT_ROOT/pipeline/data/cartpath_roads.osm}"
PROFILE="$PROJECT_ROOT/routing/profiles/cart.lua"
DATA_DIR="$PROJECT_ROOT/routing/data"
USE_DOCKER="${USE_DOCKER:-auto}"

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

# Detect OSRM installation
run_osrm() {
    local cmd="$1"
    shift

    if [ "$USE_DOCKER" = "native" ] || command -v "$cmd" &>/dev/null; then
        "$cmd" "$@"
    elif [ "$USE_DOCKER" = "docker" ] || command -v docker &>/dev/null; then
        docker run --rm -t \
            -v "$DATA_DIR:/data" \
            -v "$PROFILE:/profile/cart.lua:ro" \
            osrm/osrm-backend \
            "$cmd" "$@"
    else
        echo "ERROR: Neither OSRM tools nor Docker found."
        echo "  Install OSRM: https://github.com/Project-OSRM/osrm-backend"
        echo "  Or install Docker and pull osrm/osrm-backend"
        exit 1
    fi
}

echo "Step 1/3: osrm-extract (parsing road network)..."
if command -v osrm-extract &>/dev/null; then
    osrm-extract -p "$PROFILE" "$DATA_DIR/cartpath_roads.osm"
elif command -v docker &>/dev/null; then
    docker run --rm -t \
        -v "$DATA_DIR:/data" \
        -v "$(dirname "$PROFILE"):/profile:ro" \
        osrm/osrm-backend \
        osrm-extract -p /profile/cart.lua /data/cartpath_roads.osm
else
    echo "ERROR: No OSRM tools available."
    exit 1
fi
echo "  Done."

echo ""
echo "Step 2/3: osrm-partition (building multi-level partition)..."
if command -v osrm-partition &>/dev/null; then
    osrm-partition "$DATA_DIR/cartpath_roads.osrm"
else
    docker run --rm -t \
        -v "$DATA_DIR:/data" \
        osrm/osrm-backend \
        osrm-partition /data/cartpath_roads.osrm
fi
echo "  Done."

echo ""
echo "Step 3/3: osrm-customize (applying weights)..."
if command -v osrm-customize &>/dev/null; then
    osrm-customize "$DATA_DIR/cartpath_roads.osrm"
else
    docker run --rm -t \
        -v "$DATA_DIR:/data" \
        osrm/osrm-backend \
        osrm-customize /data/cartpath_roads.osrm
fi
echo "  Done."

echo ""
echo "OSRM graph built successfully!"
echo "  Graph files: $DATA_DIR/cartpath_roads.osrm*"
echo ""
echo "To start the OSRM server:"
echo "  osrm-routed --algorithm mld $DATA_DIR/cartpath_roads.osrm"
echo "  # Or with Docker:"
echo "  docker run -t -p 5000:5000 -v $DATA_DIR:/data osrm/osrm-backend osrm-routed --algorithm mld /data/cartpath_roads.osrm"
